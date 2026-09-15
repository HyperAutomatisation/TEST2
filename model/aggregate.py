"""Agrégation des 3 couches : moyenne pondérée, somme des probabilités = 1."""

from __future__ import annotations

from model.classes import CLASSES, normalize


def weighted_mean(
    layer1: dict[str, float],
    layer2: dict[str, float],
    layer3: dict[str, float],
    w1: float,
    w2: float,
    w3: float,
) -> dict[str, float]:
    total = w1 + w2 + w3
    if total <= 0:
        total = 1.0
        w1 = 1.0
    merged = {}
    for key in CLASSES:
        merged[key] = (
            w1 * layer1.get(key, 0.0) + w2 * layer2.get(key, 0.0) + w3 * layer3.get(key, 0.0)
        ) / total
    return normalize(merged)
