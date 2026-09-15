"""Alerte changement de saison si l'horaire source diverge de ref_flights."""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

logger = logging.getLogger(__name__)

SEASON_THRESHOLD_MIN = 20


def minutes_apart(grid: time, observed: datetime | time) -> int:
    if isinstance(observed, datetime):
        observed_t = observed.timetz().replace(tzinfo=None)
    else:
        observed_t = observed
    grid_m = grid.hour * 60 + grid.minute
    obs_m = observed_t.hour * 60 + observed_t.minute
    delta = abs(grid_m - obs_m)
    return min(delta, 24 * 60 - delta)


def is_season_change(grid: time, observed: datetime | time | None, *, threshold: int = SEASON_THRESHOLD_MIN) -> bool:
    if observed is None:
        return False
    return minutes_apart(grid, observed) >= threshold


def log_season_change(flight_number: str, grid: time, observed: datetime | time, extra: str = "") -> str:
    message = (
        f"changement de saison : {flight_number} prévu {grid.strftime('%H:%M')} "
        f"en grille, observé {observed if not isinstance(observed, datetime) else observed.strftime('%H:%M')}"
    )
    if extra:
        message = f"{message} ({extra})"
    logger.warning(message)
    return message
