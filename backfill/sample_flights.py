"""Échantillon hors ligne : OpenSky-shaped sur 12 mois, à partir de la grille JSON."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta, timezone
from typing import Any

from backfill.constants import CALLSIGN_TO_FLIGHT
from backfill.schedule import flights_on, itinerary_from_ref, scheduled_times

FLIGHT_TO_CALLSIGN = {flight: callsign for callsign, flight in CALLSIGN_TO_FLIGHT.items()}


def sample_delay_min(day: date, flight_number: str) -> int:
    digest = hashlib.sha256(f"{day.isoformat()}:{flight_number}".encode()).digest()
    bucket = digest[0] % 100
    if bucket < 45:
        return int(digest[1] % 16)
    if bucket < 70:
        return 15 + int(digest[1] % 16)
    if bucket < 88:
        return 30 + int(digest[1] % 31)
    if bucket < 97:
        return 60 + int(digest[1] % 61)
    return 120 + int(digest[1] % 90)


def _icao24(flight_number: str) -> str:
    return hashlib.sha256(flight_number.encode()).hexdigest()[:6]


def build_opensky_sample(start: date, end: date) -> list[dict[str, Any]]:
    """Objets au format API OpenSky (arrivée CDG + départ BZV) pour tests et --offline."""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[date, str]] = set()
    cursor = start
    while cursor <= end:
        for ref in flights_on(cursor, ignore_season=True):
            key = (cursor, ref["flight_number"])
            if key in seen:
                continue
            seen.add(key)
            sched_dep, sched_arr = scheduled_times(cursor, ref)
            delay = sample_delay_min(cursor, ref["flight_number"])
            actual_arr = sched_arr + timedelta(minutes=delay)
            actual_dep = sched_dep + timedelta(minutes=max(0, delay - 12))
            callsign = FLIGHT_TO_CALLSIGN[ref["flight_number"]].ljust(8)
            icao24 = _icao24(ref["flight_number"])
            itinerary = itinerary_from_ref(ref)
            if itinerary == "fih":
                dep_airport = "FZAA"
            elif itinerary == "pnr":
                dep_airport = "FCPP"
            else:
                dep_airport = "FCBB"
            rows.append(
                {
                    "icao24": icao24,
                    "firstSeen": int(actual_dep.astimezone(timezone.utc).timestamp()),
                    "estDepartureAirport": dep_airport,
                    "lastSeen": int(actual_arr.astimezone(timezone.utc).timestamp()),
                    "estArrivalAirport": "LFPG",
                    "callsign": callsign,
                    "_kind": "arrival",
                }
            )
            rows.append(
                {
                    "icao24": icao24,
                    "firstSeen": int(actual_dep.astimezone(timezone.utc).timestamp()),
                    "estDepartureAirport": "FCBB",
                    "lastSeen": int((actual_dep + timedelta(hours=1)).astimezone(timezone.utc).timestamp()),
                    "estArrivalAirport": dep_airport if dep_airport != "FCBB" else "LFPG",
                    "callsign": callsign,
                    "_kind": "departure",
                }
            )
        cursor += timedelta(days=1)
    return rows
