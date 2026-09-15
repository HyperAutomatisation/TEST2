from __future__ import annotations

import json

from collector.adsbdb import parse_aircraft, parse_callsign
from corridor.settings import ROOT


def test_itineraire_fih() -> None:
    payload = json.loads(
        (ROOT / "collector/data/samples/adsbdb_callsign.json").read_text(encoding="utf-8")
    )
    route = parse_callsign(payload, callsign="AFR754")
    assert route["flight_number"] == "AF754"
    assert route["itinerary"] == "fih"
    assert route["origin"] == "FZAA"


def test_immatriculation() -> None:
    payload = json.loads(
        (ROOT / "collector/data/samples/adsbdb_aircraft.json").read_text(encoding="utf-8")
    )
    aircraft = parse_aircraft(payload)
    assert aircraft["registration"] == "F-HRBA"
