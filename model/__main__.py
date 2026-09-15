"""CLI du modèle : génération hors ligne et score de Brier."""

from __future__ import annotations

import argparse
from datetime import date

from corridor.bootstrap import bootstrap
from corridor.db import connect, wait_for_db
from model.brier import score_database
from model.predict import generate_for_date, generate_range


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Modèle Corridor CD (3 couches + Brier)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    gen = sub.add_parser("generate", help="Générer les prédictions v1")
    gen.add_argument("--date", type=_parse_date, default=None)
    gen.add_argument("--from-date", type=_parse_date, default=None)
    gen.add_argument("--to-date", type=_parse_date, default=None)
    gen.add_argument(
        "--from-records",
        action="store_true",
        help="Une prédiction par date présente dans flight_records",
    )
    sub.add_parser("brier", help="Score de Brier vs naïve sur les prédictions en base")
    args = parser.parse_args()
    wait_for_db()
    bootstrap(replace=False)
    if args.cmd == "generate":
        if args.from_records:
            with connect() as conn:
                rows = conn.execute(
                    "SELECT MIN(date) AS a, MAX(date) AS b FROM flight_records"
                ).fetchone()
            if not rows or not rows["a"]:
                print("aucune observation")
                return
            result = generate_range(rows["a"], rows["b"])
        elif args.from_date and args.to_date:
            result = generate_range(args.from_date, args.to_date)
        else:
            result = generate_for_date(args.date)
        print(result)
        return
    print(score_database())


if __name__ == "__main__":
    main()
