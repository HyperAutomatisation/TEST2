from __future__ import annotations

import json

from collector.awc import parse_metar, parse_taf
from collector.openmeteo_forecast import parse
from corridor.settings import ROOT


def test_metar_orage_bzv() -> None:
    payload = json.loads((ROOT / "collector/data/samples/awc_metar.json").read_text(encoding="utf-8"))
    rows = parse_metar(payload)
    by_airport = {row["airport"]: row for row in rows}
    assert by_airport["BZV"]["risk_storm"] is True
    assert by_airport["CDG"]["risk_storm"] is False
    assert by_airport["CDG"]["vis_km"] is not None


def test_taf_orage() -> None:
    payload = json.loads((ROOT / "collector/data/samples/awc_taf.json").read_text(encoding="utf-8"))
    flags = {row["airport"]: row for row in parse_taf(payload)}
    assert flags["BZV"]["risk_storm"] is True


def test_openmeteo_forecast_flag() -> None:
    payload = json.loads(
        (ROOT / "collector/data/samples/openmeteo_forecast_cdg.json").read_text(encoding="utf-8")
    )
    rows = parse(payload, airport="CDG")
    assert rows
    assert all(row["forecast_bool"] is True for row in rows)
