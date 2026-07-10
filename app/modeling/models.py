"""Catalogue des modèles de classification (Couche 3 — Modeling).

Gamme professionnelle et universelle : linéaires, à base d'instances, bayésiens,
ensembles (bagging/boosting) et gradient boosting moderne. Tous exposent
``predict_proba`` (nécessaire pour la sélection par ROC-AUC) et fonctionnent sur
n'importe quel dataset une fois prétraité.

XGBoost, LightGBM et CatBoost sont importés de façon optionnelle : absents, ils
sont simplement ignorés sans casser la comparaison.
"""

from __future__ import annotations

from typing import Any

from sklearn.ensemble import (
    AdaBoostClassifier,
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier


def modeles_disponibles(
    random_state: int = 42, *, rapide: bool = True
) -> dict[str, Any]:
    """Retourne les modèles à entraîner et comparer, indexés par nom lisible.

    Args:
        random_state: Graine pour la reproductibilité.
        rapide: Si vrai (défaut), retourne un **jeu réduit et rapide** de modèles
            performants (baseline linéaire + ensembles/boosting légers), pour un
            entraînement en quelques dizaines de secondes. Si faux, retourne le
            catalogue complet (plus lent, pour un benchmark exhaustif).

    Returns:
        Un dictionnaire {nom: estimateur scikit-learn non entraîné}.
    """
    if rapide:
        return _modeles_rapides(random_state)
    return _modeles_complets(random_state)


def _modeles_rapides(random_state: int) -> dict[str, Any]:
    """Jeu réduit : baseline linéaire + boosting/forêt légers (rapide)."""
    modeles: dict[str, Any] = {
        "Régression logistique": LogisticRegression(
            max_iter=1000, random_state=random_state
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=150, random_state=random_state, n_jobs=-1
        ),
        "HistGradient Boosting": HistGradientBoostingClassifier(
            random_state=random_state
        ),
    }

    # Boosting modernes : très rapides et performants s'ils sont installés.
    try:
        from xgboost import XGBClassifier

        modeles["XGBoost"] = XGBClassifier(
            n_estimators=200, learning_rate=0.1, max_depth=5, subsample=0.9,
            eval_metric="logloss", random_state=random_state, n_jobs=-1,
        )
    except ImportError:
        pass

    try:
        from lightgbm import LGBMClassifier

        modeles["LightGBM"] = LGBMClassifier(
            n_estimators=200, learning_rate=0.05,
            random_state=random_state, n_jobs=-1, verbose=-1,
        )
    except ImportError:
        pass

    return modeles


def _modeles_complets(random_state: int) -> dict[str, Any]:
    """Catalogue complet (benchmark exhaustif, plus lent)."""
    modeles: dict[str, Any] = {
        "Régression logistique": LogisticRegression(
            max_iter=1000, random_state=random_state
        ),
        "K plus proches voisins": KNeighborsClassifier(n_neighbors=15),
        "Naive Bayes": GaussianNB(),
        "Random Forest": RandomForestClassifier(
            n_estimators=300, random_state=random_state, n_jobs=-1
        ),
        "Extra Trees": ExtraTreesClassifier(
            n_estimators=300, random_state=random_state, n_jobs=-1
        ),
        "AdaBoost": AdaBoostClassifier(n_estimators=200, random_state=random_state),
        "Gradient Boosting": GradientBoostingClassifier(random_state=random_state),
        "HistGradient Boosting": HistGradientBoostingClassifier(
            random_state=random_state
        ),
    }

    try:
        from xgboost import XGBClassifier

        modeles["XGBoost"] = XGBClassifier(
            n_estimators=300, learning_rate=0.1, max_depth=5, subsample=0.9,
            eval_metric="logloss", random_state=random_state, n_jobs=-1,
        )
    except ImportError:
        pass

    try:
        from lightgbm import LGBMClassifier

        modeles["LightGBM"] = LGBMClassifier(
            n_estimators=300, learning_rate=0.05,
            random_state=random_state, n_jobs=-1, verbose=-1,
        )
    except ImportError:
        pass

    try:
        from catboost import CatBoostClassifier

        modeles["CatBoost"] = CatBoostClassifier(
            iterations=300, learning_rate=0.05, depth=6,
            random_state=random_state, verbose=False,
        )
    except ImportError:
        pass

    return modeles
