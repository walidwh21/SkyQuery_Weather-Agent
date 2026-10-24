"""The three stages of the agent, written as plain functions over a state dict.

`graph.py` wires these same stages into a LangGraph; `Pipeline.run` executes them
in order without any framework, which is what the tests and the CLI fallback use.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Protocol, TypedDict

from .client import WeatherAPIError
from .formatter import to_markdown
from .models import CityFailure, DayReport, Mode, QueryPlan
from .planner import PlanError, SupportsInvoke, plan_query

NOT_WEATHER = "I can only help with weather questions — try asking about a city's forecast."
NO_CITY = "Which city should I look up? Please mention one in your question."


class AgentState(TypedDict, total=False):
    query: str
    plan: QueryPlan
    reports: list[DayReport]
    failures: list[CityFailure]
    answer: str
    status: str  # "ok" | "off_topic" | "needs_city" | "error"


class WeatherSource(Protocol):
    def current(self, city: str) -> list[DayReport]: ...
    def forecast(self, city: str, days: int) -> list[DayReport]: ...
    def past_days(self, city: str, days: int) -> list[DayReport]: ...
    def on_date(self, city: str, target: date) -> list[DayReport]: ...


def route_after_plan(state: AgentState) -> str:
    """Name of the next stage: 'fetch' or 'stop'."""
    return "fetch" if state.get("status") is None else "stop"


class Pipeline:
    def __init__(self, llm: SupportsInvoke, source: WeatherSource, today: Callable[[], date] = date.today):
        self.llm = llm
        self.source = source
        self._today = today

    # stage 1 -------------------------------------------------------------
    def plan(self, state: AgentState) -> AgentState:
        try:
            plan = plan_query(self.llm, state["query"], self._today())
        except PlanError as exc:
            return {"status": "error", "answer": f"I couldn't understand that request ({exc})."}
        if not plan.is_weather:
            return {"plan": plan, "status": "off_topic", "answer": NOT_WEATHER}
        if not plan.cities:
            return {"plan": plan, "status": "needs_city", "answer": NO_CITY}
        return {"plan": plan}

    # stage 2 -------------------------------------------------------------
    def fetch(self, state: AgentState) -> AgentState:
        plan = state["plan"]
        reports: list[DayReport] = []
        failures: list[CityFailure] = []
        for city in plan.cities:
            try:
                reports.extend(self._lookup(city, plan))
            except WeatherAPIError as exc:
                failures.append(CityFailure(city, str(exc)))
        return {"reports": reports, "failures": failures}

    def _lookup(self, city: str, plan: QueryPlan) -> list[DayReport]:
        if plan.mode is Mode.CURRENT:
            return self.source.current(city)
        if plan.mode is Mode.FORECAST:
            return self.source.forecast(city, plan.days)
        if plan.mode is Mode.PAST:
            return self.source.past_days(city, plan.days)
        assert plan.target_date is not None
        return self.source.on_date(city, plan.target_date)

    # stage 3 -------------------------------------------------------------
    def render(self, state: AgentState) -> AgentState:
        reports, failures = state.get("reports", []), state.get("failures", [])
        status = "ok" if reports else "error"
        return {"status": status, "answer": to_markdown(reports, failures)}

    # framework-free runner -------------------------------------------------
    def run(self, query: str) -> AgentState:
        state: AgentState = {"query": query}
        state.update(self.plan(state))
        if route_after_plan(state) == "fetch":
            state.update(self.fetch(state))
            state.update(self.render(state))
        return state


def run_any(pipeline: Pipeline, runner: Any, query: str) -> AgentState:
    """Use a compiled LangGraph if one is supplied, else the plain runner."""
    return runner.invoke({"query": query}) if runner is not None else pipeline.run(query)
