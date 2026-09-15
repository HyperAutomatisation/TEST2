"""Couche 1 : distribution empirique par vol et jour de semaine."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from corridor.db import connect

from model.classes import CLASSES, add_laplace, class_from_delay, uniform

MIN_OBS_FLIGHT = 40


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    tally: Counter[str] = Counter()
    for row in rows:
        cancelled = row.get("source") == "cancelled"
        klass = class_from_delay(row.get("delay_min"), cancelled=cancelled)
        if klass:
            tally[klass] += 1
    return {key: int(tally.get(key, 0)) for key in CLASSES}


def layer1(flight_number: str, day: date, *, before: date | None = None) -> dict[str, float]:
    """Empirique jusqu'à la veille (pas de fuite du jour prédit). Dégrade si < 40 obs."""
    cutoff = before or day
    with connect() as conn:
        flight_rows = conn.execute(
            """
            SELECT date, delay_min, actual_arr_cdg, actual_dep, source
            FROM flight_records
            WHERE flight_number = %s
              AND date < %s
              AND (delay_min IS NOT NULL OR source = 'cancelled')
            """,
            (flight_number, cutoff),
        ).fetchall()
        if len(flight_rows) < MIN_OBS_FLIGHT:
            flight_rows = conn.execute(
                """
                SELECT date, delay_min, actual_arr_cdg, actual_dep, source
                FROM flight_records
                WHERE date < %s
                  AND (delay_min IS NOT NULL OR source = 'cancelled')
                """,
                (cutoff,),
            ).fetchall()
    if not flight_rows:
        return uniform()
    weekday = day.isoweekday()
    same_weekday = [row for row in flight_rows if row["date"].isoweekday() == weekday]
    chosen = same_weekday if len(same_weekday) >= 8 else flight_rows
    return add_laplace(_counts(chosen))
