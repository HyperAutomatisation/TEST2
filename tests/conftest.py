from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://corridor:corridor@localhost:5432/corridor",
)
os.environ["OURAIRPORTS_USE_SAMPLE"] = "1"

import pytest

from corridor.bootstrap import bootstrap
from corridor.db import connect, wait_for_db


@pytest.fixture(scope="session", autouse=True)
def _prepare_database() -> None:
    wait_for_db()
    bootstrap(replace=True)


@pytest.fixture
def db_conn():
    with connect() as conn:
        yield conn
