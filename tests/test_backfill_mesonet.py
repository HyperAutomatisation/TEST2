from __future__ import annotations

from datetime import date

from backfill.constants import SAMPLES_DIR
from backfill.mesonet import parse


def test_parse_mesonet_unites() -> None:
    text = (SAMPLES_DIR / "mesonet_lfpg.csv").read_text(encoding="utf-8")
    rows = parse(text, airport="CDG")
    assert rows
    assert rows[0]["date"] == date(2026, 9, 1)
    assert rows[0]["vis_km"] is not None
    assert rows[0]["vis_km"] > 1
    assert rows[0]["wind_kmh"] is not None
    assert rows[0]["precip_mm"] is None
    assert rows[0]["risk_storm"] is False
