"""Couche 3 : fériés / ponts France (0.15) et cause DGAC du mois (0.10)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from corridor.db import connect

from model.classes import shift_up

W_CALENDAR = 0.15
W_DGAC = 0.10
RISKY_CAUSES = {"controle_aerien", "greve", "grève", "compagnie"}


def mark_ponts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pont : férié jeudi → vendredi ; férié mardi → lundi."""
    holidays = {row["date"]: row for row in rows if not row.get("is_pont")}
    existing = {row["date"] for row in rows}
    extra: list[dict[str, Any]] = []
    for day, row in list(holidays.items()):
        weekday = day.isoweekday()
        if weekday == 4:  # jeudi
            friday = day + timedelta(days=1)
            if friday not in existing:
                extra.append({"date": friday, "country": "FR", "label": "pont", "is_pont": True})
                existing.add(friday)
        if weekday == 2:  # mardi
            monday = day - timedelta(days=1)
            if monday not in existing:
                extra.append({"date": monday, "country": "FR", "label": "pont", "is_pont": True})
                existing.add(monday)
    return rows + extra


def calendar_flag(day: date) -> dict[str, Any] | None:
    with connect() as conn:
        return conn.execute(
            "SELECT date, label, is_pont FROM calendar_days WHERE date = %s AND country = 'FR'",
            (day,),
        ).fetchone()


def dgac_shift(day: date) -> tuple[bool, str | None]:
    periode = day.strftime("%Y-%m")
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT cause, share_pct FROM dgac_causes
            WHERE periode = %s AND airline = ANY(%s)
            ORDER BY share_pct DESC NULLS LAST
            """,
            (periode, ["AF", "TOUS"]),
        ).fetchall()
    if not rows:
        return False, None
    top = rows[0]
    cause = top["cause"]
    share = float(top["share_pct"] or 0)
    # Cause AF nommée, ou ponctualité dégradée (plus de 35 % de vols > 15 min).
    risky = cause in RISKY_CAUSES or (cause == "vols_retardes_plus_15min" and share >= 35)
    return risky, cause


def layer3(base: dict[str, float], day: date) -> tuple[dict[str, float], list[str], float]:
    factors: list[str] = []
    cal = calendar_flag(day)
    cal_on = bool(cal)
    if cal:
        if cal["is_pont"]:
            factors.append("Pont en France.")
        else:
            factors.append(f"Férié en France : {cal['label']}.")
    dgac_on, cause = dgac_shift(day)
    if dgac_on and cause:
        if cause == "vols_retardes_plus_15min":
            factors.append("Ponctualité DGAC du mois dégradée.")
        else:
            factors.append(f"Cause DGAC du mois : {cause.replace('_', ' ')}.")
    strength = min(1.0, (W_CALENDAR if cal_on else 0.0) + (W_DGAC if dgac_on else 0.0))
    weight = (W_CALENDAR if cal_on else 0.0) + (W_DGAC if dgac_on else 0.0)
    return shift_up(base, strength), factors, weight
