"""Aviation Weather Center : METAR et TAF des 4 aéroports du corridor."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from corridor.settings import COLLECTORS_USE_SAMPLE, ROOT, TIMEZONE

from backfill.constants import AIRPORT_ICAO_TO_IATA
from backfill.http_client import RateLimitedClient
from backfill.store import upsert_weather

METAR_URL = "https://aviationweather.gov/api/data/metar"
TAF_URL = "https://aviationweather.gov/api/data/taf"
SAMPLE_METAR = ROOT / "collector" / "data" / "samples" / "awc_metar.json"
SAMPLE_TAF = ROOT / "collector" / "data" / "samples" / "awc_taf.json"
ICAOS = "LFPG,FZAA,FCBB,FCPP"
VIS_RE = re.compile(r"\b(\d{4})\b")
WIND_RE = re.compile(r"\b(\d{3}|VRB)(\d{2,3})KT\b")


def _vis_km(raw: str, visib: Any) -> float | None:
    if isinstance(visib, (int, float)):
        # AWC visib often in statute miles.
        return round(float(visib) * 1.60934, 3)
    if isinstance(visib, str):
        if visib.endswith("+"):
            return 10.0
        try:
            return round(float(visib.replace(",", ".")) * 1.60934, 3)
        except ValueError:
            pass
    match = VIS_RE.search(raw or "")
    if match:
        meters = int(match.group(1))
        return round(meters / 1000.0, 3)
    return None


def _wind_kmh(raw: str, wspd: Any) -> float | None:
    if isinstance(wspd, (int, float)):
        return round(float(wspd) * 1.852, 2)
    match = WIND_RE.search(raw or "")
    if match:
        return round(int(match.group(2)) * 1.852, 2)
    return None


def parse_metar(payload: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    items = payload if isinstance(payload, list) else payload.get("data") or [payload]
    rows: list[dict[str, Any]] = []
    for item in items:
        icao = (item.get("icaoId") or item.get("icao") or "").upper()
        airport = AIRPORT_ICAO_TO_IATA.get(icao)
        if not airport:
            continue
        raw = item.get("rawOb") or item.get("raw") or ""
        vis = _vis_km(raw, item.get("visib"))
        wind = _wind_kmh(raw, item.get("wspd"))
        wx = (item.get("wxString") or raw or "").upper()
        storm = "TS" in wx
        report_time = item.get("reportTime") or item.get("obsTime")
        day = date.fromisoformat(str(report_time)[:10]) if report_time else datetime.now(ZoneInfo(TIMEZONE)).date()
        rows.append(
            {
                "date": day,
                "airport": airport,
                "forecast_bool": False,
                "precip_mm": None,
                "vis_km": vis,
                "wind_kmh": wind,
                "risk_storm": storm,
            }
        )
    return rows


def parse_taf(payload: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    items = payload if isinstance(payload, list) else payload.get("data") or [payload]
    flags: list[dict[str, Any]] = []
    for item in items:
        raw = (item.get("rawTAF") or item.get("raw") or "").upper()
        icao = (item.get("icaoId") or item.get("icao") or "").upper()
        airport = AIRPORT_ICAO_TO_IATA.get(icao)
        if not airport:
            continue
        flags.append({"airport": airport, "risk_storm": "TS" in raw, "fog": " FG " in f" {raw} "})
    return flags


def fetch_metar(*, sample_path: Path | None = None) -> Any:
    if COLLECTORS_USE_SAMPLE or sample_path:
        return json.loads((sample_path or SAMPLE_METAR).read_text(encoding="utf-8"))
    http = RateLimitedClient(delay_s=0.3, timeout_s=25.0)
    return http.get_json(METAR_URL, params={"ids": ICAOS, "format": "json", "hours": 24})


def fetch_taf(*, sample_path: Path | None = None) -> Any:
    if COLLECTORS_USE_SAMPLE or sample_path:
        return json.loads((sample_path or SAMPLE_TAF).read_text(encoding="utf-8"))
    http = RateLimitedClient(delay_s=0.3, timeout_s=25.0)
    return http.get_json(TAF_URL, params={"ids": ICAOS, "format": "json"})


def save(rows: list[dict[str, Any]]) -> int:
    return upsert_weather(rows)


def run(*, metar_payload: Any | None = None, taf_payload: Any | None = None) -> dict[str, Any]:
    metar = metar_payload if metar_payload is not None else fetch_metar()
    taf = taf_payload if taf_payload is not None else fetch_taf()
    rows = parse_metar(metar)
    taf_flags = {item["airport"]: item for item in parse_taf(taf)}
    for row in rows:
        extra = taf_flags.get(row["airport"])
        if extra and extra.get("risk_storm"):
            row["risk_storm"] = True
    return {"records": save(rows), "taf": len(taf_flags)}
