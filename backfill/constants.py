"""Constantes du corridor pour le backfill. Le mapping jour → vol reste dans ref_flights."""

from __future__ import annotations

from pathlib import Path

from corridor.settings import ROOT

# Callsigns ADS-B / OpenSky (ICAO) → numéro IATA stocké en base.
CALLSIGN_TO_FLIGHT = {
    "AFR736": "AF736",
    "AFR754": "AF754",
    "AFR722": "AF722",
    "AFR940": "AF940",
}
FLIGHT_NUMBERS = tuple(sorted(set(CALLSIGN_TO_FLIGHT.values())))

# OpenSky exige l'ICAO. Le cahier cite CDG/BZV (IATA) : on traduit.
AIRPORT_IATA_TO_ICAO = {
    "CDG": "LFPG",
    "FIH": "FZAA",
    "BZV": "FCBB",
    "PNR": "FCPP",
}
AIRPORT_ICAO_TO_IATA = {icao: iata for iata, icao in AIRPORT_IATA_TO_ICAO.items()}

# Coordonnées du cahier des charges, section 7.6 (secours si ref_airports vide).
AIRPORT_COORDS = {
    "CDG": (49.0097, 2.5479),
    "FIH": (-4.3030, 15.3020),
    "BZV": (-4.2516, 15.2629),
    "PNR": (-4.8236, 11.8894),
}

AIRPORT_TIMEZONES = {
    "CDG": "Europe/Paris",
    "FIH": "Africa/Kinshasa",
    "BZV": "Africa/Brazzaville",
    "PNR": "Africa/Brazzaville",
}

# Codes WMO orage (Open-Meteo weather_code).
STORM_WEATHER_CODES = frozenset({95, 96, 99})

OPENSKY_API = "https://opensky-network.org/api"
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)
# Fenêtre max documentée aujourd'hui : 2 jours, 1 jour UTC calendaire côté client officiel.
# Le cahier parlait de 7 jours : l'API a resserré. On reste sur 1 jour UTC (crédits minimes).
OPENSKY_WINDOW_HOURS = 24

OPENMETEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OPENMETEO_HISTORICAL_FORECAST = "https://historical-forecast-api.open-meteo.com/v1/forecast"

MESONET_ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

ATFM_AIRPORT_ICAO = "LFPG"
ATFM_URL_CANDIDATES = (
    "https://ansperformance.eu/download/csv/apt_dly_{year}.csv.bz2",
    "https://ansperformance.eu/download/csv/apt_dly_{year}.csv",
    "https://www.eurocontrol.int/prudata/dashboard/data/csv/apt_dly_{year}.csv.bz2",
)

DGAC_STATS_URL = (
    "https://www.ecologie.gouv.fr/politiques-publiques/statistiques-du-trafic-aerien"
)

DATA_DIR = ROOT / "backfill" / "data"
SAMPLES_DIR = DATA_DIR / "samples"
INCOMING_DIR = DATA_DIR / "incoming"
STATE_DIR = ROOT / "backfill" / ".state"
OUTPUT_DIR = ROOT / "backfill" / "output"
MANUAL_DGAC_PATH = DATA_DIR / "dgac_causes.manual.json"

SOURCE_OPENSKY = "opensky"
SOURCE_OPENSKY_SAMPLE = "opensky_sample"
SOURCE_OPENMETEO = "openmeteo"
SOURCE_ATFM = "eurocontrol_atfm"
SOURCE_DGAC = "dgac"


def data_path(*parts: str) -> Path:
    return DATA_DIR.joinpath(*parts)
