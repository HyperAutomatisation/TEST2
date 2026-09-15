from __future__ import annotations

from collector.socle import build_scheduler, poll_adsb, run_evening
from datetime import datetime
from zoneinfo import ZoneInfo


def test_scheduler_jobs() -> None:
    scheduler = build_scheduler()
    ids = {job.id for job in scheduler.get_jobs()}
    assert ids == {"evening", "closure", "airports_1745", "airports_2045", "adsb_poll"}


def test_un_collecteur_ne_bloque_pas_les_autres(monkeypatch, clean_backfill) -> None:
    def boom(**_kwargs):
        raise RuntimeError("aviationstack down")

    monkeypatch.setattr("collector.aviationstack.run", boom)
    monkeypatch.setattr("collector.adsbdb.run", lambda **_: {"records": 1})
    monkeypatch.setattr("collector.openmeteo_forecast.run", lambda **_: {"records": 2})
    monkeypatch.setattr("collector.awc.run", lambda **_: {"records": 3})
    monkeypatch.setattr("collector.airports_cg.run", lambda **_: {"records": 0})
    summary = run_evening()
    assert summary["sources"]["aviationstack"]["status"] == "error"
    assert summary["sources"]["adsbdb"]["status"] == "ok"
    assert summary["sources"]["awc"]["status"] == "ok"
    n = clean_backfill.execute(
        "SELECT source, status FROM collection_runs ORDER BY source"
    ).fetchall()
    statuses = {row["source"]: row["status"] for row in n}
    assert statuses["aviationstack"] == "error"
    assert statuses["adsbdb"] == "ok"


def test_adsb_sommeil_hors_fenetre() -> None:
    now = datetime(2026, 9, 15, 11, 0, tzinfo=ZoneInfo("Africa/Brazzaville"))
    result = poll_adsb(now)
    assert result.get("skipped") == "hors_fenetre"
