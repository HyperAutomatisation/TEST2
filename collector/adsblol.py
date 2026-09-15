"""adsb.lol : position temps réel, décollage (gs > 200 kt), atterrissage CDG."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from corridor.settings import COLLECTORS_USE_SAMPLE, ROOT, TIMEZONE
from zoneinfo import ZoneInfo

from backfill.constants import CALLSIGN_TO_FLIGHT
from backfill.http_client import RateLimitedClient
from backfill.store import insert_adsb_snapshots, upsert_flight_records
from collector.window import in_flight_window

API_CALLSIGN = "https://api.adsb.lol/v2/callsign/{callsign}"
SAMPLE_PATH = ROOT / "collector" / "data" / "samples" / "adsblol_afr754.json"
CDG_LAT, CDG_LON = 49.0097, 2.5479
GS_TAKEOFF_KT = 200
ALT_LANDING_FT = 2500


def _aircraft_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("ac"), list):
        return payload["ac"]
    if isinstance(payload.get("aircraft"), list):
        return payload["aircraft"]
    if isinstance(payload.get("states"), list):
        return payload["states"]
    return [payload] if payload.get("lat") is not None else []


def infer_event(lat: float | None, lon: float | None, alt: float | None, gs: float | None) -> str | None:
    if gs is not None and gs > GS_TAKEOFF_KT:
        if lat is not None and lon is not None and abs(lat - CDG_LAT) < 0.6 and abs(lon - CDG_LON) < 0.8:
            if alt is not None and alt < ALT_LANDING_FT:
                return "landing_cdg"
        return "airborne"
    if (
        lat is not None
        and lon is not None
        and abs(lat - CDG_LAT) < 0.35
        and abs(lon - CDG_LON) < 0.5
        and alt is not None
        and alt < ALT_LANDING_FT
    ):
        return "landing_cdg"
    return None


def parse(payload: dict[str, Any], *, callsign: str | None = None) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for ac in _aircraft_list(payload):
        raw_cs = (ac.get("flight") or ac.get("callsign") or callsign or "").strip().upper()
        compact = raw_cs.replace(" ", "")
        flight_number = CALLSIGN_TO_FLIGHT.get(compact)
        lat = ac.get("lat")
        lon = ac.get("lon")
        alt = ac.get("alt_baro")
        gs = ac.get("gs")
        rows.append(
            {
                "seen_at": now,
                "callsign": compact or raw_cs,
                "flight_number": flight_number,
                "lat": lat,
                "lon": lon,
                "alt_baro": alt,
                "gs": gs,
                "track": ac.get("track"),
                "seen_pos": ac.get("seen_pos"),
                "inferred_event": infer_event(
                    float(lat) if lat is not None else None,
                    float(lon) if lon is not None else None,
                    float(alt) if isinstance(alt, (int, float)) else None,
                    float(gs) if gs is not None else None,
                ),
            }
        )
    return rows


def fetch(callsign: str, *, client: RateLimitedClient | None = None, sample_path: Path | None = None) -> dict[str, Any]:
    if COLLECTORS_USE_SAMPLE or sample_path:
        path = sample_path or SAMPLE_PATH
        return json.loads(path.read_text(encoding="utf-8"))
    http = client or RateLimitedClient(delay_s=0.4, timeout_s=20.0)
    return http.get_json(API_CALLSIGN.format(callsign=callsign), empty_on_404=True) or {}


def save(rows: list[dict[str, Any]]) -> int:
    n = insert_adsb_snapshots(rows)
    flights: list[dict[str, Any]] = []
    day = datetime.now(ZoneInfo(TIMEZONE)).date()
    for row in rows:
        if not row.get("flight_number"):
            continue
        actual_dep = row["seen_at"] if row.get("inferred_event") == "airborne" else None
        actual_arr = row["seen_at"] if row.get("inferred_event") == "landing_cdg" else None
        if actual_dep is None and actual_arr is None:
            continue
        flights.append(
            {
                "date": day,
                "flight_number": row["flight_number"],
                "sched_dep": None,
                "actual_dep": actual_dep,
                "sched_arr_cdg": None,
                "actual_arr_cdg": actual_arr,
                "delay_min": None,
                "aircraft_reg": None,
                "itinerary": None,
                "source": "adsblol",
            }
        )
    if flights:
        upsert_flight_records(flights)
    return n


def run(*, callsigns: list[str] | None = None, payloads: dict[str, dict[str, Any]] | None = None, now: datetime | None = None) -> dict[str, Any]:
    if not in_flight_window(now):
        return {"records": 0, "skipped": "hors_fenetre", "status": "ok"}
    signs = callsigns or list(CALLSIGN_TO_FLIGHT)
    rows: list[dict[str, Any]] = []
    if payloads is not None:
        for cs, payload in payloads.items():
            rows.extend(parse(payload, callsign=cs))
    else:
        for cs in signs:
            rows.extend(parse(fetch(cs), callsign=cs))
    return {"records": save(rows)}
