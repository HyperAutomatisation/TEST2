"""Lecture de la grille ref_flights.json pour dater les horaires prévus.

Le mapping jour → vol n'est pas recopié ici : on lit le JSON de saison.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

from corridor.settings import ROOT, TIMEZONE
from backfill.constants import AIRPORT_TIMEZONES

REF_FLIGHTS_PATH = ROOT / "collector" / "data" / "ref_flights.json"
PARIS = ZoneInfo("Europe/Paris")
BZV = ZoneInfo(TIMEZONE)


@lru_cache(maxsize=1)
def ref_flight_rows() -> list[dict[str, Any]]:
    return json.loads(REF_FLIGHTS_PATH.read_text(encoding="utf-8"))


def flights_on(day: date, *, ignore_season: bool = True) -> list[dict[str, Any]]:
    weekday = day.isoweekday()
    rows: list[dict[str, Any]] = []
    for row in ref_flight_rows():
        if weekday not in row["days_of_week"]:
            continue
        if not ignore_season:
            active_from = row.get("active_from")
            active_to = row.get("active_to")
            if active_from and day < date.fromisoformat(active_from):
                continue
            if active_to and day > date.fromisoformat(active_to):
                continue
        rows.append(row)
    return rows


def primary_ref(day: date, flight_number: str) -> dict[str, Any] | None:
    """Une ligne de grille par numéro : départ BZV prioritaire (le PNR est le même avion)."""
    rows = [row for row in flights_on(day) if row["flight_number"] == flight_number]
    if not rows:
        return None
    bzv = [row for row in rows if row.get("departure_airport") == "BZV"]
    return bzv[0] if bzv else rows[0]


def itinerary_from_ref(row: dict[str, Any]) -> str:
    escale = (row.get("escale") or "").lower()
    dep = (row.get("departure_airport") or "").upper()
    if dep == "PNR" or "pointe-noire" in escale or " pnr" in f" {escale}":
        return "pnr"
    if "kinshasa" in escale or "fih" in escale:
        return "fih"
    return "direct"


def itinerary_from_airports(dep_icao: str | None, arr_icao: str | None) -> str | None:
    dep = (dep_icao or "").upper()
    if dep in {"FZAA", "FIH"}:
        return "fih"
    if dep in {"FCPP", "PNR"}:
        return "pnr"
    if dep in {"FCBB", "BZV"}:
        return "direct"
    if arr_icao:
        return "direct"
    return None


def _parse_hhmm(value: str) -> tuple[int, int]:
    hours, minutes = value.split(":")[:2]
    return int(hours), int(minutes)


def scheduled_times(day: date, row: dict[str, Any]) -> tuple[datetime, datetime]:
    dep_h, dep_m = _parse_hhmm(row["sched_dep_local"])
    arr_h, arr_m = _parse_hhmm(row["sched_arr_cdg"])
    dep_tz = ZoneInfo(AIRPORT_TIMEZONES.get(row.get("departure_airport") or "BZV", TIMEZONE))
    sched_dep = datetime(day.year, day.month, day.day, dep_h, dep_m, tzinfo=dep_tz)
    # Tous les retours Congo partent le soir et atterrissent le matin suivant à CDG.
    sched_arr = datetime(day.year, day.month, day.day, arr_h, arr_m, tzinfo=PARIS) + timedelta(
        days=1
    )
    return sched_dep, sched_arr
