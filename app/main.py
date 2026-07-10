"""Point d'entrée de l'API FastAPI de ChurnGuard.

Lancement en développement :
    uvicorn app.main:app --reload

Documentation interactive Swagger sur /docs.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.config import settings

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


@app.get("/health", tags=["Système"])
def health() -> dict[str, str]:
    """Sonde de vivacité : confirme que l'API répond."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }
