"""Render reports as Markdown (UI) or plain text (CLI)."""

from __future__ import annotations

from itertools import groupby

from .models import CityFailure, DayReport


def _fmt(value, unit: str = "") -> str:
    return "–" if value is None else f"{value:g}{unit}"


def _icon(condition: str) -> str:
    c = condition.lower()
    table = (
        (("thunder",), "⛈️"),
        (("snow", "sleet", "blizzard", "ice"), "❄️"),
        (("rain", "drizzle", "shower"), "🌧️"),
        (("fog", "mist", "haze"), "🌫️"),
        (("overcast", "cloud"), "☁️"),
        (("sunny", "clear"), "☀️"),
    )
    for words, icon in table:
        if any(w in c for w in words):
            return icon
    return "🌡️"


def to_markdown(reports: list[DayReport], failures: list[CityFailure] | None = None) -> str:
    parts: list[str] = []
    ordered = sorted(reports, key=lambda r: (r.city, r.day))
    for (city, country), rows in groupby(ordered, key=lambda r: (r.city, r.country)):
        rows = list(rows)
        parts.append(f"### {city}, {country}")
        if rows[0].is_live_reading:
            r = rows[0]
            parts.append(
                f"{_icon(r.condition)} **{_fmt(r.avg_c, '°C')}** · {r.condition} · "
                f"humidity {_fmt(r.humidity, '%')} · wind {_fmt(r.wind_kph, ' km/h')}"
            )
            continue
        parts.append("| Date | | Condition | Min | Max | Avg | Rain | Wind |")
        parts.append("|---|---|---|---|---|---|---|---|")
        for r in rows:
            parts.append(
                f"| {r.day:%a %d %b} | {_icon(r.condition)} | {r.condition} | {_fmt(r.min_c, '°')} | "
                f"{_fmt(r.max_c, '°')} | {_fmt(r.avg_c, '°')} | {_fmt(r.rain_chance, '%')} | "
                f"{_fmt(r.wind_kph, ' km/h')} |"
            )
    for f in failures or []:
        parts.append(f"> ⚠️ **{f.city}**: {f.reason}")
    return "\n\n".join(parts)


def to_text(reports: list[DayReport], failures: list[CityFailure] | None = None) -> str:
    lines: list[str] = []
    ordered = sorted(reports, key=lambda r: (r.city, r.day))
    for (city, country), rows in groupby(ordered, key=lambda r: (r.city, r.country)):
        lines.append(f"{city}, {country}")
        for r in rows:
            if r.is_live_reading:
                lines.append(
                    f"  now        {_fmt(r.avg_c, '°C'):>7}  {r.condition}  "
                    f"(humidity {_fmt(r.humidity, '%')}, wind {_fmt(r.wind_kph, ' km/h')})"
                )
            else:
                lines.append(
                    f"  {r.day:%a %d %b}  {_fmt(r.min_c, '°'):>5} / {_fmt(r.max_c, '°'):<5} "
                    f"rain {_fmt(r.rain_chance, '%'):>4}  {r.condition}"
                )
        lines.append("")
    for f in failures or []:
        lines.append(f"! {f.city}: {f.reason}")
    return "\n".join(lines).rstrip()
