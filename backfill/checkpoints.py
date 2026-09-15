"""Point de reprise JSON (fenêtres OpenSky déjà traitées)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backfill.constants import STATE_DIR


def state_path(name: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / name


def load_state(name: str) -> dict[str, Any]:
    path = state_path(name)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(name: str, payload: dict[str, Any]) -> None:
    path = state_path(name)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
