"""Nager.Date : jours fériés France, cache annuelle, ponts jeudi/mardi."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from corridor.settings import COLLECTORS_USE_SAMPLE, ROOT
from backfill.http_client import RateLimitedClient
from backfill.store import upsert_calendar
from model.layer3 import mark_ponts

API = "https://date.nager.at/api/v3/PublicHolidays/{year}/FR"
SAMPLE_PATH = ROOT / "collector" / "data" / "samples" / "nager_fr_2026.json"
SOURCE = "nager"


def fetch(year: int, *, client: RateLimitedClient | None = None) -> list[dict[str, Any]]:
    if COLLECTORS_USE_SAMPLE:
        return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    http = client or RateLimitedClient(delay_s=0.2, timeout_s=20.0)
    payload = http.get_json(API.format(year=year))
    if not isinstance(payload, list):
        raise RuntimeError("Nager.Date : réponse inattendue")
    return payload


def parse(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        raw = item.get("date")
        if not raw:
            continue
        day = date.fromisoformat(str(raw)[:10])
        rows.append(
            {
                "date": day,
                "country": "FR",
                "label": item.get("localName") or item.get("name") or "férié",
                "is_pont": False,
            }
        )
    return mark_ponts(rows)


def save(rows: list[dict[str, Any]]) -> int:
    return upsert_calendar(rows)


def run(*, year: int | None = None) -> dict[str, Any]:
    resolved = year or datetime.now().year
    raw = fetch(resolved)
    parsed = parse(raw)
    return {"records": save(parsed), "year": resolved, "source": SOURCE}
