"""Backfill OpenSky : arrivées LFPG et départs FCBB des 4 callsigns AFR.

Respect des quotas (délai, crédits /flights, reprise sur 429) et point de reprise.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from corridor.settings import (
    OPENSKY_CLIENT_ID,
    OPENSKY_CLIENT_SECRET,
    OPENSKY_PASS,
    OPENSKY_REQUEST_DELAY_S,
    OPENSKY_USER,
)

from backfill.checkpoints import load_state, save_state
from backfill.constants import (
    CALLSIGN_TO_FLIGHT,
    OPENSKY_API,
    OPENSKY_TOKEN_URL,
    SOURCE_OPENSKY,
)
from backfill.http_client import RateLimitedClient
from backfill.schedule import (
    itinerary_from_airports,
    itinerary_from_ref,
    primary_ref,
    scheduled_times,
)
from backfill.store import upsert_flight_records

logger = logging.getLogger(__name__)

PARIS = ZoneInfo("Europe/Paris")
BZV = ZoneInfo("Africa/Brazzaville")


class OpenSkyAuth:
    """OAuth2 client credentials, avec repli USER/PASS comme couple client."""

    def __init__(self) -> None:
        self.client_id = OPENSKY_CLIENT_ID or OPENSKY_USER
        self.client_secret = OPENSKY_CLIENT_SECRET or OPENSKY_PASS
        self._token: str | None = None
        self._expires_at = 0.0

    def available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def headers(self) -> dict[str, str]:
        import time

        import httpx

        if not self.available():
            return {}
        now = time.time()
        if self._token and now < self._expires_at:
            return {"Authorization": f"Bearer {self._token}"}
        response = httpx.post(
            OPENSKY_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        expires_in = float(payload.get("expires_in", 1800))
        self._expires_at = now + max(60.0, expires_in - 30.0)
        return {"Authorization": f"Bearer {self._token}"}


def normalize_callsign(raw: str | None) -> str | None:
    if not raw:
        return None
    compact = raw.strip().upper().replace(" ", "")
    if compact in CALLSIGN_TO_FLIGHT:
        return CALLSIGN_TO_FLIGHT[compact]
    # AFR0736 / AF0736 parfois paddés.
    if compact.startswith("AFR") and compact[3:].lstrip("0") :
        padded = "AFR" + compact[3:].lstrip("0")
        if padded in CALLSIGN_TO_FLIGHT:
            return CALLSIGN_TO_FLIGHT[padded]
    if compact.startswith("AF") and not compact.startswith("AFR"):
        candidate = "AFR" + compact[2:].lstrip("0")
        if candidate in CALLSIGN_TO_FLIGHT:
            return CALLSIGN_TO_FLIGHT[candidate]
    return None


def _unix_range_utc_day(day: date) -> tuple[int, int]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    return int(start.timestamp()), int(end.timestamp())


def departure_date_from_seen(
    *,
    first_seen: int | None,
    last_seen: int | None,
) -> date | None:
    """Date civile du départ Congo (soir BZV), pas la date d'arrivée CDG."""
    if first_seen:
        return datetime.fromtimestamp(first_seen, tz=BZV).date()
    if not last_seen:
        return None
    arrival_paris = datetime.fromtimestamp(last_seen, tz=PARIS)
    if arrival_paris.hour < 14:
        return (arrival_paris.astimezone(BZV) - timedelta(hours=12)).date()
    return arrival_paris.astimezone(BZV).date()


def parse(raw_flights: list[dict[str, Any]], *, source: str = SOURCE_OPENSKY) -> list[dict[str, Any]]:
    """Transforme les objets OpenSky (arrivée ou départ) en lignes flight_records."""
    merged: dict[tuple[date, str], dict[str, Any]] = {}
    for item in raw_flights:
        flight_number = normalize_callsign(item.get("callsign"))
        if not flight_number:
            continue
        first_seen = item.get("firstSeen")
        last_seen = item.get("lastSeen")
        day = departure_date_from_seen(first_seen=first_seen, last_seen=last_seen)
        if day is None:
            continue
        dep_icao = (item.get("estDepartureAirport") or "") or None
        arr_icao = (item.get("estArrivalAirport") or "") or None
        key = (day, flight_number)
        row = merged.setdefault(
            key,
            {
                "date": day,
                "flight_number": flight_number,
                "sched_dep": None,
                "actual_dep": None,
                "sched_arr_cdg": None,
                "actual_arr_cdg": None,
                "delay_min": None,
                "aircraft_reg": item.get("icao24"),
                "itinerary": None,
                "source": source,
            },
        )
        if item.get("icao24"):
            row["aircraft_reg"] = item.get("icao24")
        itinerary = itinerary_from_airports(dep_icao, arr_icao)
        if itinerary in {"fih", "pnr"}:
            row["itinerary"] = itinerary
        elif itinerary and not row.get("itinerary"):
            row["itinerary"] = itinerary
        kind = item.get("_kind")
        if kind is None:
            if arr_icao in {"LFPG", "CDG"}:
                kind = "arrival"
            elif dep_icao in {"FCBB", "BZV", "FZAA", "FIH", "FCPP", "PNR"}:
                kind = "departure"
        if kind == "arrival" and last_seen:
            row["actual_arr_cdg"] = datetime.fromtimestamp(last_seen, tz=timezone.utc)
            if first_seen and row["actual_dep"] is None:
                row["actual_dep"] = datetime.fromtimestamp(first_seen, tz=timezone.utc)
        if kind == "departure" and first_seen:
            row["actual_dep"] = datetime.fromtimestamp(first_seen, tz=timezone.utc)

    for (day, flight_number), row in merged.items():
        ref = primary_ref(day, flight_number)
        if ref:
            sched_dep, sched_arr = scheduled_times(day, ref)
            row["sched_dep"] = sched_dep
            row["sched_arr_cdg"] = sched_arr
            if not row.get("itinerary"):
                row["itinerary"] = itinerary_from_ref(ref)
            if row.get("actual_arr_cdg") and sched_arr:
                delta = row["actual_arr_cdg"] - sched_arr
                row["delay_min"] = int(round(delta.total_seconds() / 60.0))
        elif row.get("actual_arr_cdg") and row.get("actual_dep"):
            row["delay_min"] = None
    return [merged[key] for key in sorted(merged)]


def save(rows: list[dict[str, Any]]) -> int:
    return upsert_flight_records(rows)


def _client(delay_s: float) -> RateLimitedClient:
    auth = OpenSkyAuth()
    return RateLimitedClient(
        delay_s=delay_s,
        timeout_s=60.0,
        header_provider=auth.headers if auth.available() else None,
        max_retries=6,
    )


def fetch_window(
    client: RateLimitedClient,
    kind: str,
    airport_icao: str,
    begin: int,
    end: int,
) -> list[dict[str, Any]]:
    path = "/flights/arrival" if kind == "arrival" else "/flights/departure"
    payload = client.get_json(
        f"{OPENSKY_API}{path}",
        params={"airport": airport_icao, "begin": begin, "end": end},
        empty_on_404=True,
    )
    if not payload:
        return []
    if not isinstance(payload, list):
        return []
    for item in payload:
        item["_kind"] = kind
    return [item for item in payload if normalize_callsign(item.get("callsign"))]


def utc_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def fetch(
    *,
    start: date,
    end: date,
    delay_s: float | None = None,
    resume: bool = True,
    client: RateLimitedClient | None = None,
) -> list[dict[str, Any]]:
    """Télécharge arrivées LFPG puis départs FCBB, jour UTC par jour UTC."""
    delay = OPENSKY_REQUEST_DELAY_S if delay_s is None else delay_s
    http = client or _client(delay)
    state = load_state("opensky.json") if resume else {}
    done = set(state.get("done") or [])
    collected: list[dict[str, Any]] = []
    jobs: list[tuple[str, str, date]] = []
    for day in utc_days(start, end):
        jobs.append(("arrival", "LFPG", day))
        jobs.append(("departure", "FCBB", day))
    for kind, airport, day in jobs:
        token = f"{kind}:{airport}:{day.isoformat()}"
        if token in done:
            continue
        begin, finish = _unix_range_utc_day(day)
        logger.info("OpenSky %s %s %s", kind, airport, day.isoformat())
        batch = fetch_window(http, kind, airport, begin, finish)
        collected.extend(batch)
        done.add(token)
        save_state("opensky.json", {"done": sorted(done)})
    return collected


def credentials_configured() -> bool:
    return OpenSkyAuth().available()


def run(
    *,
    start: date,
    end: date,
    delay_s: float | None = None,
    offline_rows: list[dict[str, Any]] | None = None,
    source: str = SOURCE_OPENSKY,
) -> dict[str, Any]:
    if offline_rows is not None:
        parsed = parse(offline_rows, source=source)
        saved = save(parsed)
        return {"records": saved, "raw": len(offline_rows), "mode": "offline"}
    if not credentials_configured():
        raise RuntimeError(
            "OpenSky : OPENSKY_CLIENT_ID et OPENSKY_CLIENT_SECRET manquants "
            "(ou OPENSKY_USER / OPENSKY_PASS comme couple client OAuth2). "
            "Relancer avec --offline pour l'échantillon, ou renseigner .env."
        )
    raw = fetch(start=start, end=end, delay_s=delay_s)
    parsed = parse(raw, source=source)
    saved = save(parsed)
    return {"records": saved, "raw": len(raw), "mode": "live"}
