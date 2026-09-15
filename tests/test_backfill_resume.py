from __future__ import annotations

from backfill.checkpoints import load_state, save_state, state_path
from backfill.opensky import credentials_configured


def test_reprise_checkpoint(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("backfill.checkpoints.STATE_DIR", tmp_path)
    save_state("opensky.json", {"done": ["arrival:LFPG:2026-01-01"]})
    state = load_state("opensky.json")
    assert "arrival:LFPG:2026-01-01" in state["done"]
    assert (tmp_path / "opensky.json").exists()
    assert state_path("opensky.json").parent == tmp_path


def test_credentials_absents_sans_invention() -> None:
    # Pas de secrets dans l'environnement de test : le live OpenSky doit refuser.
    assert credentials_configured() is False
