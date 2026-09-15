from __future__ import annotations

import json
from datetime import date

from backfill.constants import SAMPLES_DIR, SOURCE_OPENSKY
from backfill.opensky import normalize_callsign, parse, save
from backfill.sample_flights import build_opensky_sample


def test_callsign_padding() -> None:
    assert normalize_callsign("AFR754  ") == "AF754"
    assert normalize_callsign("afr736") == "AF736"
    assert normalize_callsign("AF722") == "AF722"
    assert normalize_callsign("BAW123") is None


def test_parse_echantillon_fige() -> None:
    raw = json.loads((SAMPLES_DIR / "opensky_flights.json").read_text(encoding="utf-8"))
    rows = parse(raw, source=SOURCE_OPENSKY)
    by_flight = {row["flight_number"]: row for row in rows}
    assert set(by_flight) == {"AF754", "AF722"}
    af754 = by_flight["AF754"]
    assert af754["date"] == date(2026, 9, 15)
    assert af754["itinerary"] == "fih"
    assert af754["delay_min"] == 37
    assert af754["actual_arr_cdg"] is not None
    assert af754["actual_dep"] is not None
    assert by_flight["AF722"]["itinerary"] == "direct"
    assert by_flight["AF722"]["delay_min"] == 8


def test_save_et_upsert(clean_backfill) -> None:
    raw = json.loads((SAMPLES_DIR / "opensky_flights.json").read_text(encoding="utf-8"))
    rows = parse(raw)
    assert save(rows) == 2
    assert save(rows) == 2
    n = clean_backfill.execute("SELECT COUNT(*) AS n FROM flight_records").fetchone()["n"]
    assert n == 2


def test_generateur_couvre_quatre_vols() -> None:
    raw = build_opensky_sample(date(2026, 3, 30), date(2026, 4, 12))
    parsed = parse(raw, source="opensky_sample")
    numbers = {row["flight_number"] for row in parsed}
    assert numbers == {"AF736", "AF754", "AF722", "AF940"}
    # Un enregistrement par (date, numéro), pas le doublon PNR du dimanche.
    keys = [(row["date"], row["flight_number"]) for row in parsed]
    assert len(keys) == len(set(keys))
