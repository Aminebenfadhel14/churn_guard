"""Construction du préprocesseur scikit-learn (Couche 2 — Processing).

Assemble un ``ColumnTransformer`` qui, pour les variables explicatives :
- numériques : impute (médiane) puis standardise ;
- catégorielles : impute (mode) puis encode en one-hot.

Ce préprocesseur est destiné à être branché dans un pipeline avec SMOTE et un
modèle (étape 7).
"""

from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def separer_colonnes(
    df: pd.DataFrame, cible: str | None
) -> tuple[list[str], list[str]]:
    """Sépare les colonnes explicatives en numériques et catégorielles.

    La cible est exclue des deux listes.
    """
    numeriques: list[str] = []
    categorielles: list[str] = []
    for col in df.columns:
        if col == cible:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            numeriques.append(col)
        else:
            categorielles.append(col)
    return numeriques, categorielles


def construire_preprocesseur(
    df: pd.DataFrame, cible: str | None
) -> ColumnTransformer:
    """Construit le ``ColumnTransformer`` de préprocessing (non entraîné).

    Args:
        df: DataFrame nettoyé + enrichi (features déjà ajoutées).
        cible: Nom de la colonne cible (exclue du préprocessing).

    Returns:
        Un ``ColumnTransformer`` prêt à être intégré dans un pipeline.
    """
    numeriques, categorielles = separer_colonnes(df, cible)

    pipe_num = Pipeline(steps=[
        ("imputation", SimpleImputer(strategy="median")),
        ("standardisation", StandardScaler()),
    ])
    pipe_cat = Pipeline(steps=[
        ("imputation", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    return ColumnTransformer(
        transformers=[
            ("num", pipe_num, numeriques),
            ("cat", pipe_cat, categorielles),
        ],
        remainder="drop",
    )
