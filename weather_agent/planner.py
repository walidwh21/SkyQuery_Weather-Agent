"""Turn a free-text question into a QueryPlan.

The language model does the understanding; plain Python does the date maths.
That split keeps the model's job small (return JSON) and makes the result testable.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Protocol

from .models import Mode, QueryPlan


class SupportsInvoke(Protocol):
    def invoke(self, prompt: str):  # returns an object with `.content`
        ...


PROMPT = """You convert weather questions into JSON.
Today's date is {today}.

Return ONLY a JSON object with these keys:
  "is_weather": true if the question asks about weather, otherwise false
  "cities":     list of city names mentioned (empty list if none)
  "mode":       one of "current", "past", "forecast", "on_date"
  "days":       integer number of days for "past" / "forecast" (default 3)
  "date":       "YYYY-MM-DD" when the user names one specific date, else null

Rules:
- "now", "today", "is it raining" -> mode "current".
- "last/past N days" -> mode "past".
- "next N days", "forecast" -> mode "forecast".
- A specific calendar date -> mode "on_date" and fill "date".
- Several cities share the same mode.

Question: {query}
JSON:"""


class PlanError(ValueError):
    pass


def _extract_json(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        braces = re.search(r"\{.*\}", text, re.DOTALL)
        if braces:
            text = braces.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanError(f"Model did not return valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PlanError("Model JSON must be an object")
    return data


def _clamp(value, low: int, high: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def parse_plan(raw: str, today: date, max_days: int = 14) -> QueryPlan:
    """Validate the model's JSON and normalise it into a QueryPlan."""
    data = _extract_json(raw)

    if not data.get("is_weather"):
        return QueryPlan(is_weather=False)

    cities = [str(c).strip().title() for c in data.get("cities") or [] if str(c).strip()]
    # preserve order, drop duplicates
    cities = list(dict.fromkeys(cities))

    try:
        mode = Mode(str(data.get("mode", "current")).lower())
    except ValueError:
        mode = Mode.CURRENT

    days = _clamp(data.get("days"), 1, max_days, default=3)
    target: date | None = None

    if mode is Mode.ON_DATE:
        try:
            target = datetime.strptime(str(data.get("date")), "%Y-%m-%d").date()
        except ValueError:
            mode, target = Mode.CURRENT, None  # unusable date: fall back gracefully
        else:
            if target == today:
                mode, target = Mode.CURRENT, None

    if mode is Mode.CURRENT:
        days = 1

    return QueryPlan(is_weather=True, cities=cities, mode=mode, days=days, target_date=target)


def plan_query(llm: SupportsInvoke, query: str, today: date | None = None) -> QueryPlan:
    today = today or date.today()
    response = llm.invoke(PROMPT.format(today=today.isoformat(), query=query))
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):  # some chat models return content parts
        content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return parse_plan(content, today)
