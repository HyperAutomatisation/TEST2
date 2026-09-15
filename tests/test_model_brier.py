from __future__ import annotations

from datetime import date

from backfill.opensky import parse, save
from backfill.sample_flights import build_opensky_sample
from model.brier import compare_to_naive, naive_probs, score_database
from model.classes import CLASSES
from model.predict import generate_range


def test_naive_toute_masse_sur_l_heure() -> None:
    probs = naive_probs()
    assert probs["p_0_15"] == 1.0
    assert abs(sum(probs[key] for key in CLASSES) - 1.0) < 1e-9


def test_brier_bat_la_naive_sur_backfill_hors_ligne(clean_backfill) -> None:
    start = date(2025, 10, 1)
    end = date(2026, 9, 20)
    raw = build_opensky_sample(start, end)
    save(parse(raw, source="opensky_sample"))
    generate_range(date(2026, 6, 1), date(2026, 9, 20))
    scored = score_database()
    assert scored["n"] and scored["n"] > 80
    assert scored["brier"] is not None
    assert scored["brier_naive"] is not None
    assert scored["beats_naive"] is True
    assert scored["brier"] < scored["brier_naive"]
    pairs = compare_to_naive(
        [
            ({**naive_probs()}, 5),
            ({**naive_probs()}, 90),
        ]
    )
    assert pairs["beats_naive"] is False
