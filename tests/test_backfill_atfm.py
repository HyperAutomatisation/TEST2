from __future__ import annotations

from datetime import date

from backfill.atfm import parse, save
from backfill.constants import SAMPLES_DIR


def test_parse_atfm_uniquement_cdg() -> None:
    text = (SAMPLES_DIR / "atfm_apt_dly.csv").read_text(encoding="utf-8")
    rows = parse(text)
    airports = {row["airport"] for row in rows}
    assert airports == {"CDG"}
    by_date = {row["date"]: row for row in rows}
    assert by_date[date(2025, 9, 1)]["delay_avg_min"] == 2.0  # 2360 / 1180
    assert by_date[date(2025, 9, 3)]["delay_avg_min"] == 0.0
    assert by_date[date(2026, 7, 12)]["delay_avg_min"] == 4.0  # 5000 / 1250


def test_save_atfm(clean_backfill) -> None:
    text = (SAMPLES_DIR / "atfm_apt_dly.csv").read_text(encoding="utf-8")
    rows = parse(text)
    assert save(rows) == len(rows)
    n = clean_backfill.execute("SELECT COUNT(*) AS n FROM atfm_delays").fetchone()["n"]
    assert n == len(rows)
