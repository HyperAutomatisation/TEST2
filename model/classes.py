"""Classes de retard et helpers de distribution (heuristiques commentées)."""

from __future__ import annotations

CLASSES = ("p_0_15", "p_15_30", "p_30_60", "p_60_120", "p_120_plus", "p_cancel")
CLASS_LABELS = {
    "p_0_15": "0-15 min",
    "p_15_30": "15-30 min",
    "p_30_60": "30-60 min",
    "p_60_120": "60-120 min",
    "p_120_plus": "plus de 120 min",
    "p_cancel": "annulé",
}


def class_from_delay(delay_min: int | None, *, cancelled: bool = False) -> str | None:
    if cancelled:
        return "p_cancel"
    if delay_min is None:
        return None
    if delay_min < 15:
        return "p_0_15"
    if delay_min < 30:
        return "p_15_30"
    if delay_min < 60:
        return "p_30_60"
    if delay_min < 120:
        return "p_60_120"
    return "p_120_plus"


def uniform() -> dict[str, float]:
    return {key: 1.0 / len(CLASSES) for key in CLASSES}


def normalize(probs: dict[str, float]) -> dict[str, float]:
    total = sum(float(probs.get(key, 0.0)) for key in CLASSES)
    if total <= 0:
        return uniform()
    return {key: float(probs.get(key, 0.0)) / total for key in CLASSES}


def add_laplace(counts: dict[str, int]) -> dict[str, float]:
    """Lissage +1 pour éviter les zéros, puis renormalisation."""
    return normalize({key: counts.get(key, 0) + 1 for key in CLASSES})


def shift_up(probs: dict[str, float], strength: float) -> dict[str, float]:
    """Glisse une fraction de masse vers les classes de retard supérieures."""
    strength = min(1.0, max(0.0, strength))
    keys = [key for key in CLASSES if key != "p_cancel"]
    moved = {key: 0.0 for key in CLASSES}
    moved["p_cancel"] = float(probs.get("p_cancel", 0.0))
    for idx, key in enumerate(keys):
        mass = float(probs.get(key, 0.0))
        stay = mass * (1.0 - strength)
        bump = mass * strength
        moved[key] += stay
        if idx + 1 < len(keys):
            moved[keys[idx + 1]] += bump
        else:
            moved[key] += bump
    return normalize(moved)


def argmax_class(probs: dict[str, float]) -> str:
    return max(CLASSES, key=lambda key: float(probs.get(key, 0.0)))
