"""Cache en mémoire des recommandations IA experte (Couche Recommendations).

Évite de rappeler le LLM (Groq) pour un client déjà traité récemment : pour
un même client et un même score de risque, la recommandation générée serait
de toute façon quasi identique. Réduit la latence perçue et la consommation
du quota gratuit du LLM.

Cache TTL en mémoire, protégé par un verrou — suffisant pour un unique
processus API (pas de dépendance externe type Redis). Voir
``settings.recommendation_cache_ttl_seconds`` pour ajuster la durée de vie.
Le cache est vidé après chaque réentraînement (``vider``) : un nouveau
modèle peut produire un score différent pour les mêmes caractéristiques
client, ce qui change naturellement la clé de cache — le vider explicitement
évite simplement de laisser trainer d'anciennes entrées inutiles en mémoire.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

from app.config import settings
from app.recommendations.drafting import IDENTITY_KEYS

_verrou = threading.Lock()
_cache: dict[str, tuple[float, list[dict[str, Any]], str]] = {}


def construire_cle(record: dict[str, Any], risk_score: float) -> str:
    """Construit une clé de cache stable pour un client + son score de risque.

    Utilise un identifiant client explicite s'il existe (colonnes usuelles
    d'ID/nom/email) ; sinon, hache l'ensemble des caractéristiques du client.
    Le score est arrondi à l'entier : un écart infime ne doit pas invalider
    inutilement le cache.
    """
    for cle_id in IDENTITY_KEYS:
        valeur = record.get(cle_id)
        if valeur not in (None, ""):
            return f"id:{cle_id}={valeur}:score={round(risk_score)}"

    empreinte = hashlib.sha256(
        json.dumps(record, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"hash:{empreinte}:score={round(risk_score)}"


def obtenir(cle: str) -> tuple[list[dict[str, Any]], str] | None:
    """Retourne ``(recommandations, source)`` en cache si présent et non expiré."""
    with _verrou:
        entree = _cache.get(cle)
        if entree is None:
            return None
        expire_a, recos, source = entree
        if expire_a < time.time():
            del _cache[cle]
            return None
        return recos, source


def enregistrer(cle: str, recos: list[dict[str, Any]], source: str) -> None:
    """Met en cache des recommandations pour la durée configurée.

    ``ttl <= 0`` désactive le cache (utile en tests ou pour du debug).
    """
    ttl = settings.recommendation_cache_ttl_seconds
    if ttl <= 0:
        return
    with _verrou:
        _cache[cle] = (time.time() + ttl, recos, source)


def vider() -> None:
    """Vide le cache (appelé après un réentraînement)."""
    with _verrou:
        _cache.clear()


def taille() -> int:
    """Nombre d'entrées actuellement en cache (diagnostic/tests)."""
    with _verrou:
        return len(_cache)
