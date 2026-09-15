from __future__ import annotations

from backfill.constants import SAMPLES_DIR
from backfill.dgac import parse, parse_html_pdf_links, parse_pdf_text, save


def test_liens_tendanciel() -> None:
    html = (SAMPLES_DIR / "dgac_stats.html").read_text(encoding="utf-8")
    links = parse_html_pdf_links(html)
    periodes = {item["periode"] for item in links}
    assert "2026-07" in periodes
    assert "2026-06" in periodes


def test_texte_tendanciel_juillet_2026() -> None:
    text = (SAMPLES_DIR / "tendanciel_2026_07.txt").read_text(encoding="utf-8")
    rows = parse_pdf_text(text, periode="2026-07")
    assert rows == [
        {
            "periode": "2026-07",
            "airline": "TOUS",
            "cause": "vols_retardes_plus_15min",
            "share_pct": 40.3,
        }
    ]


def test_saisie_manuelle_null_ignoree(clean_backfill) -> None:
    html = (SAMPLES_DIR / "dgac_stats.html").read_text(encoding="utf-8")
    text = (SAMPLES_DIR / "tendanciel_2026_07.txt").read_text(encoding="utf-8")
    rows = parse(html, {"2026-07": text})
    airlines = {row["airline"] for row in rows}
    assert "TOUS" in airlines
    assert all(row["share_pct"] is not None for row in rows)
    save(rows)
    n = clean_backfill.execute("SELECT COUNT(*) AS n FROM dgac_causes").fetchone()["n"]
    assert n >= 1
