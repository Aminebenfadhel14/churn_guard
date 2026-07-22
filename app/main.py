"""Point d'entrée de l'API FastAPI de ChurnGuard.

Lancement en développement :
    uvicorn app.main:app --reload

Documentation interactive Swagger sur /docs.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.auth import amorcer_organisation_defaut
from app.config import settings
from app.db import SessionLocal

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Plateforme universelle de prédiction et d'explication "
        "de l'attrition client (churn)."
    ),
)

# CORS : en développement, on autorise toutes les origines (aucun blocage
# possible depuis le navigateur). allow_credentials doit rester False quand
# allow_origins=["*"] (contrainte de la spec CORS). Le frontend n'utilise pas
# de cookies, donc c'est sans impact.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes métier (predict, ...).
app.include_router(api_router)


@app.exception_handler(Exception)
async def gestion_erreur_non_geree(request: Request, exc: Exception) -> JSONResponse:
    """Filet de sécurité : sans handler explicite, une exception non gérée
    contourne CORSMiddleware (elle est traitée au-dessus, avant que ses
    en-têtes aient pu être ajoutés) et le navigateur affiche un "Failed to
    fetch" au lieu du vrai message — ce qui rend le bug invisible.
    """
    logger.exception("Erreur non gérée sur %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Erreur interne du serveur."})


@app.on_event("startup")
def _amorcer_organisation_defaut() -> None:
    """Cree l'organisation "Default" + son admin si la base est vide (voir app/auth/store.py)."""
    db = SessionLocal()
    try:
        amorcer_organisation_defaut(db)
    finally:
        db.close()


@app.get("/health", tags=["Système"])
def health() -> dict[str, str]:
    """Sonde de vivacité : confirme que l'API répond."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }
