"""Archives DGAC (tendanCiel). Extraction semi-automatique acceptée en v1."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from backfill.constants import DGAC_STATS_URL, MANUAL_DGAC_PATH, SAMPLES_DIR
from backfill.http_client import RateLimitedClient
from backfill.store import upsert_dgac

logger = logging.getLogger(__name__)

PDF_NAME_RE = re.compile(
    r"tendanCIEL[_-](?P<year>\d{4})[_-](?P<month>\d{2})",
    re.IGNORECASE,
)
DELAY_SHARE_RE = re.compile(
    r"Vols retardés de plus de 15 min\s+([0-9]+,[0-9]+|[0-9]+(?:\.[0-9]+)?)\s*%",
    re.IGNORECASE,
)


def parse_html_pdf_links(html: str, *, base: str = DGAC_STATS_URL) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "tendanciel" not in href.lower() or not href.lower().endswith(".pdf"):
            continue
        url = urljoin(base, href)
        if url in seen:
            continue
        seen.add(url)
        match = PDF_NAME_RE.search(url)
        periode = f"{match.group('year')}-{match.group('month')}" if match else ""
        found.append({"url": url, "periode": periode, "label": anchor.get_text(" ", strip=True)})
    return found


def parse_pdf_text(text: str, *, periode: str, airline: str = "TOUS") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    match = DELAY_SHARE_RE.search(text.replace("\xa0", " "))
    if match:
        share = float(match.group(1).replace(",", "."))
        rows.append(
            {
                "periode": periode,
                "airline": airline,
                "cause": "vols_retardes_plus_15min",
                "share_pct": share,
            }
        )
    return rows


def pdf_bytes_to_text(blob: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io_bytes(blob))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def io_bytes(blob: bytes):
    import io

    return io.BytesIO(blob)


def load_manual(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or MANUAL_DGAC_PATH
    if not target.exists():
        return []
    payload = json.loads(target.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for item in payload:
        if item.get("share_pct") is None:
            continue
        rows.append(
            {
                "periode": item["periode"],
                "airline": item.get("airline") or "AF",
                "cause": item["cause"],
                "share_pct": float(item["share_pct"]),
            }
        )
    return rows


def fetch_html(*, client: RateLimitedClient | None = None, allow_sample: bool = True) -> str:
    http = client or RateLimitedClient(delay_s=0.0, timeout_s=45.0)
    try:
        return http.get_text(DGAC_STATS_URL)
    except Exception as exc:  # noqa: BLE001
        if not allow_sample:
            raise
        logger.warning("Page DGAC indisponible (%s), échantillon figé", exc)
        return (SAMPLES_DIR / "dgac_stats.html").read_text(encoding="utf-8")


def parse(html: str, pdf_texts: dict[str, str] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for link in parse_html_pdf_links(html):
        periode = link["periode"]
        text = (pdf_texts or {}).get(periode) or (pdf_texts or {}).get(link["url"])
        if text and periode:
            rows.extend(parse_pdf_text(text, periode=periode))
    rows.extend(load_manual())
    # Dédupliquer par clé naturelle en gardant la dernière saisie manuelle.
    keyed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        keyed[(row["periode"], row["airline"], row["cause"])] = row
    return list(keyed.values())


def save(rows: list[dict[str, Any]]) -> int:
    return upsert_dgac(rows)


def run(
    *,
    html: str | None = None,
    pdf_texts: dict[str, str] | None = None,
    fetch_pdfs: bool = False,
    allow_sample: bool = True,
) -> dict[str, Any]:
    page = html if html is not None else fetch_html(allow_sample=allow_sample)
    texts = dict(pdf_texts or {})
    if fetch_pdfs:
        http = RateLimitedClient(delay_s=0.4, timeout_s=45.0)
        for link in parse_html_pdf_links(page):
            if not link["periode"] or link["periode"] in texts:
                continue
            try:
                blob = http.get_bytes(link["url"])
                texts[link["periode"]] = pdf_bytes_to_text(blob)
            except Exception as exc:  # noqa: BLE001
                logger.warning("PDF DGAC %s : %s", link["url"], exc)
    if not texts:
        sample_txt = SAMPLES_DIR / "tendanciel_2026_07.txt"
        if sample_txt.exists():
            texts["2026-07"] = sample_txt.read_text(encoding="utf-8")
    parsed = parse(page, texts)
    saved = save(parsed)
    return {"records": saved, "pdfs": sorted(texts)}
