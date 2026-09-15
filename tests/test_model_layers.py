from __future__ import annotations

from datetime import date

from collector.nager import parse as parse_nager
from corridor.settings import ROOT
from model.classes import CLASSES, shift_up
from model.layer1 import MIN_OBS_FLIGHT, layer1
from model.layer2 import layer2
from model.layer3 import layer3, mark_ponts
from model.predict import generate_for_date
import json


def test_nager_ponts_jeudi_et_mardi() -> None:
    payload = json.loads(
        (ROOT / "collector/data/samples/nager_fr_2026.json").read_text(encoding="utf-8")
    )
    rows = parse_nager(payload)
    by_date = {row["date"]: row for row in rows}
    assert by_date[date(2026, 1, 1)]["is_pont"] is False
    assert by_date[date(2026, 1, 2)]["is_pont"] is True
    assert by_date[date(2026, 1, 2)]["label"] == "pont"
    assert by_date[date(2026, 5, 15)]["is_pont"] is True
    assert by_date[date(2026, 7, 13)]["is_pont"] is True
    assert date(2026, 7, 14) in by_date


def test_mark_ponts_idempotent() -> None:
    rows = [
        {"date": date(2026, 5, 14), "country": "FR", "label": "Ascension", "is_pont": False}
    ]
    once = mark_ponts(rows)
    twice = mark_ponts(once)
    assert len(once) == len(twice) == 2


def test_layer1_degrade_si_moins_de_40_obs(clean_backfill) -> None:
    conn = clean_backfill
    for i in range(12):
        conn.execute(
            """
            INSERT INTO flight_records (date, flight_number, delay_min, source)
            VALUES (%s, 'AF754', %s, 'test')
            """,
            (date(2026, 6, 1 + i), 40 if i % 2 else 5),
        )
    conn.commit()
    probs = layer1("AF754", date(2026, 9, 15))
    assert abs(sum(probs[key] for key in CLASSES) - 1.0) < 1e-9
    # 12 obs < 40 : on mélange tout le corridor (ici le même vol).
    assert MIN_OBS_FLIGHT == 40


def test_layer2_et_layer3_glissent_la_masse() -> None:
    base = {key: 0.0 for key in CLASSES}
    base["p_0_15"] = 1.0
    l2, f2, w2 = layer2(base, inherited=90, storm=True)
    assert w2 == 0.55 + 0.20
    assert l2["p_0_15"] < 1.0
    assert any("hérité" in text for text in f2)
    assert any("Météo" in text for text in f2)


def test_layer3_ferie(clean_backfill) -> None:
    conn = clean_backfill
    conn.execute(
        """
        INSERT INTO calendar_days (date, country, label, is_pont)
        VALUES ('2026-07-14', 'FR', 'Fête nationale', FALSE)
        """
    )
    conn.execute(
        """
        INSERT INTO dgac_causes (periode, airline, cause, share_pct)
        VALUES ('2026-07', 'TOUS', 'vols_retardes_plus_15min', 40.3)
        """
    )
    conn.commit()
    base = shift_up({key: (1.0 if key == "p_0_15" else 0.0) for key in CLASSES}, 0)
    l3, factors, weight = layer3(base, date(2026, 7, 14))
    assert weight == 0.15 + 0.10
    assert abs(sum(l3[key] for key in CLASSES) - 1.0) < 1e-9
    assert any("Férié" in text for text in factors)
    assert any("DGAC" in text for text in factors)


def test_generate_for_date_somme_un(clean_backfill) -> None:
    result = generate_for_date(date(2026, 9, 15))
    assert result["records"] == 1
    row = clean_backfill.execute(
        """
        SELECT p_0_15, p_15_30, p_30_60, p_60_120, p_120_plus, p_cancel, factors_json
        FROM predictions WHERE date = '2026-09-15' AND flight_number = 'AF754'
        """
    ).fetchone()
    total = sum(float(row[key]) for key in CLASSES)
    assert abs(total - 1.0) < 1e-9
    assert row["factors_json"]
