from datetime import date
from types import SimpleNamespace

import pytest

from weather_agent.client import WeatherAPIError, WeatherClient
from weather_agent.demo import KeywordPlanner, SampleSource
from weather_agent.formatter import to_markdown, to_text
from weather_agent.models import Mode
from weather_agent.pipeline import NO_CITY, NOT_WEATHER, Pipeline
from weather_agent.planner import PlanError, parse_plan

TODAY = date(2026, 10, 24)


class StubLLM:
    def __init__(self, reply):
        self.reply = reply

    def invoke(self, prompt):
        return SimpleNamespace(content=self.reply)


# ---- planner ---------------------------------------------------------------
def test_parse_plan_handles_code_fences_and_dedupes_cities():
    raw = '```json\n{"is_weather": true, "cities": ["paris", "Paris", "tokyo"], "mode": "forecast", "days": 4}\n```'
    plan = parse_plan(raw, TODAY)
    assert plan.cities == ["Paris", "Tokyo"]
    assert plan.mode is Mode.FORECAST and plan.days == 4


def test_parse_plan_clamps_days_and_defaults_bad_mode():
    plan = parse_plan('{"is_weather": true, "cities": ["Rome"], "mode": "nonsense", "days": 99}', TODAY)
    assert plan.mode is Mode.CURRENT and plan.days == 1  # current always means 1


def test_parse_plan_clamps_forecast_days():
    plan = parse_plan('{"is_weather": true, "cities": ["Rome"], "mode": "forecast", "days": 99}', TODAY)
    assert plan.days == 14


def test_parse_plan_on_date_today_becomes_current_and_bad_date_falls_back():
    p1 = parse_plan('{"is_weather": true, "cities": ["Rome"], "mode": "on_date", "date": "2026-10-24"}', TODAY)
    p2 = parse_plan('{"is_weather": true, "cities": ["Rome"], "mode": "on_date", "date": "soon"}', TODAY)
    assert p1.mode is Mode.CURRENT and p2.mode is Mode.CURRENT


def test_parse_plan_rejects_garbage():
    with pytest.raises(PlanError):
        parse_plan("sorry, I can't do that", TODAY)


def test_off_topic():
    assert parse_plan('{"is_weather": false}', TODAY).is_weather is False


# ---- pipeline --------------------------------------------------------------
def make_pipeline(llm=None):
    return Pipeline(llm or KeywordPlanner(), SampleSource(), today=lambda: TODAY)


def test_pipeline_off_topic():
    state = make_pipeline().run("what is the capital of France")
    assert state["status"] == "off_topic" and state["answer"] == NOT_WEATHER


def test_pipeline_needs_city():
    state = make_pipeline().run("what's the weather like")
    assert state["status"] == "needs_city" and state["answer"] == NO_CITY


def test_pipeline_forecast_multi_city():
    state = make_pipeline().run("forecast for Paris and Tokyo for the next 3 days")
    assert state["status"] == "ok"
    assert len(state["reports"]) == 6
    assert "### Paris, France" in state["answer"] and "### Tokyo, Japan" in state["answer"]


def test_pipeline_partial_failure_is_reported_not_raised():
    llm = StubLLM('{"is_weather": true, "cities": ["Paris", "Atlantis"], "mode": "current"}')
    state = make_pipeline(llm).run("weather")
    assert state["status"] == "ok"
    assert [f.city for f in state["failures"]] == ["Atlantis"]
    assert "Atlantis" in state["answer"]


def test_pipeline_all_cities_fail_is_error():
    llm = StubLLM('{"is_weather": true, "cities": ["Atlantis"], "mode": "current"}')
    assert make_pipeline(llm).run("weather")["status"] == "error"


def test_pipeline_invalid_model_output():
    state = make_pipeline(StubLLM("¯\\_(ツ)_/¯")).run("weather in Paris")
    assert state["status"] == "error"


# ---- client (HTTP mocked) ---------------------------------------------------
class FakeSession:
    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def get(self, url, params, timeout):
        self.calls.append((url, params))
        return SimpleNamespace(json=lambda: self.payload)


FORECAST_PAYLOAD = {
    "location": {"name": "Paris", "country": "France"},
    "forecast": {
        "forecastday": [
            {
                "date": f"2026-10-2{n}",
                "day": {
                    "mintemp_c": 9.0,
                    "maxtemp_c": 17.5,
                    "avgtemp_c": 13.1,
                    "maxwind_kph": 20.2,
                    "avghumidity": 70,
                    "daily_chance_of_rain": 40,
                    "condition": {"text": "Light rain"},
                },
            }
            for n in (4, 5, 6)
        ]
    },
}


def test_client_forecast_parses_and_sends_params():
    session = FakeSession(FORECAST_PAYLOAD)
    reports = WeatherClient("k", session=session).forecast("Paris", 3)
    assert [r.day.day for r in reports] == [24, 25, 26]
    assert reports[0].rain_chance == 40 and reports[0].condition == "Light rain"
    url, params = session.calls[0]
    assert url.endswith("/forecast.json") and params["days"] == 3 and params["q"] == "Paris"


def test_client_api_error_is_wrapped():
    session = FakeSession({"error": {"code": 1006, "message": "No matching location found."}})
    with pytest.raises(WeatherAPIError, match="No matching location"):
        WeatherClient("k", session=session).current("Nowhere")


def test_client_current_is_live_reading():
    payload = {
        "location": {"name": "Paris", "country": "France"},
        "current": {"temp_c": 14.0, "humidity": 80, "wind_kph": 11.0, "condition": {"text": "Overcast"}},
    }
    (r,) = WeatherClient("k", session=FakeSession(payload)).current("Paris")
    assert r.is_live_reading and r.avg_c == 14.0


# ---- formatter ---------------------------------------------------------------
def test_formatters_handle_missing_values():
    (r,) = SampleSource().on_date("Oslo", TODAY)
    r.min_c = r.max_c = r.rain_chance = None
    assert "–" in to_markdown([r]) and "–" in to_text([r])
