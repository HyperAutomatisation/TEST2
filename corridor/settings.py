"""Paramètres d'environnement. Les secrets restent dans .env, jamais en dur."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://corridor:corridor@localhost:5432/corridor",
)
TIMEZONE = os.environ.get("TIMEZONE", "Africa/Brazzaville")
OURAIRPORTS_URL = os.environ.get(
    "OURAIRPORTS_URL",
    "https://davidmegginson.github.io/ourairports-data/airports.csv",
)
AVIATIONSTACK_KEY = os.environ.get("AVIATIONSTACK_KEY", "")
OPENSKY_USER = os.environ.get("OPENSKY_USER", "")
OPENSKY_PASS = os.environ.get("OPENSKY_PASS", "")
