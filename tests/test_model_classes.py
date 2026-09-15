from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from model.aggregate import weighted_mean
from model.classes import CLASSES, add_laplace, class_from_delay, normalize, shift_up, uniform
from model.warehouse import DISCLAIMER, warehouse_out


def _sum(probs: dict[str, float]) -> float:
    return sum(probs[key] for key in CLASSES)


def test_normalize_somme_un() -> None:
    probs = normalize({"p_0_15": 2, "p_15_30": 1, "p_30_60": 1})
    assert abs(_sum(probs) - 1.0) < 1e-9
    assert set(probs) == set(CLASSES)


def test_laplace_et_uniforme() -> None:
    uni = uniform()
    assert abs(_sum(uni) - 1.0) < 1e-9
    smoothed = add_laplace({"p_0_15": 3})
    assert abs(_sum(smoothed) - 1.0) < 1e-9
    assert smoothed["p_cancel"] > 0


def test_class_from_delay() -> None:
    assert class_from_delay(0) == "p_0_15"
    assert class_from_delay(15) == "p_15_30"
    assert class_from_delay(45) == "p_30_60"
    assert class_from_delay(90) == "p_60_120"
    assert class_from_delay(180) == "p_120_plus"
    assert class_from_delay(None, cancelled=True) == "p_cancel"


def test_shift_up_conserve_la_somme() -> None:
    base = add_laplace({"p_0_15": 10, "p_15_30": 4})
    moved = shift_up(base, 0.55)
    assert abs(_sum(moved) - 1.0) < 1e-9
    assert moved["p_0_15"] < base["p_0_15"]
    assert moved["p_15_30"] + moved["p_30_60"] > base["p_15_30"] + base["p_30_60"]


def test_weighted_mean_somme_un() -> None:
    l1 = uniform()
    l2 = shift_up(l1, 0.4)
    l3 = shift_up(l1, 0.2)
    merged = weighted_mean(l1, l2, l3, 1.0, 0.55, 0.15)
    assert abs(_sum(merged) - 1.0) < 1e-9


def test_warehouse_samedi_plus_48h() -> None:
    paris = ZoneInfo("Europe/Paris")
    samedi = datetime(2026, 9, 19, 7, 5, tzinfo=paris)
    out = warehouse_out(samedi)
    assert (out - samedi).total_seconds() == 48 * 3600
    vendredi = datetime(2026, 9, 18, 6, 40, tzinfo=paris)
    assert warehouse_out(vendredi).hour == 10
    via_fih = warehouse_out(vendredi, itinerary="fih")
    assert (via_fih - vendredi).total_seconds() == 6 * 3600
    assert "v1" in DISCLAIMER
    assert "historique" in DISCLAIMER
