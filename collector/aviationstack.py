"""AviationStack : heures prévues/réelles, 4 requêtes par jour de vol maximum."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from corridor.flights import flights_for_date
from corridor.settings import (
    AVIATIONSTACK_KEY,
    AVIATIONSTACK_MAX_REQ_PER_DAY,
    COLLECTORS_USE_SAMPLE,
    ROOT,
    TIMEZONE,
)

from backfill.http_client import RateLimitedClient
from backfill.schedule import itinerary_from_ref, primary_ref, scheduled_times
from backfill.store import upsert_flight_records
from collector.season import is_season_change, log_season_change

logger = logging.getLogger(__name__)

API_URL = "https://api.aviationstack.com/v1/flights"
SAMPLE_PATH = ROOT / "collector" / "data" / "samples" / "aviationstack_af754.json"
STATE_PATH = ROOT / "collector" / ".state" / "aviationstack_quota.json"
SOURCE = "aviationstack"


def _quota_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"day": None, "count": 0}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _save_quota(day: date, count: int) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps({"day": day.isoformat(), "count": count}),
        encoding="utf-8",
    )


def remaining_quota(day: date) -> int:
    state = _quota_state()
    if state.get("day") != day.isoformat():
        return AVIATIONSTACK_MAX_REQ_PER_DAY
    return max(0, AVIATIONSTACK_MAX_REQ_PER_DAY - int(state.get("count") or 0))


def consume_quota(day: date, n: int = 1) -> bool:
    left = remaining_quota(day)
    if n > left:
        return False
    used = AVIATIONSTACK_MAX_REQ_PER_DAY - left + n
    _save_quota(day, used)
    return True


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def parse(payload: dict[str, Any], *, day: date | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    alerts: list[str] = []
    rows: list[dict[str, Any]] = []
    items = payload.get("data") or payload.get("flights") or []
    for item in items:
        flight = (item.get("flight") or {}).get("iata") or ""
        flight_number = flight.replace(" ", "").upper()
        if not flight_number.startswith("AF"):
            continue
        dep = item.get("departure") or {}
        arr = item.get("arrival") or {}
        aircraft = item.get("aircraft") or {}
        status = (item.get("flight_status") or "").lower()
        sched_dep = _parse_iso(dep.get("scheduled"))
        actual_dep = _parse_iso(dep.get("actual") or dep.get("estimated"))
        sched_arr = _parse_iso(arr.get("scheduled"))
        actual_arr = _parse_iso(arr.get("actual") or arr.get("estimated"))
        flight_day = day
        if flight_day is None and sched_dep:
            flight_day = sched_dep.astimezone(ZoneInfo(TIMEZONE)).date()
        if flight_day is None:
            continue
        ref = primary_ref(flight_day, flight_number)
        grid_dep, grid_arr = (None, None)
        itinerary = None
        if ref:
            grid_dep, grid_arr = scheduled_times(flight_day, ref)
            itinerary = itinerary_from_ref(ref)
            if sched_dep and is_season_change(ref_time(ref), sched_dep):
                alerts.append(log_season_change(flight_number, ref_time(ref), sched_dep))
        delay = None
        if actual_arr and (sched_arr or grid_arr):
            base = sched_arr or grid_arr
            delay = int(round((actual_arr - base).total_seconds() / 60.0))
        if status == "cancelled":
            delay = None
        rows.append(
            {
                "date": flight_day,
                "flight_number": flight_number,
                "sched_dep": sched_dep or grid_dep,
                "actual_dep": actual_dep,
                "sched_arr_cdg": sched_arr or grid_arr,
                "actual_arr_cdg": None if status == "cancelled" else actual_arr,
                "delay_min": delay,
                "aircraft_reg": aircraft.get("registration"),
                "itinerary": itinerary,
                "source": SOURCE,
                "flight_status": status,
            }
        )
    return rows, alerts


def ref_time(ref: dict[str, Any]):
    from datetime import time as time_cls

    value = ref["sched_dep_local"]
    if isinstance(value, time_cls):
        return value
    hours, minutes = str(value).split(":")[:2]
    return time_cls(int(hours), int(minutes))


def fetch(
    flight_iata: str,
    *,
    client: RateLimitedClient | None = None,
    sample_path: Path | None = None,
) -> dict[str, Any]:
    if COLLECTORS_USE_SAMPLE or sample_path:
        path = sample_path or SAMPLE_PATH
        return json.loads(path.read_text(encoding="utf-8"))
    if not AVIATIONSTACK_KEY:
        raise RuntimeError(
            "AVIATIONSTACK_KEY manquant. Renseigner .env, sans inventer de clé. "
            "Tests : COLLECTORS_USE_SAMPLE=1 ou payload figé."
        )
    http = client or RateLimitedClient(delay_s=0.5, timeout_s=30.0)
    return http.get_json(
        API_URL,
        params={"access_key": AVIATIONSTACK_KEY, "airline_iata": "AF", "flight_iata": flight_iata},
    )


def save(rows: list[dict[str, Any]]) -> int:
    cleaned = [{k: v for k, v in row.items() if k != "flight_status"} for row in rows]
    return upsert_flight_records(cleaned)


def run(*, day: date | None = None, payloads: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    resolved = day or datetime.now(ZoneInfo(TIMEZONE)).date()
    refs = flights_for_date(resolved)
    wanted = []
    seen: set[str] = set()
    for ref in refs:
        number = ref["flight_number"]
        if number not in seen:
            seen.add(number)
            wanted.append(number)
    wanted = wanted[:AVIATIONSTACK_MAX_REQ_PER_DAY]
    all_rows: list[dict[str, Any]] = []
    alerts: list[str] = []
    fetched = 0
    if payloads is not None:
        for payload in payloads:
            rows, more = parse(payload, day=resolved)
            all_rows.extend(rows)
            alerts.extend(more)
            fetched += 1
    else:
        for number in wanted:
            if not COLLECTORS_USE_SAMPLE and not consume_quota(resolved):
                logger.warning("AviationStack quota journalier atteint (%s)", AVIATIONSTACK_MAX_REQ_PER_DAY)
                break
            payload = fetch(number)
            rows, more = parse(payload, day=resolved)
            all_rows.extend(rows)
            alerts.extend(more)
            fetched += 1
    saved = save(all_rows)
    return {"records": saved, "requests": fetched, "alerts": alerts}
