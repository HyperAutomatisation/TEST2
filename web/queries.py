"""Requêtes pages et API : baromètre, vol, meilleur jour, fiabilité."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from corridor.db import connect
from corridor.flights import (
    WEEKDAY_LABELS,
    flights_for_date,
    format_flight_label,
    serialize_flight,
    today_corridor,
)
from collector.window import in_flight_window
from model import MODEL_VERSION
from model.brier import score_database
from model.classes import CLASSES, CLASS_LABELS
from model.predict import predict_one
from model.warehouse import DISCLAIMER, warehouse_out
from backfill.schedule import itinerary_from_ref, primary_ref, scheduled_times

PARIS = ZoneInfo("Europe/Paris")
SEO_TITLE = "suivi fret aérien Congo Brazzaville Pointe-Noire Paris"
SEO_DESCRIPTION = (
    "Suivi fret aérien Congo Brazzaville Pointe-Noire Paris : baromètre des "
    "vols Air France Congo vers CDG, probabilités de retard et fenêtre de "
    "sortie d'entrepôt, sans compte ni paiement."
)
MOIS = (
    "",
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def icao_callsign(flight_number: str) -> str:
    compact = flight_number.replace(" ", "").upper()
    if compact.startswith("AF") and compact[2:].isdigit():
        return "AFR" + compact[2:]
    return compact


def normalize_flight_number(value: str) -> str:
    return value.replace(" ", "").upper()


def format_dt_fr(value: datetime | None) -> str:
    if value is None:
        return ""
    local = value.astimezone(PARIS) if value.tzinfo else value.replace(tzinfo=PARIS)
    label = WEEKDAY_LABELS[local.isoweekday()]
    return (
        f"{label} {local.day} {MOIS[local.month]} {local.year} "
        f"à {local.strftime('%Hh%M')}"
    )


def known_flight_numbers() -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT flight_number FROM ref_flights
            ORDER BY flight_number
            """
        ).fetchall()
    return [row["flight_number"] for row in rows]


def stats_30d(flight_number: str, *, before: date) -> dict[str, Any]:
    start = before - timedelta(days=30)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS n,
                AVG(delay_min) AS retard_moyen,
                COUNT(*) FILTER (WHERE delay_min < 15) AS on_time
            FROM flight_records
            WHERE flight_number = %s
              AND delay_min IS NOT NULL
              AND date >= %s AND date < %s
            """,
            (flight_number, start, before),
        ).fetchone()
    n = int(row["n"] or 0) if row else 0
    if n == 0:
        return {"n_30d": 0, "ponctualite_30d": None, "retard_moyen_30d": None}
    return {
        "n_30d": n,
        "ponctualite_30d": 100.0 * int(row["on_time"]) / n,
        "retard_moyen_30d": float(row["retard_moyen"]),
    }


def _serialize_prediction(row: dict[str, Any]) -> dict[str, Any]:
    probs = {key: float(row[key]) for key in CLASSES}
    factors = row.get("factors_json") or []
    if isinstance(factors, dict):
        factors = factors.get("factors") or list(factors.values())
    return {
        "date": row["date"].isoformat() if hasattr(row["date"], "isoformat") else row["date"],
        "flight_number": row["flight_number"],
        "model_version": row.get("model_version") or MODEL_VERSION,
        "probs": probs,
        "factors": list(factors),
        "p_on_time_pct": round(probs["p_0_15"] * 100),
        "p_plus_1h_pct": round((probs["p_60_120"] + probs["p_120_plus"]) * 100),
        "labels": CLASS_LABELS,
    }


def get_prediction(
    day: date, flight_number: str, *, compute: bool = True
) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT date, flight_number, model_version, factors_json,
                   p_0_15, p_15_30, p_30_60, p_60_120, p_120_plus, p_cancel
            FROM predictions
            WHERE date = %s AND flight_number = %s AND model_version = %s
            """,
            (day, flight_number, MODEL_VERSION),
        ).fetchone()
    if row:
        return _serialize_prediction(row)
    if not compute:
        return None
    probs, factors = predict_one(flight_number, day)
    values = list(probs.values())
    if max(values) - min(values) < 1e-9:
        return None
    return _serialize_prediction(
        {
            "date": day,
            "flight_number": flight_number,
            "model_version": MODEL_VERSION,
            "factors_json": factors,
            **probs,
        }
    )


def signature_figure(day: date) -> dict[str, Any]:
    flights = flights_for_date(day)
    if not flights:
        return {
            "text": "Aucun vol de référence actif pour cette date.",
            "flight_number": None,
            "flight_label": None,
        }
    first = serialize_flight(flights[0])
    pred = get_prediction(day, first["flight_number"])
    if not pred:
        return {
            "flight_number": first["flight_number"],
            "flight_label": first["flight_label"],
            "text": (
                f"{first['flight_label']} de ce soir : prévision en attente "
                "de la collecte de 21 h."
            ),
            "prediction": None,
        }
    return {
        "flight_number": first["flight_number"],
        "flight_label": first["flight_label"],
        "text": (
            f"{first['flight_label']} de ce soir : {pred['p_on_time_pct']} % "
            f"à l'heure, {pred['p_plus_1h_pct']} % retard +1 h."
        ),
        "prediction": pred,
    }


def barometre(start: date | None = None) -> dict[str, Any]:
    resolved = start or today_corridor()
    days: list[dict[str, Any]] = []
    for offset in range(7):
        day = resolved + timedelta(days=offset)
        rows = []
        for flight in flights_for_date(day):
            item = serialize_flight(flight)
            item.update(stats_30d(item["flight_number"], before=day))
            item["prediction"] = get_prediction(day, item["flight_number"])
            item["itinerary"] = itinerary_from_ref(flight)
            rows.append(item)
        days.append(
            {
                "date": day.isoformat(),
                "weekday": day.isoweekday(),
                "weekday_label": WEEKDAY_LABELS[day.isoweekday()],
                "flights": rows,
            }
        )
    return {
        "start": resolved.isoformat(),
        "signature": signature_figure(resolved),
        "days": days,
        "seo_title": SEO_TITLE,
        "seo_description": SEO_DESCRIPTION,
    }


def latest_adsb(flight_number: str) -> dict[str, Any] | None:
    callsign = icao_callsign(flight_number)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT seen_at, callsign, flight_number, lat, lon, alt_baro, gs,
                   track, inferred_event
            FROM adsb_snapshots
            WHERE flight_number = %s
               OR callsign = %s
               OR TRIM(callsign) = %s
            ORDER BY seen_at DESC
            LIMIT 1
            """,
            (flight_number, callsign, callsign),
        ).fetchone()
    if not row:
        return None
    return {
        "seen_at": row["seen_at"].isoformat() if row["seen_at"] else None,
        "seen_display": format_dt_fr(row["seen_at"]),
        "callsign": row["callsign"],
        "lat": row["lat"],
        "lon": row["lon"],
        "alt_baro": row["alt_baro"],
        "gs": row["gs"],
        "track": row["track"],
        "inferred_event": row["inferred_event"],
        "in_window": in_flight_window(),
    }


def history_90d(flight_number: str, *, before: date) -> list[dict[str, Any]]:
    start = before - timedelta(days=90)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT date, delay_min
            FROM flight_records
            WHERE flight_number = %s AND delay_min IS NOT NULL
              AND date >= %s AND date < %s
            ORDER BY date
            """,
            (flight_number, start, before),
        ).fetchall()
    return [
        {"date": row["date"].isoformat(), "delay_min": int(row["delay_min"])} for row in rows
    ]


def punctuality_by_weekday(flight_number: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT date, delay_min FROM flight_records
            WHERE flight_number = %s AND delay_min IS NOT NULL
            """,
            (flight_number,),
        ).fetchall()
    buckets: dict[int, list[int]] = defaultdict(list)
    for row in rows:
        buckets[row["date"].isoweekday()].append(int(row["delay_min"]))
    result = []
    for weekday in range(1, 8):
        delays = buckets.get(weekday, [])
        n = len(delays)
        result.append(
            {
                "weekday": weekday,
                "weekday_label": WEEKDAY_LABELS[weekday],
                "n": n,
                "ponctualite": (100.0 * sum(1 for d in delays if d < 15) / n) if n else None,
                "retard_moyen": (sum(delays) / n) if n else None,
            }
        )
    return result


def next_departure_day(flight_number: str, start: date) -> date | None:
    for offset in range(0, 16):
        day = start + timedelta(days=offset)
        if any(row["flight_number"] == flight_number for row in flights_for_date(day)):
            return day
    return None


def warehouse_payload(day: date, flight_number: str) -> dict[str, Any] | None:
    with connect() as conn:
        rec = conn.execute(
            """
            SELECT actual_arr_cdg, sched_arr_cdg, itinerary
            FROM flight_records
            WHERE date = %s AND flight_number = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (day, flight_number),
        ).fetchone()
    arrival = rec["actual_arr_cdg"] or rec["sched_arr_cdg"] if rec else None
    itinerary = rec["itinerary"] if rec else None
    ref = primary_ref(day, flight_number)
    if ref:
        itinerary = itinerary or itinerary_from_ref(ref)
        if arrival is None:
            _, arrival = scheduled_times(day, ref)
    if arrival is None:
        return None
    estimated = warehouse_out(arrival, itinerary=itinerary)
    return {
        "arrival": arrival.isoformat(),
        "arrival_display": format_dt_fr(arrival),
        "warehouse_out": estimated.isoformat(),
        "warehouse_display": format_dt_fr(estimated),
        "itinerary": itinerary,
        "disclaimer": DISCLAIMER,
    }


def vol_payload(flight_number: str, day: date | None = None) -> dict[str, Any] | None:
    number = normalize_flight_number(flight_number)
    if number not in known_flight_numbers():
        return None
    resolved = day or today_corridor()
    target = next_departure_day(number, resolved) or resolved
    refs = [serialize_flight(row) for row in flights_for_date(target) if row["flight_number"] == number]
    history = history_90d(number, before=target)
    return {
        "flight_number": number,
        "flight_label": format_flight_label(number),
        "date": target.isoformat(),
        "weekday_label": WEEKDAY_LABELS[target.isoweekday()],
        "grille": refs,
        "live": latest_adsb(number),
        "prediction": get_prediction(target, number),
        "warehouse": warehouse_payload(target, number),
        "history_90d": history,
        "history_90d_json": json.dumps(history),
        "ponctualite_semaine": punctuality_by_weekday(number),
        "seo_title": SEO_TITLE,
        "seo_description": SEO_DESCRIPTION,
    }


def meilleur_jour_payload(start: date | None = None) -> dict[str, Any]:
    resolved = start or today_corridor()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT date, delay_min FROM flight_records
            WHERE delay_min IS NOT NULL
            """
        ).fetchall()
    by_wd: dict[int, list[int]] = defaultdict(list)
    for row in rows:
        by_wd[row["date"].isoweekday()].append(int(row["delay_min"]))
    ranking: list[dict[str, Any]] = []
    seen: set[int] = set()
    for offset in range(7):
        day = resolved + timedelta(days=offset)
        weekday = day.isoweekday()
        if weekday in seen:
            continue
        seen.add(weekday)
        delays = by_wd.get(weekday, [])
        n = len(delays)
        flights = [serialize_flight(row) for row in flights_for_date(day)]
        itineraries = sorted({itinerary_from_ref(row) for row in flights_for_date(day)})
        ranking.append(
            {
                "weekday": weekday,
                "weekday_label": WEEKDAY_LABELS[weekday],
                "n": n,
                "ponctualite": (100.0 * sum(1 for d in delays if d < 15) / n) if n else None,
                "retard_moyen": (sum(delays) / n) if n else None,
                "flights": flights,
                "itineraries": itineraries,
            }
        )
    ranking.sort(
        key=lambda item: (
            -(item["ponctualite"] if item["ponctualite"] is not None else -1.0),
            item["retard_moyen"] if item["retard_moyen"] is not None else 10**9,
        )
    )
    return {
        "start": resolved.isoformat(),
        "ranking": ranking,
        "lecture": (
            "Lecture guidée : le mardi et le samedi passent souvent par Kinshasa, "
            "le mercredi est un direct, le vendredi soir arrive le samedi "
            "(fenêtre d'entrepôt plus longue, estimation v1)."
        ),
        "seo_title": SEO_TITLE,
        "seo_description": SEO_DESCRIPTION,
    }


def fiabilite_payload() -> dict[str, Any]:
    scored = score_database()
    return {
        **scored,
        "seo_title": SEO_TITLE,
        "seo_description": SEO_DESCRIPTION,
        "modele": MODEL_VERSION,
        "naive_label": "prédiction naïve : heure prévue de la grille (classe 0-15 min)",
    }


def pct(value: float | None) -> str:
    if value is None:
        return "n.d."
    return f"{value:.0f} %"


def minutes(value: float | None) -> str:
    if value is None:
        return "n.d."
    return f"{value:.0f} min"
