"""Outils du Retention Copilot : enrobage des endpoints ChurnGuard existants.

Chaque fonction appelle l'API FastAPI locale (via httpx) et renvoie le JSON.
Aucune logique métier n'est dupliquée : on réutilise le backend tel quel.
La configuration (URL de l'API, clé) vient de ``app.config.settings``.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

import httpx

from app.config import settings

# Délai par défaut ; l'entraînement n'est pas appelé ici, ces endpoints sont rapides.
TIMEOUT_DEFAUT = 30.0

# Token de session de l'utilisateur courant, à propager aux appels HTTP internes
# du copilot : sans lui, les sous-requêtes (/predict, /dashboard…) seraient
# résolues en accès clé API (modèle global) et un opérateur verrait les données
# d'un autre. On le fixe depuis l'endpoint copilot (même thread, synchrone).
_token_session: ContextVar[str | None] = ContextVar("copilot_token_session", default=None)


def definir_token_session(token: str | None) -> None:
    """Fixe le token de session à transmettre aux appels d'outils du copilot."""
    _token_session.set(token)


class OutilChurnGuardError(RuntimeError):
    """Erreur lors de l'appel à un endpoint ChurnGuard (réseau ou statut != 200)."""


def _headers() -> dict[str, str]:
    """En-têtes HTTP : clé API si configurée + token de session s'il est présent.

    Le token de session (Bearer) fait que les endpoints appelés résolvent le
    bon utilisateur et servent donc son modèle personnel (isolation par
    opérateur), et non le modèle global.
    """
    entetes = {"Content-Type": "application/json"}
    if settings.api_key and settings.api_key != "change-me-please":
        entetes["x-api-key"] = settings.api_key
    token = _token_session.get()
    if token:
        entetes["Authorization"] = f"Bearer {token}"
    return entetes


def _post(chemin: str, payload: dict[str, Any], timeout: float = TIMEOUT_DEFAUT) -> dict[str, Any]:
    """POST vers l'API ChurnGuard ; lève ``OutilChurnGuardError`` en cas de souci."""
    url = f"{settings.api_base_url}{chemin}"
    try:
        with httpx.Client() as client:
            reponse = client.post(url, json=payload, headers=_headers(), timeout=timeout)
    except httpx.RequestError as exc:
        raise OutilChurnGuardError(
            f"API injoignable ({url}). L'API FastAPI est-elle démarrée ? Détail : {exc}"
        ) from exc
    if reponse.status_code != 200:
        raise OutilChurnGuardError(f"{chemin} a renvoyé {reponse.status_code} : {reponse.text}")
    return reponse.json()


def _get(
    chemin: str,
    params: dict[str, Any] | None = None,
    timeout: float = TIMEOUT_DEFAUT,
) -> dict[str, Any]:
    """GET vers l'API ChurnGuard ; lève ``OutilChurnGuardError`` en cas de souci."""
    url = f"{settings.api_base_url}{chemin}"
    try:
        with httpx.Client() as client:
            reponse = client.get(url, params=params, headers=_headers(), timeout=timeout)
    except httpx.RequestError as exc:
        raise OutilChurnGuardError(
            f"API injoignable ({url}). L'API FastAPI est-elle démarrée ? Détail : {exc}"
        ) from exc
    if reponse.status_code != 200:
        raise OutilChurnGuardError(f"{chemin} a renvoyé {reponse.status_code} : {reponse.text}")
    return reponse.json()


# ----- Outils exposés à l'orchestrateur -----

def predire(client: dict[str, Any]) -> dict[str, Any]:
    """Score de churn d'un client (POST /predict)."""
    return _post("/predict", client)


def expliquer(client: dict[str, Any], top_k: int = 5) -> dict[str, Any]:
    """Facteurs SHAP de la prédiction (POST /explain)."""
    return _post("/explain", {**client, "top_k": top_k})


def recommander(client: dict[str, Any]) -> dict[str, Any]:
    """Actions + plan de rétention + brouillon d'email (POST /recommend/enriched)."""
    return _post("/recommend/enriched", client)


def simuler_what_if(client: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Simulation du score avant/après modifications (POST /what-if)."""
    return _post("/what-if", {"client": client, "overrides": overrides})


def clients_a_risque(limit: int = 10) -> dict[str, Any]:
    """Top-N clients les plus à risque (GET /clients/high-risk)."""
    return _get("/clients/high-risk", {"limit": limit})


def resume_dashboard() -> dict[str, Any]:
    """Agrégats du tableau de bord (GET /dashboard)."""
    return _get("/dashboard")


def schema_actif() -> dict[str, Any]:
    """Variables attendues par le modèle actif (GET /schema)."""
    return _get("/schema")


# Catalogue des outils, utile pour l'orchestrateur (nom -> fonction).
OUTILS = {
    "predire": predire,
    "expliquer": expliquer,
    "recommander": recommander,
    "simuler_what_if": simuler_what_if,
    "clients_a_risque": clients_a_risque,
    "resume_dashboard": resume_dashboard,
    "schema_actif": schema_actif,
}
