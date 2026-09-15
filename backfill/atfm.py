"""Retards ATFM Eurocontrol (Airport Arrival ATFM Delay) pour CDG / LFPG."""

from __future__ import annotations

import bz2
import csv
import io
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from backfill.constants import ATFM_AIRPORT_ICAO, ATFM_URL_CANDIDATES, INCOMING_DIR, SAMPLES_DIR
from backfill.http_client import RateLimitedClient
from backfill.store import upsert_atfm

logger = logging.getLogger(__name__)


def _parse_flt_date(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    if "T" in text:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        snippet = text[:10]
        try:
            return datetime.strptime(snippet, fmt).date()
        except ValueError:
            continue
    return None


def parse(csv_text: str, *, airport_iata: str = "CDG") -> list[dict[str, Any]]:
    sample = csv_text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(sample))
    rows: list[dict[str, Any]] = []
    for raw in reader:
        icao = (raw.get("APT_ICAO") or raw.get("apt_icao") or "").strip().upper()
        if icao not in {ATFM_AIRPORT_ICAO, "CDG"}:
            continue
        day = _parse_flt_date(raw.get("FLT_DATE") or raw.get("flt_date") or "")
        if day is None:
            continue
        arrivals_raw = raw.get("FLT_ARR_1") or raw.get("flt_arr_1") or "0"
        delay_raw = raw.get("DLY_APT_ARR_1") or raw.get("dly_apt_arr_1") or "0"
        try:
            arrivals = float(str(arrivals_raw).replace(",", ".") or 0)
            delay_total = float(str(delay_raw).replace(",", ".") or 0)
        except ValueError:
            continue
        avg = delay_total / arrivals if arrivals else 0.0
        rows.append(
            {
                "date": day,
                "airport": airport_iata,
                "delay_avg_min": round(avg, 2),
            }
        )
    rows.sort(key=lambda item: item["date"])
    return rows


def _decode(blob: bytes) -> str:
    if blob.startswith(b"BZh"):
        blob = bz2.decompress(blob)
    return blob.decode("utf-8", errors="replace")


def _incoming_files(years: list[int]) -> list[Path]:
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    found: list[Path] = []
    for year in years:
        for name in (f"apt_dly_{year}.csv.bz2", f"apt_dly_{year}.csv"):
            path = INCOMING_DIR / name
            if path.exists():
                found.append(path)
    return found


def fetch(
    years: list[int],
    *,
    client: RateLimitedClient | None = None,
    allow_sample: bool = True,
) -> str:
    local = _incoming_files(years)
    if local:
        parts = [_decode(path.read_bytes()) for path in local]
        return _concat_csv(parts)
    http = client or RateLimitedClient(delay_s=0.5, timeout_s=45.0)
    blobs: list[str] = []
    errors: list[str] = []
    for year in years:
        ok = False
        for template in ATFM_URL_CANDIDATES:
            url = template.format(year=year)
            try:
                blob = http.get_bytes(url)
                if blob.lstrip().startswith(b"<!DOCTYPE") or blob.lstrip().startswith(b"<html"):
                    errors.append(f"{url}: HTML (Cloudflare ou portail)")
                    continue
                blobs.append(_decode(blob))
                ok = True
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{url}: {exc}")
        if not ok:
            logger.warning("ATFM %s indisponible à distance (%s)", year, " ; ".join(errors[-3:]))
    if blobs:
        return _concat_csv(blobs)
    if allow_sample:
        sample = SAMPLES_DIR / "atfm_apt_dly.csv"
        logger.warning("ATFM distant bloqué, échantillon figé %s", sample)
        return sample.read_text(encoding="utf-8")
    raise RuntimeError(
        "ATFM Eurocontrol : téléchargement bloqué (Cloudflare). "
        "Déposer apt_dly_AAAA.csv ou .csv.bz2 dans backfill/data/incoming/ "
        "(fichiers du portail https://ansperformance.eu/csv/). "
        + " | ".join(errors[:6])
    )


def _concat_csv(parts: list[str]) -> str:
    if not parts:
        return ""
    header = None
    body: list[str] = []
    for part in parts:
        lines = [line for line in part.splitlines() if line.strip()]
        if not lines:
            continue
        if header is None:
            header = lines[0]
            body.extend(lines[1:])
        else:
            start = 1 if lines[0].lower().startswith("year") or "FLT_DATE" in lines[0].upper() else 0
            body.extend(lines[start:])
    return "\n".join([header or ""] + body) + "\n"


def save(rows: list[dict[str, Any]]) -> int:
    return upsert_atfm(rows)


def run(
    *,
    start: date,
    end: date,
    csv_text: str | None = None,
    allow_sample: bool = True,
) -> dict[str, Any]:
    years = list(range(start.year, end.year + 1))
    text = csv_text if csv_text is not None else fetch(years, allow_sample=allow_sample)
    parsed = parse(text)
    filtered = [row for row in parsed if start <= row["date"] <= end]
    saved = save(filtered)
    return {"records": saved, "parsed": len(parsed)}
