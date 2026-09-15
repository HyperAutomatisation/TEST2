from __future__ import annotations

from datetime import time
from pathlib import Path

from tests.expected import ATTENDU_PAR_JOUR, NUMEROS_VOL


def _hhmm(value: time) -> str:
    return value.strftime("%H:%M")


def test_grille_contient_les_quatre_numeros(db_conn) -> None:
    rows = db_conn.execute("SELECT DISTINCT flight_number FROM ref_flights").fetchall()
    numbers = {row["flight_number"] for row in rows}
    assert numbers == NUMEROS_VOL


def test_grille_couvre_la_semaine(db_conn) -> None:
    for weekday, attendu in ATTENDU_PAR_JOUR.items():
        rows = db_conn.execute(
            """
            SELECT flight_number, departure_airport, sched_dep_local, sched_arr_cdg
            FROM ref_flights
            WHERE %s = ANY(days_of_week)
            ORDER BY sched_dep_local, departure_airport, flight_number
            """,
            (weekday,),
        ).fetchall()
        obtenu = [
            (
                row["flight_number"],
                row["departure_airport"],
                _hhmm(row["sched_dep_local"]),
                _hhmm(row["sched_arr_cdg"]),
            )
            for row in rows
        ]
        assert obtenu == attendu, f"jour ISO {weekday}"


def test_mapping_jour_vol_absent_du_code_applicatif() -> None:
    roots = [Path("corridor"), Path("web")]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for numero in NUMEROS_VOL:
                assert numero not in text, f"{numero} ne doit pas être en dur dans {path}"


def test_airports_corridor_en_base(db_conn) -> None:
    rows = db_conn.execute(
        "SELECT ident, iata_code, timezone FROM ref_airports ORDER BY ident"
    ).fetchall()
    by_ident = {row["ident"]: row for row in rows}
    assert set(by_ident) == {"FCBB", "FCPP", "FZAA", "LFPG"}
    assert by_ident["LFPG"]["iata_code"] == "CDG"
    assert by_ident["FZAA"]["iata_code"] == "FIH"
    assert by_ident["FCBB"]["iata_code"] == "BZV"
    assert by_ident["FCPP"]["iata_code"] == "PNR"
    assert by_ident["LFPG"]["timezone"] == "Europe/Paris"
