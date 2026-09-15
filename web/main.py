"""FastAPI : page d'accueil et API JSON du vol du jour."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from corridor.bootstrap import bootstrap
from corridor.db import wait_for_db
from corridor.flights import payload_vol_du_jour

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    wait_for_db()
    bootstrap(replace=False)
    yield


app = FastAPI(
    title="Corridor CD",
    description="Prédiction du fret aérien Congo vers Paris CDG. Usage raisonnable de l'API publique.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/vol-du-jour")
def api_vol_du_jour(
    date_param: date | None = Query(default=None, alias="date"),
) -> dict:
    return payload_vol_du_jour(date_param)


@app.get("/", response_class=HTMLResponse)
def accueil(request: Request, date_param: date | None = Query(default=None, alias="date")):
    payload = payload_vol_du_jour(date_param)
    return TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {"payload": payload},
    )
