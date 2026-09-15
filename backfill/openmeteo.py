"""Archive Open-Meteo pour CDG, FIH, BZV, PNR. Visibilité complétée via historical-forecast."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from typing import Any

from backfill.constants import (
    AIRPORT_COORDS,
    AIRPORT_TIMEZONES,
    OPENMETEO_ARCHIVE,
    OPENMETEO_HISTORICAL_FORECAST,
    STORM_WEATHER_CODES,
)
from backfill.http_client import RateLimitedClient
from backfill.store import upsert_weather

logger = logging.getLogger(__name__)

HOURLY = "precipitation,visibility,wind_speed_10m,weather_code"


def _to_vis_km(value: float | None) -> float | None:
    if value is None:
        return None
    if value > 50:
        return round(value / 1000.0, 3)
    return float(value)


def parse(payload: dict[str, Any], *, airport: str) -> list[dict[str, Any]]:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    precip = hourly.get("precipitation") or [None] * len(times)
    vis = hourly.get("visibility") or [None] * len(times)
    wind = hourly.get("wind_speed_10m") or [None] * len(times)
    codes = hourly.get("weather_code") or [None] * len(times)
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"precip": 0.0, "vis": [], "wind": [], "storm": False, "n": 0}
    )
    for idx, stamp in enumerate(times):
        day = str(stamp)[:10]
        bucket = buckets[day]
        bucket["n"] += 1
        rain = precip[idx] if idx < len(precip) else None
        if rain is not None:
            bucket["precip"] += float(rain)
        vis_km = _to_vis_km(vis[idx] if idx < len(vis) else None)
        if vis_km is not None:
            bucket["vis"].append(vis_km)
        wspeed = wind[idx] if idx < len(wind) else None
        if wspeed is not None:
            bucket["wind"].append(float(wspeed))
        code = codes[idx] if idx < len(codes) else None
        if code is not None and int(code) in STORM_WEATHER_CODES:
            bucket["storm"] = True
    rows: list[dict[str, Any]] = []
    for day in sorted(buckets):
        bucket = buckets[day]
        rows.append(
            {
                "date": date.fromisoformat(day),
                "airport": airport,
                "forecast_bool": False,
                "precip_mm": round(bucket["precip"], 2),
                "vis_km": round(min(bucket["vis"]), 3) if bucket["vis"] else None,
                "wind_kmh": round(max(bucket["wind"]), 2) if bucket["wind"] else None,
                "risk_storm": bool(bucket["storm"]),
            }
        )
    return rows


def _merge_visibility(archive: dict[str, Any], extra: dict[str, Any] | None) -> dict[str, Any]:
    if not extra:
        return archive
    base_vis = (archive.get("hourly") or {}).get("visibility") or []
    extra_vis = (extra.get("hourly") or {}).get("visibility") or []
    extra_times = (extra.get("hourly") or {}).get("time") or []
    by_time = {stamp: extra_vis[idx] if idx < len(extra_vis) else None for idx, stamp in enumerate(extra_times)}
    times = (archive.get("hourly") or {}).get("time") or []
    merged = []
    for idx, stamp in enumerate(times):
        current = base_vis[idx] if idx < len(base_vis) else None
        merged.append(current if current is not None else by_time.get(stamp))
    archive.setdefault("hourly", {})["visibility"] = merged
    return archive


def fetch_airport(
    airport: str,
    start: date,
    end: date,
    *,
    client: RateLimitedClient | None = None,
) -> dict[str, Any]:
    lat, lon = AIRPORT_COORDS[airport]
    tz = AIRPORT_TIMEZONES[airport]
    http = client or RateLimitedClient(delay_s=0.4, timeout_s=60.0)
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": HOURLY,
        "timezone": tz,
        "wind_speed_unit": "kmh",
    }
    archive = http.get_json(OPENMETEO_ARCHIVE, params=params)
    extra = None
    vis = (archive.get("hourly") or {}).get("visibility") or []
    if not vis or all(value is None for value in vis):
        logger.info("Open-Meteo visibilité archive vide pour %s, historique prévisionnel", airport)
        extra = http.get_json(OPENMETEO_HISTORICAL_FORECAST, params=params)
    return _merge_visibility(archive, extra)


def fetch(start: date, end: date, *, client: RateLimitedClient | None = None) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for airport in AIRPORT_COORDS:
        payloads[airport] = fetch_airport(airport, start, end, client=client)
    return payloads


def save(rows: list[dict[str, Any]]) -> int:
    return upsert_weather(rows)


def run(
    *,
    start: date,
    end: date,
    payloads: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    data = payloads if payloads is not None else fetch(start, end)
    rows: list[dict[str, Any]] = []
    for airport, payload in data.items():
        rows.extend(parse(payload, airport=airport))
    saved = save(rows)
    return {"records": saved, "airports": sorted(data)}
