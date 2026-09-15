"""Tableaux des aéroports congolais : parser HTML tolérant (BeautifulSoup)."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from corridor.settings import COLLECTORS_USE_SAMPLE, ROOT, TIMEZONE

from backfill.http_client import RateLimitedClient
from backfill.store import upsert_rotations

logger = logging.getLogger(__name__)

PAGES = {
    "bzv_dep": "https://www.brazzaville-aeroport.com/departs-du-jour/",
    "bzv_arr": "https://www.brazzaville-aeroport.com/arrivees-du-jour/",
    "pnr_dep": "https://www.pointenoire-aeroport.com/departs-du-jour/",
    "pnr_arr": "https://www.pointenoire-aeroport.com/arrivees-du-jours/",
}
SAMPLES = ROOT / "collector" / "data" / "samples"
FLIGHT_RE = re.compile(r"\bAF\s*(\d{3})\b", re.I)
TIME_RE = re.compile(r"\b(\d{1,2})[h:](\d{2})\b")
STATUS_RE = re.compile(r"(parti|posé|pose)\s*à\s*(\d{1,2}[h:]\d{2})", re.I)


def _hhmm(match: re.Match[str]) -> time:
    return time(int(match.group(1)), int(match.group(2)))


def parse(html: str, *, page: str = "bzv_dep") -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        logger.warning("aéroports congolais : pas de table (%s), structure peut-être changée", page)
    rows: list[dict[str, Any]] = []
    text_blocks: list[str] = []
    if tables:
        for table in tables:
            for tr in table.find_all("tr"):
                text_blocks.append(" ".join(td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])))
    else:
        text_blocks.append(soup.get_text(" ", strip=True))
    for block in text_blocks:
        flight_m = FLIGHT_RE.search(block)
        if not flight_m:
            continue
        flight_number = f"AF{flight_m.group(1)}"
        status_m = STATUS_RE.search(block)
        sched_m = TIME_RE.search(block)
        actual = None
        kind = "unknown"
        if status_m:
            kind = "dep" if status_m.group(1).lower().startswith("parti") else "arr"
            hm = TIME_RE.search(status_m.group(0))
            if hm:
                actual = _hhmm(hm)
        sched = _hhmm(sched_m) if sched_m else None
        delay = None
        if actual and sched:
            delay = (actual.hour * 60 + actual.minute) - (sched.hour * 60 + sched.minute)
        rows.append(
            {
                "page": page,
                "flight_number": flight_number,
                "sched": sched,
                "actual": actual,
                "kind": kind,
                "delay_min": delay,
                "raw": block[:240],
            }
        )
    if not rows:
        logger.warning("aéroports congolais : aucune ligne Air France (%s)", page)
    return rows


def fetch(page: str, *, sample_path: Path | None = None) -> str:
    sample = sample_path or (SAMPLES / f"aeroport_{page}.html")
    if COLLECTORS_USE_SAMPLE or sample_path or sample.exists() and COLLECTORS_USE_SAMPLE:
        if sample.exists():
            return sample.read_text(encoding="utf-8")
    if COLLECTORS_USE_SAMPLE:
        return sample.read_text(encoding="utf-8")
    http = RateLimitedClient(delay_s=0.5, timeout_s=25.0)
    return http.get_text(PAGES[page])


def save(rows: list[dict[str, Any]], *, day: date | None = None) -> int:
    resolved = day or datetime.now(ZoneInfo(TIMEZONE)).date()
    rotations = []
    for row in rows:
        if row.get("kind") == "arr" and row.get("delay_min") is not None:
            rotations.append(
                {
                    "date": resolved,
                    "aircraft_reg": f"inconnu-{row['flight_number']}",
                    "retard_troncon_aller_min": row["delay_min"],
                }
            )
    return upsert_rotations(rotations) if rotations else 0


def run(*, html_by_page: dict[str, str] | None = None, day: date | None = None) -> dict[str, Any]:
    parsed: list[dict[str, Any]] = []
    if html_by_page is not None:
        for page, html in html_by_page.items():
            parsed.extend(parse(html, page=page))
    else:
        for page in PAGES:
            try:
                parsed.extend(parse(fetch(page), page=page))
            except Exception as exc:  # noqa: BLE001
                logger.warning("aéroport %s : %s", page, exc)
    saved = save(parsed, day=day)
    return {"records": saved, "parsed": len(parsed)}
