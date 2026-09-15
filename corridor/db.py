"""Connexion PostgreSQL via psycopg, sans ORM."""

from __future__ import annotations

import time

import psycopg
from psycopg.rows import dict_row

from corridor.settings import DATABASE_URL


def connect(*, autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        autocommit=autocommit,
    )


def wait_for_db(*, attempts: int = 40, delay_s: float = 0.5) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            with connect(autocommit=True) as conn:
                conn.execute("SELECT 1")
            return
        except Exception as exc:  # noqa: BLE001 - on réessaie jusqu'au délai
            last_error = exc
            time.sleep(delay_s)
    raise RuntimeError(f"PostgreSQL indisponible sur {DATABASE_URL}: {last_error}")
