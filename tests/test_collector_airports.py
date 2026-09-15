from __future__ import annotations

from collector.airports_cg import parse
from corridor.settings import ROOT


def test_parse_depart_bzv() -> None:
    html = (ROOT / "collector/data/samples/aeroport_bzv_dep.html").read_text(encoding="utf-8")
    rows = parse(html, page="bzv_dep")
    af = [row for row in rows if row["flight_number"] == "AF754"]
    assert af
    assert af[0]["kind"] == "dep"
    assert af[0]["delay_min"] == 37


def test_parse_arrivee_aller() -> None:
    html = (ROOT / "collector/data/samples/aeroport_bzv_arr.html").read_text(encoding="utf-8")
    rows = parse(html, page="bzv_arr")
    assert rows[0]["kind"] == "arr"
    assert rows[0]["delay_min"] == 37  # 18h12 - 17h35
