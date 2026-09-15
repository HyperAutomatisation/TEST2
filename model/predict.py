"""Génération des prédictions du soir (21 h) et clôture (9 h 30)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from psycopg.types.json import Json

from corridor.db import connect
from corridor.flights import flights_for_date, today_corridor
from model import MODEL_VERSION
from model.aggregate import weighted_mean
from model.classes import CLASSES
from model.layer1 import layer1
from model.layer2 import inherited_delay_min, layer2, weather_risk
from model.layer3 import layer3
from backfill.store import upsert_predictions


def _aircraft_reg(day: date, flight_number: str) -> str | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT aircraft_reg FROM flight_records
            WHERE date = %s AND flight_number = %s AND aircraft_reg IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (day, flight_number),
        ).fetchone()
    if row:
        return row["aircraft_reg"]
    return None


def predict_one(flight_number: str, day: date) -> tuple[dict[str, float], list[str]]:
    base = layer1(flight_number, day, before=day)
    inherited = inherited_delay_min(day, _aircraft_reg(day, flight_number))
    storm = weather_risk(day)
    layer_two, factors_two, weight_two = layer2(base, inherited=inherited, storm=storm)
    layer_three, factors_three, weight_three = layer3(base, day)
    probs = weighted_mean(base, layer_two, layer_three, 1.0, weight_two, weight_three)
    factors = factors_two + factors_three
    if not factors:
        factors = ["Distribution empirique du corridor, sans facteur du jour."]
    return probs, factors


def generate_for_date(day: date | None = None) -> dict[str, Any]:
    """Écrit une prédiction v1 par numéro de vol du jour (upsert)."""
    resolved = day or today_corridor()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for flight in flights_for_date(resolved):
        number = flight["flight_number"]
        if number in seen:
            continue
        seen.add(number)
        probs, factors = predict_one(number, resolved)
        row: dict[str, Any] = {
            "date": resolved,
            "flight_number": number,
            "model_version": MODEL_VERSION,
            "factors_json": Json(factors),
        }
        for key in CLASSES:
            row[key] = probs[key]
        rows.append(row)
    saved = upsert_predictions(rows)
    return {"records": saved, "date": resolved.isoformat(), "model_version": MODEL_VERSION}


def generate_range(start: date, end: date) -> dict[str, Any]:
    total = 0
    cursor = start
    while cursor <= end:
        total += int(generate_for_date(cursor).get("records") or 0)
        cursor += timedelta(days=1)
    return {"records": total, "start": start.isoformat(), "end": end.isoformat()}
