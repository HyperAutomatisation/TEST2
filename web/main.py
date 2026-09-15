"""FastAPI : pages publiques et API JSON v1, sans compte ni cookie de suivi."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from corridor.bootstrap import bootstrap
from corridor.db import wait_for_db
from corridor.flights import payload_vol_du_jour
from web.queries import (
    SEO_DESCRIPTION,
    SEO_TITLE,
    barometre,
    fiabilite_payload,
    meilleur_jour_payload,
    minutes,
    pct,
    vol_payload,
)

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
TEMPLATES.env.globals["seo_title"] = SEO_TITLE
TEMPLATES.env.globals["seo_description"] = SEO_DESCRIPTION
TEMPLATES.env.globals["pct"] = pct
TEMPLATES.env.globals["minutes"] = minutes


@asynccontextmanager
async def lifespan(_app: FastAPI):
    wait_for_db()
    bootstrap(replace=False)
    yield


app = FastAPI(
    title="Corridor CD",
    description=(
        "Prédiction du fret aérien Congo vers Paris CDG. "
        "API publique en usage raisonnable : pas de moissonnage agressif, "
        "pas de compte, pas de paiement, pas de cookie de suivi."
    ),
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1")
def api_index() -> dict:
    return {
        "name": "Corridor CD",
        "usage": "API publique, usage raisonnable.",
        "endpoints": {
            "/api/v1/vol-du-jour": "Vols de la grille pour une date",
            "/api/v1/barometre": "Baromètre des 7 prochains jours",
            "/api/v1/vol/{flight_number}": "Statut, distribution, entrepôt, historique 90 j",
            "/api/v1/meilleur-jour": "Classement des jours par ponctualité",
            "/api/v1/fiabilite": "Score de Brier vs prédiction naïve",
        },
    }


@app.get("/api/v1/vol-du-jour")
def api_vol_du_jour(
    date_param: date | None = Query(default=None, alias="date"),
) -> dict:
    return payload_vol_du_jour(date_param)


@app.get("/api/v1/barometre")
def api_barometre(
    date_param: date | None = Query(default=None, alias="date"),
) -> dict:
    return barometre(date_param)


@app.get("/api/v1/vol/{flight_number}")
def api_vol(
    flight_number: str,
    date_param: date | None = Query(default=None, alias="date"),
) -> dict:
    payload = vol_payload(flight_number, date_param)
    if payload is None:
        raise HTTPException(status_code=404, detail="Vol inconnu sur le corridor")
    return payload


@app.get("/api/v1/meilleur-jour")
def api_meilleur_jour(
    date_param: date | None = Query(default=None, alias="date"),
) -> dict:
    return meilleur_jour_payload(date_param)


@app.get("/api/v1/fiabilite")
def api_fiabilite() -> dict:
    return fiabilite_payload()


@app.get("/", response_class=HTMLResponse)
def accueil(request: Request, date_param: date | None = Query(default=None, alias="date")):
    payload = barometre(date_param)
    grille = payload_vol_du_jour(date_param)
    return TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {"payload": payload, "grille": grille},
    )


@app.get("/vol/{flight_number}", response_class=HTMLResponse)
def page_vol(
    request: Request,
    flight_number: str,
    date_param: date | None = Query(default=None, alias="date"),
):
    payload = vol_payload(flight_number, date_param)
    if payload is None:
        raise HTTPException(status_code=404, detail="Vol inconnu sur le corridor")
    return TEMPLATES.TemplateResponse(request, "vol.html", {"payload": payload, "chart": True})


@app.get("/meilleur-jour", response_class=HTMLResponse)
def page_meilleur_jour(
    request: Request, date_param: date | None = Query(default=None, alias="date")
):
    payload = meilleur_jour_payload(date_param)
    return TEMPLATES.TemplateResponse(request, "meilleur_jour.html", {"payload": payload})


@app.get("/fiabilite", response_class=HTMLResponse)
def page_fiabilite(request: Request):
    payload = fiabilite_payload()
    return TEMPLATES.TemplateResponse(request, "fiabilite.html", {"payload": payload})
