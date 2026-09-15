from __future__ import annotations

import json
from datetime import date, time

from collector.aviationstack import parse
from collector.season import is_season_change
from corridor.settings import ROOT


def test_parse_aviationstack_retard() -> None:
    payload = json.loads(
        (ROOT / "collector/data/samples/aviationstack_af754.json").read_text(encoding="utf-8")
    )
    rows, alerts = parse(payload, day=date(2026, 9, 15))
    assert len(rows) == 1
    row = rows[0]
    assert row["flight_number"] == "AF754"
    assert row["delay_min"] == 37
    assert row["aircraft_reg"] == "F-HRBA"
    assert row["itinerary"] == "fih"
    assert alerts == []


def test_alerte_changement_de_saison() -> None:
    payload = json.loads(
        (ROOT / "collector/data/samples/aviationstack_season_shift.json").read_text(encoding="utf-8")
    )
    rows, alerts = parse(payload, day=date(2026, 9, 15))
    assert rows[0]["flight_number"] == "AF754"
    assert alerts
    assert "changement de saison" in alerts[0]
    assert is_season_change(time(19, 5), time(22, 5)) is True
    assert is_season_change(time(19, 5), time(19, 10)) is False
