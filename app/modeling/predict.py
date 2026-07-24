"""Service de prédiction (Couche 3 — Modeling / Serving).

Charge le meilleur modèle sauvegardé (best_model.joblib) et prédit le risque
de churn d'un client à partir de ses caractéristiques brutes.
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings
from app.processing.features import ajouter_features

# Répertoire du modèle actif pour la requête courante. None -> modèle global
# (racine ``settings.models_dir``, comportement historique). Un opérateur
# connecté le fixe sur son dossier personnel via ``definir_repertoire_modeles``
# (voir app/api/routes.py) : chaque utilisateur charge ainsi son propre modèle
# sans que les datasets soient partagés. Un ContextVar isole naturellement les
# requêtes concurrentes (chacune a sa propre valeur).
_repertoire_modeles: ContextVar[Path | None] = ContextVar("repertoire_modeles", default=None)


def definir_repertoire_modeles(chemin: Path | None) -> None:
    """Fixe (pour la requête courante) le dossier d'où charger le modèle actif.

    ``None`` rétablit le modèle global (racine). À appeler en tête des endpoints
    de lecture, à partir de l'utilisateur courant.
    """
    _repertoire_modeles.set(chemin)


def _rep() -> Path:
    """Répertoire effectif du modèle actif : celui de la requête, sinon la racine."""
    return _repertoire_modeles.get() or settings.models_dir


@lru_cache(maxsize=16)
def _charger_modele_depuis(dossier: Path):
    """Charge et met en cache le pipeline de ``<dossier>/best_model.joblib``.

    Cache keyé par dossier : chaque utilisateur (dossier distinct) a son entrée.
    """
    import joblib

    chemin = dossier / "best_model.joblib"
    if not chemin.exists():
        raise FileNotFoundError(
            "Modèle introuvable. Importez un dataset puis lancez un entraînement."
        )
    return joblib.load(chemin)


@lru_cache(maxsize=16)
def _charger_meta_depuis(dossier: Path) -> dict[str, Any]:
    """Charge et met en cache les métadonnées de ``<dossier>/model_meta.json``."""
    chemin = dossier / "model_meta.json"
    if chemin.exists():
        return json.loads(chemin.read_text(encoding="utf-8"))
    return {}


def charger_modele():
    """Charge le pipeline du modèle actif pour la requête courante.

    Raises:
        FileNotFoundError: Si le modèle n'a pas encore été entraîné.
    """
    return _charger_modele_depuis(_rep())


def charger_meta() -> dict[str, Any]:
    """Charge les métadonnées du modèle actif (nom, colonnes, cible)."""
    return _charger_meta_depuis(_rep())


def vider_caches_modele() -> None:
    """Vide les caches de chargement (modèle + métadonnées), tous dossiers confondus.

    À appeler après un (ré)entraînement ou une activation pour que l'API serve
    immédiatement le nouveau modèle.
    """
    _charger_modele_depuis.cache_clear()
    _charger_meta_depuis.cache_clear()


def niveau_risque(score: float) -> str:
    """Convertit un score 0-100 en niveau de risque."""
    if score < 30:
        return "faible"
    if score <= 70:
        return "moyen"
    return "eleve"


def predire(record: dict[str, Any]) -> dict[str, Any]:
    """Prédit le risque de churn d'un client.

    Args:
        record: Dictionnaire des caractéristiques brutes du client
            (ex. ``{"CreditScore": 619, "Geography": "France", ...}``).

    Returns:
        Un dictionnaire avec ``risk_score`` (0-100), ``prediction`` (0/1),
        ``risk_level`` et ``modele`` (nom du modèle utilisé).
    """
    pipeline = charger_modele()
    meta = charger_meta()

    # Reproduit le feature engineering appliqué à l'entraînement.
    df = pd.DataFrame([record])
    df = ajouter_features(df)

    proba = float(pipeline.predict_proba(df)[0, 1])
    score = round(proba * 100, 1)

    return {
        "risk_score": score,
        "prediction": int(proba >= 0.5),
        "risk_level": niveau_risque(score),
        "modele": meta.get("meilleur_modele", "inconnu"),
    }
