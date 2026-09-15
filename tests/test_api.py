from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from tests.expected import ATTENDU_PAR_JOUR, DATES_SAISON
from web.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _tuples(payload: dict) -> list[tuple[str, str, str, str]]:
    return [
        (
            vol["flight_number"],
            vol["departure_airport"],
            vol["sched_dep_local"],
            vol["sched_arr_cdg"],
        )
        for vol in payload["flights"]
    ]


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize("weekday", sorted(ATTENDU_PAR_JOUR))
def test_api_vol_du_jour_selon_la_grille(client: TestClient, weekday: int) -> None:
    jour = DATES_SAISON[weekday]
    response = client.get("/api/v1/vol-du-jour", params={"date": jour})
    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == jour
    assert payload["weekday"] == weekday
    assert _tuples(payload) == ATTENDU_PAR_JOUR[weekday]


def test_api_mardi_15_septembre_2026(client: TestClient) -> None:
    """Ancre : le 15 septembre 2026 est un mardi, vol AF754 selon la section 4."""
    response = client.get("/api/v1/vol-du-jour", params={"date": "2026-09-15"})
    payload = response.json()
    assert date.fromisoformat(payload["date"]).isoweekday() == 2
    assert payload["weekday_label"] == "mardi"
    assert [vol["flight_number"] for vol in payload["flights"]] == ["AF754"]


def test_page_accueil_en_francais(client: TestClient) -> None:
    response = client.get("/", params={"date": "2026-09-15"})
    assert response.status_code == 200
    body = response.text
    assert "Corridor CD" in body
    assert "mardi" in body
    assert "AF 754" in body
    assert "19h05" in body
    assert "—" not in body
    assert "–" not in body
