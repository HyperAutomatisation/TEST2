"""Score de Brier multiclasse vs prédiction naïve (heure de la grille)."""

from __future__ import annotations

from typing import Any

from corridor.db import connect
from model import MODEL_VERSION
from model.classes import CLASSES, argmax_class, class_from_delay


def brier(probs: dict[str, float], actual_class: str) -> float:
    score = 0.0
    for key in CLASSES:
        observed = 1.0 if key == actual_class else 0.0
        score += (float(probs.get(key, 0.0)) - observed) ** 2
    return score


def naive_probs() -> dict[str, float]:
    """Naïve : l'heure de la grille, donc classe 0-15 min avec proba 1."""
    return {key: (1.0 if key == "p_0_15" else 0.0) for key in CLASSES}


def _pairs_from_rows(rows: list[dict[str, Any]]) -> list[tuple[dict[str, float], int | None]]:
    pairs: list[tuple[dict[str, float], int | None]] = []
    for row in rows:
        probs = {key: float(row[key]) for key in CLASSES}
        pairs.append((probs, row.get("delay_min")))
    return pairs


def compare_to_naive(predictions: list[tuple[dict[str, float], int | None]]) -> dict[str, Any]:
    product: list[float] = []
    naive: list[float] = []
    correct = 0
    always = naive_probs()
    for probs, delay in predictions:
        klass = class_from_delay(delay)
        if not klass:
            continue
        product.append(brier(probs, klass))
        naive.append(brier(always, klass))
        if argmax_class(probs) == klass:
            correct += 1
    if not product:
        return {
            "n": 0,
            "brier": None,
            "brier_naive": None,
            "beats_naive": False,
            "pct_correct": None,
        }
    mean_p = sum(product) / len(product)
    mean_n = sum(naive) / len(naive)
    return {
        "n": len(product),
        "brier": mean_p,
        "brier_naive": mean_n,
        "beats_naive": mean_p < mean_n,
        "pct_correct": 100.0 * correct / len(product),
    }


def fetch_scored_rows(*, model_version: str = MODEL_VERSION) -> list[dict[str, Any]]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT DISTINCT ON (p.date, p.flight_number)
                p.date, p.flight_number, p.model_version,
                p.p_0_15, p.p_15_30, p.p_30_60, p.p_60_120, p.p_120_plus, p.p_cancel,
                f.delay_min
            FROM predictions AS p
            JOIN flight_records AS f
              ON f.date = p.date AND f.flight_number = p.flight_number
            WHERE p.model_version = %s AND f.delay_min IS NOT NULL
            ORDER BY p.date, p.flight_number, f.id DESC
            """,
            (model_version,),
        ).fetchall()


def score_database(*, model_version: str = MODEL_VERSION) -> dict[str, Any]:
    rows = fetch_scored_rows(model_version=model_version)
    result = compare_to_naive(_pairs_from_rows(rows))
    result["model_version"] = model_version
    weekly: dict[str, list[tuple[dict[str, float], int | None]]] = {}
    for row in rows:
        iso = row["date"].isocalendar()
        key = f"{iso.year}-S{iso.week:02d}"
        weekly.setdefault(key, []).append(
            ({k: float(row[k]) for k in CLASSES}, row["delay_min"])
        )
    result["weekly"] = [
        {"semaine": week, **compare_to_naive(pairs)}
        for week, pairs in sorted(weekly.items())
    ]
    return result
