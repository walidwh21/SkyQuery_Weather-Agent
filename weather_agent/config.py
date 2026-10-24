"""Runtime configuration, read from environment variables (or a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Raised when a required setting is missing."""


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional
        return
    load_dotenv()


@dataclass(frozen=True)
class Settings:
    google_api_key: str | None
    weather_api_key: str | None
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.0
    request_timeout: float = 10.0
    max_forecast_days: int = 14
    max_past_days: int = 14
    demo: bool = False

    @classmethod
    def from_env(cls, demo: bool | None = None) -> "Settings":
        _load_dotenv()
        if demo is None:
            demo = os.getenv("WEATHER_AGENT_DEMO", "").lower() in {"1", "true", "yes"}
        return cls(
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            weather_api_key=os.getenv("WEATHER_API_KEY"),
            model_name=os.getenv("WEATHER_AGENT_MODEL", cls.model_name),
            demo=demo,
        )

    def require_live_keys(self) -> None:
        """Fail early with a readable message instead of prompting interactively."""
        missing = [
            name
            for name, value in (
                ("GOOGLE_API_KEY", self.google_api_key),
                ("WEATHER_API_KEY", self.weather_api_key),
            )
            if not value
        ]
        if missing:
            raise ConfigError(
                "Missing environment variable(s): "
                + ", ".join(missing)
                + ". Copy .env.example to .env and fill them in, "
                "or run in demo mode (WEATHER_AGENT_DEMO=1)."
            )
