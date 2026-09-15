from __future__ import annotations

import json
from datetime import date

from backfill.constants import SAMPLES_DIR
from backfill.openmeteo import parse, save


def test_parse_openmeteo_visibilite_en_km() -> None:
    payload = json.loads((SAMPLES_DIR / "openmeteo_cdg.json").read_text(encoding="utf-8"))
    rows = parse(payload, airport="CDG")
    assert [row["date"] for row in rows] == [
        date(2026, 9, 1),
        date(2026, 9, 2),
        date(2026, 9, 3),
    ]
    first = rows[0]
    assert first["airport"] == "CDG"
    assert first["forecast_bool"] is False
    assert first["vis_km"] is not None
    assert first["vis_km"] < 50  # mètres convertis
    assert first["precip_mm"] is not None
    assert first["wind_kmh"] is not None
    assert first["risk_storm"] is False


def test_orage_wmo_95() -> None:
    payload = {
        "hourly": {
            "time": ["2026-04-01T18:00", "2026-04-01T19:00"],
            "precipitation": [2.0, 8.0],
            "visibility": [4000, 2000],
            "wind_speed_10m": [20.0, 35.0],
            "weather_code": [61, 95],
        }
    }
    rows = parse(payload, airport="FIH")
    assert len(rows) == 1
    assert rows[0]["risk_storm"] is True
    assert rows[0]["precip_mm"] == 10.0
    assert rows[0]["vis_km"] == 2.0
    assert rows[0]["wind_kmh"] == 35.0


def test_save_weather(clean_backfill) -> None:
    payload = json.loads((SAMPLES_DIR / "openmeteo_bzv.json").read_text(encoding="utf-8"))
    rows = parse(payload, airport="BZV")
    assert save(rows) == 3
    assert save(rows) == 3
    n = clean_backfill.execute("SELECT COUNT(*) AS n FROM weather").fetchone()["n"]
    assert n == 3
