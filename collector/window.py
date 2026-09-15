"""Fenêtre de vol 19h00-07h15 (heure du corridor) pour le polling adsb.lol."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from corridor.settings import TIMEZONE

WINDOW_START = time(19, 0)
WINDOW_END = time(7, 15)


def in_flight_window(moment: datetime | None = None) -> bool:
    """Vrai de 19h00 à 07h15 inclus, heure locale du corridor. Traverse minuit."""
    now = moment or datetime.now(ZoneInfo(TIMEZONE))
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo(TIMEZONE))
    else:
        now = now.astimezone(ZoneInfo(TIMEZONE))
    clock = now.timetz().replace(tzinfo=None)
    return clock >= WINDOW_START or clock <= WINDOW_END
