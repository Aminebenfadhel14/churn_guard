"""Couche 3 — Modeling.

Entraînement et comparaison de plusieurs modèles (régression logistique,
Random Forest, Gradient Boosting, XGBoost, LightGBM), sélection du meilleur
selon ROC-AUC / F1, sauvegarde joblib et suivi MLflow.

Point d'entrée principal : :func:`entrainer_et_selectionner`.
"""

from app.modeling.models import modeles_disponibles
from app.modeling.train import (
    ResultatEntrainement,
    ResultatModele,
    construire_pipeline,
    entrainer_et_selectionner,
    formater_resultat_entrainement,
)

__all__ = [
    "modeles_disponibles",
    "entrainer_et_selectionner",
    "construire_pipeline",
    "formater_resultat_entrainement",
    "ResultatEntrainement",
    "ResultatModele",
]
