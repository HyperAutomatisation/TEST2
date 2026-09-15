"""Écritures SQL simples (upsert) vers les tables du chantier 2."""

from __future__ import annotations

from typing import Any

from corridor.db import connect


def upsert_flight_records(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO flight_records (
            date, flight_number, sched_dep, actual_dep, sched_arr_cdg,
            actual_arr_cdg, delay_min, aircraft_reg, itinerary, source
        )
        VALUES (
            %(date)s, %(flight_number)s, %(sched_dep)s, %(actual_dep)s,
            %(sched_arr_cdg)s, %(actual_arr_cdg)s, %(delay_min)s,
            %(aircraft_reg)s, %(itinerary)s, %(source)s
        )
        ON CONFLICT (date, flight_number, source) DO UPDATE SET
            sched_dep = COALESCE(EXCLUDED.sched_dep, flight_records.sched_dep),
            actual_dep = COALESCE(EXCLUDED.actual_dep, flight_records.actual_dep),
            sched_arr_cdg = COALESCE(EXCLUDED.sched_arr_cdg, flight_records.sched_arr_cdg),
            actual_arr_cdg = COALESCE(EXCLUDED.actual_arr_cdg, flight_records.actual_arr_cdg),
            delay_min = COALESCE(EXCLUDED.delay_min, flight_records.delay_min),
            aircraft_reg = COALESCE(EXCLUDED.aircraft_reg, flight_records.aircraft_reg),
            itinerary = COALESCE(EXCLUDED.itinerary, flight_records.itinerary)
    """
    with connect() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
        conn.commit()
    return len(rows)


def upsert_weather(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO weather (
            date, airport, forecast_bool, precip_mm, vis_km, wind_kmh, risk_storm
        )
        VALUES (
            %(date)s, %(airport)s, %(forecast_bool)s, %(precip_mm)s,
            %(vis_km)s, %(wind_kmh)s, %(risk_storm)s
        )
        ON CONFLICT (date, airport, forecast_bool) DO UPDATE SET
            precip_mm = EXCLUDED.precip_mm,
            vis_km = COALESCE(EXCLUDED.vis_km, weather.vis_km),
            wind_kmh = EXCLUDED.wind_kmh,
            risk_storm = EXCLUDED.risk_storm
    """
    with connect() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
        conn.commit()
    return len(rows)


def upsert_atfm(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO atfm_delays (date, airport, delay_avg_min)
        VALUES (%(date)s, %(airport)s, %(delay_avg_min)s)
        ON CONFLICT (date, airport) DO UPDATE SET
            delay_avg_min = EXCLUDED.delay_avg_min
    """
    with connect() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
        conn.commit()
    return len(rows)


def upsert_rotations(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO aircraft_rotations (date, aircraft_reg, retard_troncon_aller_min)
        VALUES (%(date)s, %(aircraft_reg)s, %(retard_troncon_aller_min)s)
        ON CONFLICT (date, aircraft_reg) DO UPDATE SET
            retard_troncon_aller_min = COALESCE(
                EXCLUDED.retard_troncon_aller_min,
                aircraft_rotations.retard_troncon_aller_min
            )
    """
    with connect() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
        conn.commit()
    return len(rows)


def insert_adsb_snapshots(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO adsb_snapshots (
            seen_at, callsign, flight_number, lat, lon, alt_baro, gs, track,
            seen_pos, inferred_event
        )
        VALUES (
            %(seen_at)s, %(callsign)s, %(flight_number)s, %(lat)s, %(lon)s,
            %(alt_baro)s, %(gs)s, %(track)s, %(seen_pos)s, %(inferred_event)s
        )
    """
    with connect() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
        conn.commit()
    return len(rows)


def upsert_calendar(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO calendar_days (date, country, label, is_pont)
        VALUES (%(date)s, %(country)s, %(label)s, %(is_pont)s)
        ON CONFLICT (date, country) DO UPDATE SET
            label = EXCLUDED.label,
            is_pont = EXCLUDED.is_pont
    """
    with connect() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
        conn.commit()
    return len(rows)


def upsert_predictions(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO predictions (
            date, flight_number, model_version,
            p_0_15, p_15_30, p_30_60, p_60_120, p_120_plus, p_cancel,
            factors_json
        )
        VALUES (
            %(date)s, %(flight_number)s, %(model_version)s,
            %(p_0_15)s, %(p_15_30)s, %(p_30_60)s, %(p_60_120)s,
            %(p_120_plus)s, %(p_cancel)s, %(factors_json)s
        )
        ON CONFLICT (date, flight_number, model_version) DO UPDATE SET
            p_0_15 = EXCLUDED.p_0_15,
            p_15_30 = EXCLUDED.p_15_30,
            p_30_60 = EXCLUDED.p_30_60,
            p_60_120 = EXCLUDED.p_60_120,
            p_120_plus = EXCLUDED.p_120_plus,
            p_cancel = EXCLUDED.p_cancel,
            factors_json = EXCLUDED.factors_json,
            created_at = NOW()
    """
    with connect() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
        conn.commit()
    return len(rows)


def upsert_dgac(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO dgac_causes (periode, airline, cause, share_pct)
        VALUES (%(periode)s, %(airline)s, %(cause)s, %(share_pct)s)
        ON CONFLICT (periode, airline, cause) DO UPDATE SET
            share_pct = EXCLUDED.share_pct
    """
    with connect() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
        conn.commit()
    return len(rows)
