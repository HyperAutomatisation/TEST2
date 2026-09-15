"""Lecture du vol du jour depuis ref_flights. Le mapping jour → vol est en base, jamais ici."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from corridor.db import connect
from corridor.settings import TIMEZONE

WEEKDAY_LABELS = {
    1: "lundi",
    2: "mardi",
    3: "mercredi",
    4: "jeudi",
    5: "vendredi",
    6: "samedi",
    7: "dimanche",
}

_SELECT_JOUR = """
SELECT
    f.id,
    f.flight_number,
    f.airline,
    f.aircraft,
    f.departure_airport,
    f.escale,
    f.days_of_week,
    f.sched_dep_local,
    f.sched_arr_cdg,
    f.active_from,
    f.active_to,
    a.name AS departure_name
FROM ref_flights AS f
LEFT JOIN ref_airports AS a ON a.iata_code = f.departure_airport
WHERE %s = ANY(f.days_of_week)
  AND (f.active_from IS NULL OR f.active_from <= %s)
  AND (f.active_to IS NULL OR f.active_to >= %s)
ORDER BY f.sched_dep_local, f.departure_airport, f.flight_number
"""


def today_corridor() -> date:
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def format_time_iso(value: time | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%H:%M")


def format_heure_fr(value: time | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        hhmm = value[:5]
    else:
        hhmm = value.strftime("%H:%M")
    heures, minutes = hhmm.split(":")
    return f"{heures}h{minutes}"


def format_flight_label(flight_number: str) -> str:
    if flight_number.startswith("AF") and flight_number[2:].isdigit():
        return f"AF {flight_number[2:]}"
    return flight_number


def flights_for_date(day: date) -> list[dict[str, Any]]:
    weekday = day.isoweekday()
    with connect() as conn:
        rows = conn.execute(_SELECT_JOUR, (weekday, day, day)).fetchall()
    return [dict(row) for row in rows]


def serialize_flight(row: dict[str, Any]) -> dict[str, Any]:
    departure_name = row.get("departure_name")
    if not departure_name:
        departure_name = row["departure_airport"]
    return {
        "flight_number": row["flight_number"],
        "flight_label": format_flight_label(row["flight_number"]),
        "airline": row["airline"],
        "aircraft": row["aircraft"],
        "departure_airport": row["departure_airport"],
        "departure_name": departure_name,
        "escale": row["escale"],
        "sched_dep_local": format_time_iso(row["sched_dep_local"]),
        "sched_arr_cdg": format_time_iso(row["sched_arr_cdg"]),
        "dep_display": format_heure_fr(row["sched_dep_local"]),
        "arr_display": format_heure_fr(row["sched_arr_cdg"]),
    }


def payload_vol_du_jour(day: date | None = None) -> dict[str, Any]:
    resolved = day or today_corridor()
    weekday = resolved.isoweekday()
    flights = [serialize_flight(row) for row in flights_for_date(resolved)]
    return {
        "date": resolved.isoformat(),
        "weekday": weekday,
        "weekday_label": WEEKDAY_LABELS[weekday],
        "flights": flights,
    }
