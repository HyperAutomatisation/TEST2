"""Iowa Mesonet ASOS : vérification optionnelle des archives METAR (CDG/LFPG)."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date
from typing import Any

from backfill.constants import AIRPORT_IATA_TO_ICAO, MESONET_ASOS
from backfill.http_client import RateLimitedClient

# vsby = miles statutaires, sknt = nœuds (URL du cahier des charges).
MILES_TO_KM = 1.60934
KNOTS_TO_KMH = 1.852


def fetch(
    start: date,
    end: date,
    *,
    station: str = "LFPG",
    client: RateLimitedClient | None = None,
) -> str:
    http = client or RateLimitedClient(delay_s=0.0, timeout_s=60.0)
    params = {
        "station": station,
        "data": "tmpc,relh,vsby,sknt,skyc1,wxcodes",
        "year1": start.year,
        "month1": start.month,
        "day1": start.day,
        "year2": end.year,
        "month2": end.month,
        "day2": end.day,
        "tz": "Europe/Paris",
        "format": "onlycomma",
        "missing": "M",
        "latlon": "no",
    }
    return http.get_text(MESONET_ASOS, params=params)


def parse(csv_text: str, *, airport: str = "CDG") -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"vis": [], "wind": [], "storm": False, "n": 0}
    )
    for raw in reader:
        valid = (raw.get("valid") or "")[:10]
        if len(valid) < 10:
            continue
        bucket = buckets[valid]
        bucket["n"] += 1
        vsby = raw.get("vsby")
        if vsby and vsby not in {"M", "null"}:
            bucket["vis"].append(float(vsby) * MILES_TO_KM)
        sknt = raw.get("sknt")
        if sknt and sknt not in {"M", "null"}:
            bucket["wind"].append(float(sknt) * KNOTS_TO_KMH)
        codes = (raw.get("wxcodes") or "").upper()
        if "TS" in codes:
            bucket["storm"] = True
    rows: list[dict[str, Any]] = []
    for day in sorted(buckets):
        bucket = buckets[day]
        rows.append(
            {
                "date": date.fromisoformat(day),
                "airport": airport,
                "forecast_bool": False,
                "precip_mm": None,
                "vis_km": round(min(bucket["vis"]), 3) if bucket["vis"] else None,
                "wind_kmh": round(max(bucket["wind"]), 2) if bucket["wind"] else None,
                "risk_storm": bool(bucket["storm"]),
            }
        )
    return rows


def compare(openmeteo_rows: list[dict[str, Any]], mesonet_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date = {row["date"]: row for row in openmeteo_rows if row["airport"] == "CDG"}
    report: list[dict[str, Any]] = []
    for meso in mesonet_rows:
        om = by_date.get(meso["date"])
        if not om:
            continue
        report.append(
            {
                "date": meso["date"].isoformat(),
                "vis_km_openmeteo": om.get("vis_km"),
                "vis_km_mesonet": meso.get("vis_km"),
                "wind_kmh_openmeteo": om.get("wind_kmh"),
                "wind_kmh_mesonet": meso.get("wind_kmh"),
                "storm_openmeteo": om.get("risk_storm"),
                "storm_mesonet": meso.get("risk_storm"),
            }
        )
    return report


def run(
    *,
    start: date,
    end: date,
    csv_text: str | None = None,
    openmeteo_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    text = csv_text if csv_text is not None else fetch(start, end, station=AIRPORT_IATA_TO_ICAO["CDG"])
    rows = parse(text, airport="CDG")
    report = compare(openmeteo_rows or [], rows)
    return {"records": len(rows), "comparison": report, "rows": rows}
