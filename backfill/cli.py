"""Point d'entrée : python -m backfill run|charts|coverage."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from corridor.bootstrap import bootstrap
from corridor.db import wait_for_db
from corridor.settings import BACKFILL_MONTHS, OPENSKY_REQUEST_DELAY_S, TIMEZONE

from backfill import atfm, coverage, dgac, mesonet, openmeteo, opensky
from backfill.charts import write_report
from backfill.collection import run_safely
from backfill.constants import OUTPUT_DIR, SAMPLES_DIR, SOURCE_OPENSKY_SAMPLE
from backfill.sample_flights import build_opensky_sample

logger = logging.getLogger(__name__)


def _period(months: int, end: date | None) -> tuple[date, date]:
    last = end or (datetime.now(ZoneInfo(TIMEZONE)).date() - timedelta(days=1))
    first = last - timedelta(days=int(round(months * 30.44)) - 1)
    return first, last


def cmd_run(args: argparse.Namespace) -> int:
    wait_for_db()
    bootstrap(replace=False)
    start, end = _period(args.months, args.end_date)
    sources = [item.strip() for item in args.sources.split(",") if item.strip()]
    summary: dict[str, object] = {"start": start.isoformat(), "end": end.isoformat(), "sources": {}}

    if "opensky" in sources:
        if args.offline:
            raw = build_opensky_sample(start, end)
            summary["sources"]["opensky"] = run_safely(
                "opensky",
                opensky.run,
                start=start,
                end=end,
                offline_rows=raw,
                source=SOURCE_OPENSKY_SAMPLE,
            )
        else:
            summary["sources"]["opensky"] = run_safely(
                "opensky",
                opensky.run,
                start=start,
                end=end,
                delay_s=args.delay,
            )

    om_rows = []
    if "openmeteo" in sources:
        payloads = None
        if args.offline:
            payloads = {
                "CDG": json.loads((SAMPLES_DIR / "openmeteo_cdg.json").read_text(encoding="utf-8")),
                "FIH": json.loads((SAMPLES_DIR / "openmeteo_fih.json").read_text(encoding="utf-8")),
                "BZV": json.loads((SAMPLES_DIR / "openmeteo_bzv.json").read_text(encoding="utf-8")),
                "PNR": json.loads((SAMPLES_DIR / "openmeteo_pnr.json").read_text(encoding="utf-8")),
            }
        result = run_safely("openmeteo", openmeteo.run, start=start, end=end, payloads=payloads)
        summary["sources"]["openmeteo"] = result
        if result.get("status") == "ok":
            # Mesonet compare against what we just stored if needed later.
            om_rows = []

    if args.with_mesonet or "mesonet" in sources:
        csv_text = None
        if args.offline:
            csv_text = (SAMPLES_DIR / "mesonet_lfpg.csv").read_text(encoding="utf-8")
        summary["sources"]["mesonet"] = run_safely(
            "mesonet",
            mesonet.run,
            start=start,
            end=end,
            csv_text=csv_text,
            openmeteo_rows=om_rows,
        )
        meso = summary["sources"]["mesonet"]
        if isinstance(meso, dict) and meso.get("comparison"):
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            path = OUTPUT_DIR / "mesonet_verification.json"
            path.write_text(json.dumps(meso["comparison"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if "atfm" in sources:
        csv_text = None
        if args.offline:
            csv_text = (SAMPLES_DIR / "atfm_apt_dly.csv").read_text(encoding="utf-8")
        summary["sources"]["atfm"] = run_safely(
            "atfm",
            atfm.run,
            start=start,
            end=end,
            csv_text=csv_text,
            allow_sample=args.offline,
        )

    if "dgac" in sources:
        html = None
        pdf_texts = None
        if args.offline:
            html = (SAMPLES_DIR / "dgac_stats.html").read_text(encoding="utf-8")
            pdf_texts = {
                "2026-07": (SAMPLES_DIR / "tendanciel_2026_07.txt").read_text(encoding="utf-8")
            }
        summary["sources"]["dgac"] = run_safely(
            "dgac",
            dgac.run,
            html=html,
            pdf_texts=pdf_texts,
            fetch_pdfs=not args.offline and not args.dry_run,
            allow_sample=True,
            min_periode=start.isoformat()[:7],
        )

    if args.dry_run:
        logger.info("dry-run : les upserts ont tout de même servi les parsers (pas de mode lecture seule SQL)")

    paths = write_report(output_dir=Path(args.output_dir) if args.output_dir else None)
    summary["outputs"] = paths
    summary["coverage"] = coverage.evaluate()
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_charts(args: argparse.Namespace) -> int:
    wait_for_db()
    paths = write_report(output_dir=Path(args.output_dir) if args.output_dir else None)
    print(json.dumps(paths, indent=2, ensure_ascii=False))
    return 0


def cmd_coverage(_args: argparse.Namespace) -> int:
    wait_for_db()
    report = coverage.evaluate()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backfill",
        description="Backfill Corridor CD : OpenSky, Open-Meteo, ATFM, DGAC.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Exécuter le backfill")
    run.add_argument("--offline", action="store_true", help="Échantillons figés, sans secrets")
    run.add_argument("--dry-run", action="store_true", help="Documenter le parcours (upserts de test OK)")
    run.add_argument(
        "--sources",
        default="opensky,openmeteo,atfm,dgac",
        help="Liste séparée par des virgules",
    )
    run.add_argument("--with-mesonet", action="store_true", help="Vérification Iowa Mesonet (optionnelle)")
    run.add_argument("--months", type=int, default=BACKFILL_MONTHS)
    run.add_argument("--end-date", type=date.fromisoformat, default=None)
    run.add_argument("--delay", type=float, default=OPENSKY_REQUEST_DELAY_S)
    run.add_argument("--output-dir", default=str(OUTPUT_DIR))
    run.set_defaults(func=cmd_run)

    charts = sub.add_parser("charts", help="Régénérer le rapport HTML/CSV")
    charts.add_argument("--output-dir", default=str(OUTPUT_DIR))
    charts.set_defaults(func=cmd_charts)

    cov = sub.add_parser("coverage", help="Vérifier le critère 6 mois par vol")
    cov.set_defaults(func=cmd_coverage)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
