"""Import unique OurAirports pour LFPG, FZAA, FCBB, FCPP."""

from __future__ import annotations

import csv
import io
import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from corridor.db import connect
from corridor.settings import OURAIRPORTS_URL, ROOT

logger = logging.getLogger(__name__)

CORRIDOR_ICAO = ("LFPG", "FZAA", "FCBB", "FCPP")
SAMPLE_PATH = ROOT / "collector" / "data" / "ourairports_airports.sample.csv"
TIMEZONES_PATH = ROOT / "collector" / "data" / "airport_timezones.json"


def _timezones() -> dict[str, str]:
    return json.loads(TIMEZONES_PATH.read_text(encoding="utf-8"))


def fetch(url: str | None = None, *, sample_path: Path | None = None) -> str:
    """Télécharge le CSV OurAirports, sinon lit l'échantillon figé."""
    path = sample_path or SAMPLE_PATH
    if os.environ.get("OURAIRPORTS_USE_SAMPLE") == "1":
        logger.info("OurAirports : échantillon figé (OURAIRPORTS_USE_SAMPLE=1)")
        return path.read_text(encoding="utf-8")
    target = url or OURAIRPORTS_URL
    try:
        response = httpx.get(target, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        logger.info("OurAirports : CSV distant lu (%s)", target)
        return response.text
    except Exception as exc:
        logger.warning("OurAirports distant indisponible (%s), échantillon figé", exc)
        return path.read_text(encoding="utf-8")


def parse(csv_text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    wanted = set(CORRIDOR_ICAO)
    timezones = _timezones()
    rows: list[dict[str, Any]] = []
    for raw in reader:
        ident = (raw.get("ident") or "").strip()
        if ident not in wanted:
            continue
        icao = (raw.get("icao_code") or raw.get("gps_code") or ident).strip()
        rows.append(
            {
                "ident": ident,
                "iata_code": (raw.get("iata_code") or "").strip() or None,
                "icao_code": icao,
                "name": (raw.get("name") or "").strip() or None,
                "latitude": float(raw["latitude_deg"]),
                "longitude": float(raw["longitude_deg"]),
                "timezone": timezones.get(ident),
            }
        )
    rows.sort(key=lambda item: item["ident"])
    return rows


def save(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with connect() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO ref_airports (
                        ident, iata_code, icao_code, name, latitude, longitude, timezone
                    )
                    VALUES (
                        %(ident)s, %(iata_code)s, %(icao_code)s, %(name)s,
                        %(latitude)s, %(longitude)s, %(timezone)s
                    )
                    ON CONFLICT (ident) DO UPDATE SET
                        iata_code = EXCLUDED.iata_code,
                        icao_code = EXCLUDED.icao_code,
                        name = EXCLUDED.name,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        timezone = EXCLUDED.timezone
                    """,
                    row,
                )
        conn.commit()
    return len(rows)


def import_airports(*, url: str | None = None, sample_path: Path | None = None) -> int:
    csv_text = fetch(url, sample_path=sample_path)
    return save(parse(csv_text))
