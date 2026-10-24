"""Thin client for the WeatherAPI.com REST endpoints."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import requests

from .models import DayReport

BASE_URL = "https://api.weatherapi.com/v1"


class WeatherAPIError(RuntimeError):
    pass


class WeatherClient:
    def __init__(self, api_key: str, timeout: float = 10.0, session: requests.Session | None = None):
        self._key = api_key
        self._timeout = timeout
        self._http = session or requests.Session()

    # -- transport ---------------------------------------------------------
    def _get(self, endpoint: str, **params: Any) -> dict:
        params = {"key": self._key, **params}
        try:
            resp = self._http.get(f"{BASE_URL}/{endpoint}.json", params=params, timeout=self._timeout)
            payload = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise WeatherAPIError(f"network problem: {exc.__class__.__name__}") from exc
        if "error" in payload:
            raise WeatherAPIError(payload["error"].get("message", "unknown API error"))
        return payload

    # -- parsing -----------------------------------------------------------
    @staticmethod
    def _from_day_block(payload: dict, block: dict) -> DayReport:
        d = block["day"]
        return DayReport(
            city=payload["location"]["name"],
            country=payload["location"]["country"],
            day=date.fromisoformat(block["date"]),
            condition=d["condition"]["text"],
            min_c=d.get("mintemp_c"),
            max_c=d.get("maxtemp_c"),
            avg_c=d.get("avgtemp_c"),
            humidity=d.get("avghumidity"),
            wind_kph=d.get("maxwind_kph"),
            rain_chance=d.get("daily_chance_of_rain"),
        )

    # -- public API --------------------------------------------------------
    def current(self, city: str) -> list[DayReport]:
        data = self._get("current", q=city)
        cur = data["current"]
        return [
            DayReport(
                city=data["location"]["name"],
                country=data["location"]["country"],
                day=date.today(),
                condition=cur["condition"]["text"],
                avg_c=cur.get("temp_c"),
                humidity=cur.get("humidity"),
                wind_kph=cur.get("wind_kph"),
                is_live_reading=True,
            )
        ]

    def forecast(self, city: str, days: int) -> list[DayReport]:
        data = self._get("forecast", q=city, days=days)
        return [self._from_day_block(data, b) for b in data["forecast"]["forecastday"]]

    def history(self, city: str, day: date) -> DayReport:
        data = self._get("history", q=city, dt=day.isoformat())
        return self._from_day_block(data, data["forecast"]["forecastday"][0])

    def past_days(self, city: str, days: int) -> list[DayReport]:
        """Oldest first, ending yesterday."""
        today = date.today()
        return [self.history(city, today - timedelta(days=n)) for n in range(days, 0, -1)]

    def on_date(self, city: str, target: date) -> list[DayReport]:
        today = date.today()
        if target < today:
            return [self.history(city, target)]
        span = (target - today).days + 1
        return [self.forecast(city, span)[-1]]
