from __future__ import annotations

from backfill.cli import build_parser, main


def test_cli_aide() -> None:
    parser = build_parser()
    args = parser.parse_args(["run", "--offline", "--months", "12", "--sources", "opensky"])
    assert args.offline is True
    assert args.months == 12


def test_cli_coverage_apres_offline(clean_backfill, capsys) -> None:
    code = main(
        [
            "run",
            "--offline",
            "--sources",
            "opensky,openmeteo,atfm,dgac",
            "--months",
            "12",
            "--end-date",
            "2026-09-14",
        ]
    )
    assert code == 0
    coverage_code = main(["coverage"])
    assert coverage_code == 0
    captured = capsys.readouterr().out
    assert "AF736" in captured
