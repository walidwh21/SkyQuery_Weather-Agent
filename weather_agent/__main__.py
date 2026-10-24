"""Command-line entry point:  python -m weather_agent "forecast for Paris" [--demo]"""

from __future__ import annotations

import argparse
import sys

from . import ConfigError, Settings, build_agent
from .formatter import to_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="weather_agent", description="Ask a weather question in plain English.")
    parser.add_argument("question", nargs="+", help="e.g. 'next 3 days in Tokyo'")
    parser.add_argument("--demo", action="store_true", help="use offline sample data (no API keys needed)")
    args = parser.parse_args(argv)

    try:
        agent = build_agent(Settings.from_env(demo=True if args.demo else None))
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    state = agent.ask(" ".join(args.question))
    if state.get("status") == "ok":
        print(to_text(state["reports"], state.get("failures")))
        return 0
    print(state.get("answer", "Something went wrong."))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
