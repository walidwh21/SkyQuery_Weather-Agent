"""Plain data containers shared by every stage of the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Mode(str, Enum):
    CURRENT = "current"
    PAST = "past"
    FORECAST = "forecast"
    ON_DATE = "on_date"


@dataclass
class QueryPlan:
    """Structured interpretation of a free-text question."""

    is_weather: bool
    cities: list[str] = field(default_factory=list)
    mode: Mode = Mode.CURRENT
    days: int = 1
    target_date: date | None = None


@dataclass
class DayReport:
    """One city on one day. Optional fields are None when the API omits them."""

    city: str
    country: str
    day: date
    condition: str
    min_c: float | None = None
    max_c: float | None = None
    avg_c: float | None = None
    humidity: float | None = None
    wind_kph: float | None = None
    rain_chance: int | None = None
    is_live_reading: bool = False  # True for "right now" observations


@dataclass
class CityFailure:
    city: str
    reason: str
