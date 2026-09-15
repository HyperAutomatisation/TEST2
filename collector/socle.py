"""Socle de collecte quotidienne : run_evening 21h, run_closure 9h30, polling adsb."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from corridor.settings import TIMEZONE

from backfill.collection import run_safely
from collector import adsblol, adsbdb, airports_cg, aviationstack, awc, nager, openmeteo_forecast
from collector.window import in_flight_window
from model.predict import generate_for_date
from notify import send

logger = logging.getLogger(__name__)


def run_evening(day=None) -> dict:
    """Collecte 21h : AviationStack, adsbdb, Open-Meteo, AWC, aéroports."""
    summary = {
        "job": "run_evening",
        "at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
        "sources": {},
    }
    summary["sources"]["aviationstack"] = run_safely("aviationstack", aviationstack.run, day=day)
    summary["sources"]["adsbdb"] = run_safely("adsbdb", adsbdb.run)
    summary["sources"]["openmeteo"] = run_safely("openmeteo_forecast", openmeteo_forecast.run)
    summary["sources"]["awc"] = run_safely("awc", awc.run)
    summary["sources"]["airports_cg"] = run_safely("airports_cg", airports_cg.run, day=day)
    summary["sources"]["nager"] = run_safely("nager", nager.run)
    resolved = day or datetime.now(ZoneInfo(TIMEZONE)).date()
    summary["sources"]["model"] = run_safely("model_evening", generate_for_date, resolved)
    alerts = []
    av = summary["sources"]["aviationstack"]
    if isinstance(av, dict):
        alerts = av.get("alerts") or []
    for message in alerts:
        send("log", None, "changement de saison", message)
    return summary


def run_closure(day=None) -> dict:
    """Clôture 9h30 : heures réelles AviationStack + METAR du matin."""
    summary = {
        "job": "run_closure",
        "at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
        "sources": {},
    }
    summary["sources"]["aviationstack"] = run_safely("aviationstack_closure", aviationstack.run, day=day)
    summary["sources"]["awc"] = run_safely("awc_closure", awc.run)
    summary["sources"]["airports_cg"] = run_safely("airports_cg_closure", airports_cg.run, day=day)
    resolved = day or datetime.now(ZoneInfo(TIMEZONE)).date()
    yesterday = resolved - timedelta(days=1)
    summary["sources"]["model"] = run_safely("model_closure", generate_for_date, yesterday)
    return summary


def poll_adsb(now: datetime | None = None) -> dict:
    """Polling 5 min uniquement dans la fenêtre 19h00-07h15, sinon sommeil."""
    if not in_flight_window(now):
        logger.info("adsb.lol : hors fenêtre de vol, sommeil")
        return {"records": 0, "skipped": "hors_fenetre"}
    return run_safely("adsblol", adsblol.run, now=now)


def build_scheduler():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    tz = TIMEZONE
    scheduler = BlockingScheduler(timezone=tz)
    scheduler.add_job(run_evening, CronTrigger(hour=21, minute=0, timezone=tz), id="evening")
    scheduler.add_job(run_closure, CronTrigger(hour=9, minute=30, timezone=tz), id="closure")
    scheduler.add_job(
        airports_cg.run,
        CronTrigger(hour=17, minute=45, timezone=tz),
        id="airports_1745",
    )
    scheduler.add_job(
        airports_cg.run,
        CronTrigger(hour=20, minute=45, timezone=tz),
        id="airports_2045",
    )
    scheduler.add_job(poll_adsb, IntervalTrigger(minutes=5, timezone=tz), id="adsb_poll")
    return scheduler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from corridor.bootstrap import bootstrap
    from corridor.db import wait_for_db

    wait_for_db()
    bootstrap(replace=False)
    scheduler = build_scheduler()
    logger.info("Socle collecteurs : 21h, 9h30, adsb 5 min (fenêtre 19h-07h15)")
    scheduler.start()


if __name__ == "__main__":
    main()
