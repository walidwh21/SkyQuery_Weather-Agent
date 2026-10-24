"""Assemble a ready-to-use agent from Settings."""

from __future__ import annotations

from .config import Settings
from .pipeline import AgentState, Pipeline, run_any


class Agent:
    def __init__(self, pipeline: Pipeline, runner=None):
        self._pipeline = pipeline
        self._runner = runner  # compiled LangGraph, or None for the plain runner

    def ask(self, query: str) -> AgentState:
        return run_any(self._pipeline, self._runner, query)


def build_agent(settings: Settings | None = None) -> Agent:
    settings = settings or Settings.from_env()

    if settings.demo:
        from .demo import KeywordPlanner, SampleSource

        return Agent(Pipeline(KeywordPlanner(), SampleSource()))

    settings.require_live_keys()
    from langchain_google_genai import ChatGoogleGenerativeAI

    from .client import WeatherClient
    from .graph import build_graph

    llm = ChatGoogleGenerativeAI(
        model=settings.model_name,
        google_api_key=settings.google_api_key,
        temperature=settings.temperature,
    )
    pipeline = Pipeline(llm, WeatherClient(settings.weather_api_key, settings.request_timeout))
    return Agent(pipeline, runner=build_graph(pipeline))
