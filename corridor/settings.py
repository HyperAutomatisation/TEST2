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
# OpenSky exige OAuth2 (client credentials) depuis mars 2026.
# USER/PASS restent lus : si CLIENT_ID/SECRET sont vides, on tente USER/PASS
# comme identifiants de client (certains dépôts y collent le couple OAuth2).
OPENSKY_CLIENT_ID = os.environ.get("OPENSKY_CLIENT_ID", "")
OPENSKY_CLIENT_SECRET = os.environ.get("OPENSKY_CLIENT_SECRET", "")
OPENSKY_REQUEST_DELAY_S = float(os.environ.get("OPENSKY_REQUEST_DELAY_S", "10"))
BACKFILL_MONTHS = int(os.environ.get("BACKFILL_MONTHS", "12"))
COLLECTORS_USE_SAMPLE = os.environ.get("COLLECTORS_USE_SAMPLE", "") == "1"
AVIATIONSTACK_MAX_REQ_PER_DAY = int(os.environ.get("AVIATIONSTACK_MAX_REQ_PER_DAY", "4"))
