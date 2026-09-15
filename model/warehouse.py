"""Fenêtre de sortie d'entrepôt CDG : heuristique v1 honnête."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
DISCLAIMER = "estimation v1, se fiabilise avec l'historique"


def warehouse_out(arrival: datetime, itinerary: str | None = None) -> datetime:
    """Samedi : base + 48 h (week-end). Sinon + 4 h. Escale FIH/PNR : + 2 h."""
    local = arrival.astimezone(PARIS) if arrival.tzinfo else arrival.replace(tzinfo=PARIS)
    extra = timedelta(hours=48) if local.isoweekday() == 6 else timedelta(hours=4)
    if itinerary in {"fih", "pnr"}:
        extra += timedelta(hours=2)
    return arrival + extra
