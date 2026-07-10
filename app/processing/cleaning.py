"""Nettoyage adaptatif des données (Couche 2 — Processing).

Retire les colonnes inutiles (identifiants, fuites), impute les valeurs
manquantes et limite l'effet des valeurs aberrantes (outliers).
"""

from __future__ import annotations

import pandas as pd

from app.ingestion.schema import RapportSchema


def retirer_colonnes_inutiles(df: pd.DataFrame, schema: RapportSchema) -> pd.DataFrame:
    """Retire les colonnes d'identifiant et les fuites détectées.

    La colonne cible est conservée.
    """
    a_retirer = [
        c for c in (set(schema.colonnes_id) | set(schema.fuites_potentielles))
        if c in df.columns and c != schema.cible
    ]
    return df.drop(columns=a_retirer)


def imputer_manquants(df: pd.DataFrame, cible: str | None = None) -> pd.DataFrame:
    """Impute les valeurs manquantes.

    - Colonnes numériques : médiane (robuste aux outliers).
    - Colonnes catégorielles : mode (valeur la plus fréquente).
    La cible n'est jamais imputée (les lignes sans cible sont laissées telles quelles).
    """
    df = df.copy()
    for col in df.columns:
        if col == cible or not df[col].isna().any():
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].median())
        else:
            mode = df[col].mode(dropna=True)
            if not mode.empty:
                df[col] = df[col].fillna(mode.iloc[0])
    return df


def limiter_outliers(
    df: pd.DataFrame,
    cible: str | None = None,
    *,
    facteur: float = 1.5,
) -> pd.DataFrame:
    """Limite (clip) les valeurs aberrantes des colonnes numériques.

    Utilise la méthode de l'écart interquartile (IQR) : toute valeur au-delà de
    [Q1 - facteur*IQR ; Q3 + facteur*IQR] est ramenée à la borne. On ne supprime
    aucune ligne (le clipping préserve la taille du dataset).
    Les colonnes binaires (2 valeurs) et la cible sont ignorées.
    """
    df = df.copy()
    for col in df.select_dtypes(include="number").columns:
        if col == cible or df[col].nunique(dropna=True) <= 2:
            continue
        q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        borne_bas = q1 - facteur * iqr
        borne_haut = q3 + facteur * iqr
        df[col] = df[col].clip(lower=borne_bas, upper=borne_haut)
    return df


def nettoyer_dataframe(
    df: pd.DataFrame,
    schema: RapportSchema,
    *,
    clip_outliers: bool = True,
) -> pd.DataFrame:
    """Applique le pipeline complet de nettoyage.

    Étapes : retrait des colonnes inutiles → imputation → (optionnel) clip des
    outliers. Retourne un nouveau DataFrame nettoyé.
    """
    df = retirer_colonnes_inutiles(df, schema)
    df = imputer_manquants(df, schema.cible)
    if clip_outliers:
        df = limiter_outliers(df, schema.cible)
    return df
