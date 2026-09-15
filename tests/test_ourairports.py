from __future__ import annotations

from collector.ourairports import SAMPLE_PATH, parse


def test_parse_echantillon_fige() -> None:
    rows = parse(SAMPLE_PATH.read_text(encoding="utf-8"))
    by_ident = {row["ident"]: row for row in rows}
    assert set(by_ident) == {"FCBB", "FCPP", "FZAA", "LFPG"}
    assert by_ident["LFPG"]["iata_code"] == "CDG"
    assert by_ident["FZAA"]["iata_code"] == "FIH"
    assert by_ident["FCBB"]["iata_code"] == "BZV"
    assert by_ident["FCPP"]["iata_code"] == "PNR"
    assert by_ident["LFPG"]["timezone"] == "Europe/Paris"
    assert by_ident["FCBB"]["timezone"] == "Africa/Brazzaville"
    assert by_ident["FCPP"]["timezone"] == "Africa/Brazzaville"
    assert by_ident["FZAA"]["timezone"] == "Africa/Kinshasa"
