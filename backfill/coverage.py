"""Critère de fin du chantier 2 : 6 mois d'observations réelles par vol."""

from __future__ import annotations

from datetime import date
from typing import Any

from corridor.db import connect

from backfill.constants import FLIGHT_NUMBERS, SOURCE_OPENSKY, SOURCE_OPENSKY_SAMPLE

MIN_SPAN_DAYS = 180
MIN_OBS = 12


def coverage_rows(
    *,
    sources: tuple[str, ...] = (SOURCE_OPENSKY, SOURCE_OPENSKY_SAMPLE),
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            flight_number,
            COUNT(*) AS n,
            MIN(date) AS dmin,
            MAX(date) AS dmax,
            COUNT(actual_arr_cdg) AS n_arr,
            COUNT(actual_dep) AS n_dep
        FROM flight_records
        WHERE source = ANY(%s)
          AND (actual_arr_cdg IS NOT NULL OR actual_dep IS NOT NULL)
        GROUP BY flight_number
        ORDER BY flight_number
    """
    with connect() as conn:
        return list(conn.execute(sql, (list(sources),)).fetchall())


def evaluate(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data = rows if rows is not None else coverage_rows()
    by_flight = {row["flight_number"]: row for row in data}
    details: list[dict[str, Any]] = []
    ok = True
    for number in FLIGHT_NUMBERS:
        row = by_flight.get(number)
        if not row:
            details.append(
                {
                    "flight_number": number,
                    "ok": False,
                    "n": 0,
                    "span_days": 0,
                    "reason": "aucune observation",
                }
            )
            ok = False
            continue
        dmin: date = row["dmin"]
        dmax: date = row["dmax"]
        span = (dmax - dmin).days
        n = int(row["n"])
        flight_ok = span >= MIN_SPAN_DAYS and n >= MIN_OBS
        if not flight_ok:
            ok = False
        details.append(
            {
                "flight_number": number,
                "ok": flight_ok,
                "n": n,
                "n_arr": int(row["n_arr"]),
                "n_dep": int(row["n_dep"]),
                "dmin": dmin.isoformat(),
                "dmax": dmax.isoformat(),
                "span_days": span,
            }
        )
    return {
        "ok": ok,
        "min_span_days": MIN_SPAN_DAYS,
        "min_obs": MIN_OBS,
        "flights": details,
    }
