from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from backfill.opensky import parse, save
from backfill.sample_flights import build_opensky_sample
from model.predict import generate_range
from web.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_pages(clean_backfill):
    raw = build_opensky_sample(date(2026, 6, 1), date(2026, 9, 20))
    save(parse(raw, source="opensky_sample"))
    generate_range(date(2026, 8, 1), date(2026, 9, 20))
    return clean_backfill


def _no_tracking(response) -> None:
    assert "set-cookie" not in {key.lower() for key in response.headers}
    body = response.text
    assert "—" not in body
    assert "–" not in body


def test_api_index_usage_raisonnable(client: TestClient) -> None:
    response = client.get("/api/v1")
    assert response.status_code == 200
    payload = response.json()
    assert "usage raisonnable" in payload["usage"]
    assert "/api/v1/barometre" in payload["endpoints"]


def test_pages_cles_et_api(client: TestClient, sample_pages) -> None:
    home = client.get("/", params={"date": "2026-09-15"})
    assert home.status_code == 200
    assert "suivi fret aérien Congo Brazzaville Pointe-Noire Paris" in home.text
    assert "AF 754" in home.text
    assert "19h05" in home.text
    assert "mardi" in home.text
    assert "Baromètre des 7 prochains jours" in home.text
    _no_tracking(home)

    vol = client.get("/vol/AF754", params={"date": "2026-09-15"})
    assert vol.status_code == 200
    assert "Distribution de probabilité" in vol.text
    assert "estimation v1" in vol.text
    assert "Historique 90 jours" in vol.text
    _no_tracking(vol)

    meilleur = client.get("/meilleur-jour", params={"date": "2026-09-15"})
    assert meilleur.status_code == 200
    assert "Meilleur jour d'expédition" in meilleur.text
    assert "Kinshasa" in meilleur.text
    _no_tracking(meilleur)

    fiab = client.get("/fiabilite")
    assert fiab.status_code == 200
    assert "Brier" in fiab.text
    _no_tracking(fiab)

    baro = client.get("/api/v1/barometre", params={"date": "2026-09-15"})
    assert baro.status_code == 200
    payload = baro.json()
    assert len(payload["days"]) == 7
    assert payload["days"][0]["flights"][0]["flight_number"] == "AF754"
    pred = payload["signature"]["prediction"]
    assert pred is not None
    total = sum(pred["probs"].values())
    assert abs(total - 1.0) < 1e-6

    api_vol = client.get("/api/v1/vol/AF754", params={"date": "2026-09-15"})
    assert api_vol.status_code == 200
    body = api_vol.json()
    assert body["flight_number"] == "AF754"
    assert body["warehouse"]["disclaimer"]
    assert body["history_90d"]

    api_fiab = client.get("/api/v1/fiabilite")
    assert api_fiab.status_code == 200
    scored = api_fiab.json()
    assert scored["n"] >= 1
    assert scored["beats_naive"] is True

    assert client.get("/vol/AF000").status_code == 404
    assert client.get("/api/v1/vol/AF000").status_code == 404
