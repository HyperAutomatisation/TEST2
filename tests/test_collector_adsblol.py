from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from collector.adsblol import infer_event, parse, run
from corridor.settings import ROOT


def test_decollage_gs() -> None:
    assert infer_event(-4.2, 15.1, 32000, 450) == "airborne"
    assert infer_event(49.012, 2.55, 900, 140) == "landing_cdg"


def test_parse_airborne() -> None:
    payload = json.loads(
        (ROOT / "collector/data/samples/adsblol_afr754.json").read_text(encoding="utf-8")
    )
    rows = parse(payload, callsign="AFR754")
    assert rows[0]["flight_number"] == "AF754"
    assert rows[0]["inferred_event"] == "airborne"


def test_parse_atterrissage_cdg() -> None:
    payload = json.loads(
        (ROOT / "collector/data/samples/adsblol_landing_cdg.json").read_text(encoding="utf-8")
    )
    rows = parse(payload)
    assert rows[0]["inferred_event"] == "landing_cdg"


def test_poll_hors_fenetre() -> None:
    now = datetime(2026, 9, 15, 12, 0, tzinfo=ZoneInfo("Africa/Brazzaville"))
    result = run(now=now)
    assert result["skipped"] == "hors_fenetre"
    assert result["records"] == 0
