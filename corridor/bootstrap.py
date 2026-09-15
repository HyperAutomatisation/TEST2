"""Création du schéma, saisie de la grille, import OurAirports."""

from __future__ import annotations

import json
from pathlib import Path

from corridor.db import connect
from corridor.settings import ROOT

SCHEMA_PATH = ROOT / "sql" / "schema.sql"
REF_FLIGHTS_PATH = ROOT / "collector" / "data" / "ref_flights.json"


def _statements(script: str) -> list[str]:
    parts: list[str] = []
    for chunk in script.split(";"):
        stmt = chunk.strip()
        if not stmt:
            continue
        parts.append(stmt)
    return parts


def apply_schema() -> None:
    script = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect() as conn:
        with conn.cursor() as cur:
            for stmt in _statements(script):
                cur.execute(stmt)
        conn.commit()


def seed_ref_flights(*, replace: bool = False) -> int:
    rows = json.loads(REF_FLIGHTS_PATH.read_text(encoding="utf-8"))
    with connect() as conn:
        with conn.cursor() as cur:
            if not replace:
                cur.execute("SELECT COUNT(*) AS n FROM ref_flights")
                if cur.fetchone()["n"]:
                    return 0
            else:
                cur.execute("TRUNCATE ref_flights RESTART IDENTITY")
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO ref_flights (
                        flight_number, airline, aircraft, departure_airport,
                        escale, days_of_week, sched_dep_local, sched_arr_cdg,
                        active_from, active_to
                    )
                    VALUES (
                        %(flight_number)s, %(airline)s, %(aircraft)s,
                        %(departure_airport)s, %(escale)s, %(days_of_week)s,
                        %(sched_dep_local)s, %(sched_arr_cdg)s,
                        %(active_from)s, %(active_to)s
                    )
                    """,
                    row,
                )
        conn.commit()
    return len(rows)


def bootstrap(*, replace: bool = False) -> None:
    from collector.ourairports import import_airports

    apply_schema()
    seed_ref_flights(replace=replace)
    import_airports()
