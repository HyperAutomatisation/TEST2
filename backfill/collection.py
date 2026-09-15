"""Journal collection_runs : un collecteur qui échoue ne bloque pas les autres."""

from __future__ import annotations

from typing import Any

from corridor.db import connect


def log_run(source: str, status: str, records_fetched: int | None = None, error: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO collection_runs (source, status, records_fetched, error)
            VALUES (%s, %s, %s, %s)
            """,
            (source, status, records_fetched, error),
        )
        conn.commit()


def run_safely(run_name: str, fn, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        result = fn(*args, **kwargs)
        count = result.get("records") if isinstance(result, dict) else result
        log_run(run_name, "ok", records_fetched=int(count or 0))
        if isinstance(result, dict):
            result.setdefault("status", "ok")
            return result
        return {"status": "ok", "records": int(result or 0)}
    except Exception as exc:  # noqa: BLE001 - journaliser, ne pas tout arrêter
        log_run(run_name, "error", error=str(exc))
        return {"status": "error", "records": 0, "error": str(exc)}
