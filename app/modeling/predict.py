"""Service de prédiction (Couche 3 — Modeling / Serving).

Charge le meilleur modèle sauvegardé (best_model.joblib) et prédit le risque
de churn d'un client à partir de ses caractéristiques brutes.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import pandas as pd

from app.config import settings
from app.processing.features import ajouter_features


@lru_cache(maxsize=1)
def charger_modele():
    """Charge le pipeline entraîné depuis ``models/best_model.joblib``.

    Le résultat est mis en cache (chargé une seule fois).

    Raises:
        FileNotFoundError: Si le modèle n'a pas encore été entraîné.
    """
    import joblib

    chemin = settings.models_dir / "best_model.joblib"
    if not chemin.exists():
        raise FileNotFoundError(
            "Modèle introuvable. Lance d'abord l'entraînement : "
            "`python scripts/train_model.py`."
        )
    return joblib.load(chemin)


@lru_cache(maxsize=1)
def charger_meta() -> dict[str, Any]:
    """Charge les métadonnées du modèle (nom, colonnes, cible)."""
    chemin = settings.models_dir / "model_meta.json"
    if chemin.exists():
        return json.loads(chemin.read_text(encoding="utf-8"))
    return {}


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
