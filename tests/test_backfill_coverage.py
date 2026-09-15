from __future__ import annotations

from datetime import date

from backfill.charts import render_html, write_report
from backfill.coverage import evaluate
from backfill.opensky import parse, save
from backfill.sample_flights import build_opensky_sample


def test_critere_six_mois(clean_backfill, tmp_path) -> None:
    raw = build_opensky_sample(date(2025, 9, 15), date(2026, 9, 14))
    rows = parse(raw, source="opensky_sample")
    save(rows)
    report = evaluate()
    assert report["ok"] is True
    by_flight = {item["flight_number"]: item for item in report["flights"]}
    for number in ("AF736", "AF754", "AF722", "AF940"):
        assert by_flight[number]["ok"] is True
        assert by_flight[number]["span_days"] >= 180
        assert by_flight[number]["n"] >= 12

    paths = write_report(output_dir=tmp_path)
    html = (tmp_path / "rapport_backfill.html").read_text(encoding="utf-8")
    assert "Corridor CD" in html
    assert "Couverture par vol" in html
    assert "—" not in html
    assert "–" not in html
    assert "é" in html or "à" in html
    csv_text = (tmp_path / "flight_records.csv").read_text(encoding="utf-8")
    assert "AF754" in csv_text
    assert paths["html"].endswith("rapport_backfill.html")
