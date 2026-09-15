"""Couche 2 : retard hérité (poids 0.55) et météo (poids 0.20)."""

from __future__ import annotations

from datetime import date

from corridor.db import connect

from model.classes import shift_up

W_INHERITED = 0.55
W_WEATHER = 0.20


def inherited_delay_min(day: date, aircraft_reg: str | None = None) -> int | None:
    with connect() as conn:
        row = None
        if aircraft_reg:
            row = conn.execute(
                """
                SELECT retard_troncon_aller_min FROM aircraft_rotations
                WHERE date = %s AND aircraft_reg = %s
                """,
                (day, aircraft_reg),
            ).fetchone()
            if row and row["retard_troncon_aller_min"] is not None:
                return int(row["retard_troncon_aller_min"])
        row = conn.execute(
            """
            SELECT retard_troncon_aller_min FROM aircraft_rotations
            WHERE date = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (day,),
        ).fetchone()
    if row and row["retard_troncon_aller_min"] is not None:
        return int(row["retard_troncon_aller_min"])
    return None


def weather_risk(day: date) -> bool:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT bool_or(risk_storm) AS storm,
                   min(vis_km) FILTER (WHERE airport = 'CDG') AS vis_cdg
            FROM weather
            WHERE date = %s AND airport = ANY(%s)
            """,
            (day, ["CDG", "FIH", "BZV", "PNR"]),
        ).fetchone()
    if not row:
        return False
    if row["storm"]:
        return True
    vis = row["vis_cdg"]
    return vis is not None and float(vis) < 3.0


def layer2(
    base: dict[str, float], *, inherited: int | None, storm: bool
) -> tuple[dict[str, float], list[str], float]:
    factors: list[str] = []
    inh_strength = 0.0
    if inherited and inherited > 0:
        inh_strength = min(1.0, inherited / 90.0)
        factors.append(f"Retard hérité de l'aller : {inherited} min.")
    wx_strength = 1.0 if storm else 0.0
    if storm:
        factors.append("Météo : orage ou mauvaise visibilité sur le corridor.")
    strength = min(1.0, W_INHERITED * inh_strength + W_WEATHER * wx_strength)
    weight = (W_INHERITED if inh_strength else 0.0) + (W_WEATHER if storm else 0.0)
    return shift_up(base, strength), factors, weight
