"""Open-Meteo prévisionnel quotidien (CDG, FIH, BZV, PNR)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from corridor.settings import COLLECTORS_USE_SAMPLE, ROOT, TIMEZONE

from backfill.constants import AIRPORT_COORDS, AIRPORT_TIMEZONES, OPENMETEO_ARCHIVE
from backfill.openmeteo import parse as parse_hourly
from backfill.http_client import RateLimitedClient
from backfill.store import upsert_weather

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SAMPLE_DIR = ROOT / "collector" / "data" / "samples"


def fetch_airport(airport: str, *, client: RateLimitedClient | None = None) -> dict[str, Any]:
    sample = SAMPLE_DIR / f"openmeteo_forecast_{airport.lower()}.json"
    if COLLECTORS_USE_SAMPLE and sample.exists():
        return json.loads(sample.read_text(encoding="utf-8"))
    lat, lon = AIRPORT_COORDS[airport]
    http = client or RateLimitedClient(delay_s=0.3, timeout_s=30.0)
    return http.get_json(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "precipitation,visibility,wind_speed_10m,weather_code",
            "forecast_days": 2,
            "timezone": AIRPORT_TIMEZONES[airport],
            "wind_speed_unit": "kmh",
        },
    )


def parse(payload: dict[str, Any], *, airport: str) -> list[dict[str, Any]]:
    rows = parse_hourly(payload, airport=airport)
    for row in rows:
        row["forecast_bool"] = True
    return rows


def fetch() -> dict[str, dict[str, Any]]:
    return {airport: fetch_airport(airport) for airport in AIRPORT_COORDS}


def save(rows: list[dict[str, Any]]) -> int:
    return upsert_weather(rows)


def run(*, payloads: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    data = payloads if payloads is not None else fetch()
    rows: list[dict[str, Any]] = []
    for airport, payload in data.items():
        rows.extend(parse(payload, airport=airport))
    return {"records": save(rows)}
