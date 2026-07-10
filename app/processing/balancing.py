"""Rééquilibrage des classes par SMOTE (Couche 2 — Processing).

SMOTE (Synthetic Minority Over-sampling Technique) génère des exemples
synthétiques de la classe minoritaire. À n'appliquer que sur le jeu
d'ENTRAÎNEMENT, jamais sur le jeu de test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ratio_desequilibre(y: pd.Series | np.ndarray) -> float:
    """Retourne le ratio classe majoritaire / classe minoritaire."""
    valeurs = pd.Series(y).value_counts()
    if len(valeurs) < 2 or valeurs.min() == 0:
        return 1.0
    return float(valeurs.max() / valeurs.min())


def est_desequilibre(y: pd.Series | np.ndarray, seuil: float = 1.5) -> bool:
    """Indique si les classes sont déséquilibrées au-delà d'un seuil."""
    return ratio_desequilibre(y) >= seuil


def equilibrer_smote(
    X,
    y,
    *,
    seuil: float = 1.5,
    random_state: int = 42,
):
    """Applique SMOTE si les classes sont déséquilibrées.

    Args:
        X: Matrice de features (déjà encodée numériquement).
        y: Vecteur cible.
        seuil: Ratio de déséquilibre à partir duquel SMOTE est appliqué.
        random_state: Graine pour la reproductibilité.

    Returns:
        Un tuple ``(X_res, y_res, applique)`` où ``applique`` indique si SMOTE
        a effectivement été utilisé.
    """
    if not est_desequilibre(y, seuil):
        return X, y, False

    from imblearn.over_sampling import SMOTE

    smote = SMOTE(random_state=random_state)
    X_res, y_res = smote.fit_resample(X, y)
    return X_res, y_res, True
