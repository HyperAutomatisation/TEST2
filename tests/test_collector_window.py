from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from collector.window import in_flight_window


def test_fenetre_nuit_et_matin() -> None:
    tz = ZoneInfo("Africa/Brazzaville")
    assert in_flight_window(datetime(2026, 9, 15, 19, 0, tzinfo=tz)) is True
    assert in_flight_window(datetime(2026, 9, 15, 18, 59, tzinfo=tz)) is False
    assert in_flight_window(datetime(2026, 9, 16, 7, 15, tzinfo=tz)) is True
    assert in_flight_window(datetime(2026, 9, 16, 7, 16, tzinfo=tz)) is False
    assert in_flight_window(datetime(2026, 9, 16, 2, 0, tzinfo=tz)) is True
