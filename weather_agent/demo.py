"""Offline stand-ins so the app can run with no API keys (WEATHER_AGENT_DEMO=1).

Both classes are deterministic. The numbers are synthetic sample data and are
NOT real weather — they exist only to demonstrate the UI and the pipeline.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from types import SimpleNamespace

from .client import WeatherAPIError
from .models import DayReport

_KNOWN = {
    "paris": "France", "london": "United Kingdom", "tokyo": "Japan", "madrid": "Spain",
    "berlin": "Germany", "cairo": "Egypt", "toronto": "Canada", "sydney": "Australia",
    "nairobi": "Kenya", "lima": "Peru", "oslo": "Norway", "rome": "Italy",
    "casablanca": "Morocco", "seoul": "South Korea", "chicago": "United States",
}
_CONDITIONS = ["Sunny", "Partly cloudy", "Cloudy", "Patchy rain nearby", "Light rain", "Overcast", "Clear"]


class KeywordPlanner:
    """Fake chat model: answers the planner prompt with JSON using simple keyword rules."""

    def invoke(self, prompt: str):
        query = prompt.rsplit("Question:", 1)[-1].replace("JSON:", "").strip()
        low = query.lower()
        is_weather = bool(re.search(r"weather|forecast|rain|temperature|sunny|snow|hot|cold|humid", low))
        cities = [c.title() for c in _KNOWN if re.search(rf"\b{c}\b", low)]
        if cities and re.search(r"day|week|now|today|tomorrow|yesterday|\d{4}-\d{2}-\d{2}", low):
            is_weather = True  # "past 2 days in London" has no weather keyword but is clearly one

        mode, days, when = "current", 1, None
        number = re.search(r"(\d+)\s*days?", low)
        if "past" in low or "last" in low or "yesterday" in low:
            mode, days = "past", int(number.group(1)) if number else 3
        elif "next" in low or "forecast" in low or "tomorrow" in low:
            mode, days = "forecast", int(number.group(1)) if number else 3
        iso = re.search(r"\d{4}-\d{2}-\d{2}", low)
        if iso:
            mode, when = "on_date", iso.group(0)

        payload = {"is_weather": is_weather, "cities": cities, "mode": mode, "days": days, "date": when}
        return SimpleNamespace(content=json.dumps(payload))


def _seed(city: str, day: date) -> int:
    return int(hashlib.sha256(f"{city}{day}".encode()).hexdigest()[:8], 16)


def _make_day(city: str, day: date) -> DayReport:
    country = _KNOWN.get(city.lower())
    if country is None:
        raise WeatherAPIError("No matching location found.")
    s = _seed(city, day)
    low = 8 + s % 12
    high = low + 4 + (s >> 4) % 7
    return DayReport(
        city=city,
        country=country,
        day=day,
        condition=_CONDITIONS[(s >> 8) % len(_CONDITIONS)],
        min_c=float(low),
        max_c=float(high),
        avg_c=round((low + high) / 2, 1),
        humidity=float(45 + (s >> 12) % 40),
        wind_kph=round(8 + (s >> 16) % 25, 1),
        rain_chance=((s >> 20) % 10) * 10,
    )


class SampleSource:
    """Fake weather provider with the same interface as WeatherClient."""

    def current(self, city: str) -> list[DayReport]:
        d = _make_day(city, date.today())
        d.is_live_reading, d.min_c, d.max_c, d.rain_chance = True, None, None, None
        return [d]

    def forecast(self, city: str, days: int) -> list[DayReport]:
        return [_make_day(city, date.today() + timedelta(days=n)) for n in range(days)]

    def past_days(self, city: str, days: int) -> list[DayReport]:
        return [_make_day(city, date.today() - timedelta(days=n)) for n in range(days, 0, -1)]

    def on_date(self, city: str, target: date) -> list[DayReport]:
        return [_make_day(city, target)]
