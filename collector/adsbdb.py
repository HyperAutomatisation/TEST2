"""adsbdb : route du jour (direct / FIH / PNR) et immatriculation."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from corridor.settings import COLLECTORS_USE_SAMPLE, ROOT, TIMEZONE

from backfill.constants import CALLSIGN_TO_FLIGHT
from backfill.http_client import RateLimitedClient
from backfill.schedule import itinerary_from_airports
from backfill.store import upsert_flight_records, upsert_rotations

API_CALLSIGN = "https://api.adsbdb.com/v0/callsign/{callsign}"
API_AIRCRAFT = "https://api.adsbdb.com/v0/aircraft/{hex}"
SAMPLE_CALLSIGN = ROOT / "collector" / "data" / "samples" / "adsbdb_callsign.json"
SAMPLE_AIRCRAFT = ROOT / "collector" / "data" / "samples" / "adsbdb_aircraft.json"


def _unwrap(payload: dict[str, Any]) -> dict[str, Any]:
    inner = payload.get("response") or payload
    return inner if isinstance(inner, dict) else payload


def itinerary_from_route(origin: str | None, destination: str | None) -> str | None:
    return itinerary_from_airports(origin, destination)


def parse_callsign(payload: dict[str, Any], *, callsign: str | None = None) -> dict[str, Any]:
    body = _unwrap(payload)
    route = body.get("flightroute") or body.get("route") or body
    origin = route.get("origin") or {}
    dest = route.get("destination") or {}
    origin_code = origin.get("icao_code") or origin.get("iata_code") or route.get("origin_icao")
    dest_code = dest.get("icao_code") or dest.get("iata_code") or route.get("destination_icao")
    compact = (callsign or body.get("callsign") or "").replace(" ", "").upper()
    flight_number = CALLSIGN_TO_FLIGHT.get(compact)
    return {
        "callsign": compact,
        "flight_number": flight_number,
        "origin": origin_code,
        "destination": dest_code,
        "itinerary": itinerary_from_route(origin_code, dest_code),
        "airline": (route.get("airline") or {}).get("name"),
    }


def parse_aircraft(payload: dict[str, Any]) -> dict[str, Any]:
    body = _unwrap(payload)
    aircraft = body.get("aircraft") or body
    return {
        "registration": aircraft.get("registration"),
        "type": aircraft.get("type") or aircraft.get("icao_type"),
        "icao24": aircraft.get("mode_s") or aircraft.get("icao24") or aircraft.get("hex"),
    }


def fetch_callsign(callsign: str, *, sample_path: Path | None = None) -> dict[str, Any]:
    if COLLECTORS_USE_SAMPLE or sample_path:
        return json.loads((sample_path or SAMPLE_CALLSIGN).read_text(encoding="utf-8"))
    http = RateLimitedClient(delay_s=0.4, timeout_s=20.0)
    return http.get_json(API_CALLSIGN.format(callsign=callsign), empty_on_404=True) or {}


def fetch_aircraft(modes_hex: str, *, sample_path: Path | None = None) -> dict[str, Any]:
    if COLLECTORS_USE_SAMPLE or sample_path:
        return json.loads((sample_path or SAMPLE_AIRCRAFT).read_text(encoding="utf-8"))
    http = RateLimitedClient(delay_s=0.4, timeout_s=20.0)
    return http.get_json(API_AIRCRAFT.format(hex=modes_hex), empty_on_404=True) or {}


def save(route: dict[str, Any], aircraft: dict[str, Any] | None = None, *, day: date | None = None) -> int:
    resolved = day or datetime.now(ZoneInfo(TIMEZONE)).date()
    n = 0
    if route.get("flight_number"):
        n += upsert_flight_records(
            [
                {
                    "date": resolved,
                    "flight_number": route["flight_number"],
                    "sched_dep": None,
                    "actual_dep": None,
                    "sched_arr_cdg": None,
                    "actual_arr_cdg": None,
                    "delay_min": None,
                    "aircraft_reg": (aircraft or {}).get("registration"),
                    "itinerary": route.get("itinerary"),
                    "source": "adsbdb",
                }
            ]
        )
    if aircraft and aircraft.get("registration"):
        n += upsert_rotations(
            [
                {
                    "date": resolved,
                    "aircraft_reg": aircraft["registration"],
                    "retard_troncon_aller_min": None,
                }
            ]
        )
    return n


def run(*, callsign: str = "AFR754", payloads: dict[str, Any] | None = None) -> dict[str, Any]:
    if payloads:
        route = parse_callsign(payloads.get("callsign") or payloads, callsign=callsign)
        aircraft = parse_aircraft(payloads["aircraft"]) if payloads.get("aircraft") else None
    else:
        route = parse_callsign(fetch_callsign(callsign), callsign=callsign)
        aircraft = None
    saved = save(route, aircraft)
    return {"records": saved, "itinerary": route.get("itinerary")}
