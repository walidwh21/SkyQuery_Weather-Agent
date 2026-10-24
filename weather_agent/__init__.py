"""Weather Agent: natural-language weather questions answered by an LLM planner + WeatherAPI."""

from .config import ConfigError, Settings
from .factory import Agent, build_agent

__all__ = ["Agent", "ConfigError", "Settings", "build_agent"]
__version__ = "2.0.0"
