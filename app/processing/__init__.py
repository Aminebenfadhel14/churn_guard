"""Couche 2 — Processing.

Nettoyage adaptatif (valeurs manquantes, outliers), feature engineering,
encodage des variables catégorielles et rééquilibrage des classes via SMOTE.

Point d'entrée principal : :func:`preparer_donnees`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.compose import ColumnTransformer

from app.ingestion.schema import RapportSchema, analyser_schema
from app.processing.balancing import (
    equilibrer_smote,
    est_desequilibre,
    ratio_desequilibre,
)
from app.processing.cleaning import nettoyer_dataframe
from app.processing.features import ajouter_features
from app.processing.preprocessing import construire_preprocesseur, separer_colonnes

__all__ = [
    "preparer_donnees",
    "ResultatPreparation",
    "nettoyer_dataframe",
    "ajouter_features",
    "construire_preprocesseur",
    "separer_colonnes",
    "equilibrer_smote",
    "est_desequilibre",
    "ratio_desequilibre",
]


@dataclass
class ResultatPreparation:
    """Données prêtes pour la modélisation (étape 7)."""

    X: pd.DataFrame                 # variables explicatives (non encodées)
    y: pd.Series                    # cible
    preprocesseur: ColumnTransformer  # ColumnTransformer non entraîné
    colonnes_numeriques: list[str]
    colonnes_categorielles: list[str]


def preparer_donnees(
    df: pd.DataFrame,
    schema: RapportSchema | None = None,
    *,
    clip_outliers: bool = True,
) -> ResultatPreparation:
    """Prépare un dataset brut pour l'entraînement.

    Enchaîne : détection de schéma (si non fournie) -> nettoyage ->
    feature engineering -> construction du préprocesseur, et sépare X / y.
    Le rééquilibrage SMOTE n'est PAS appliqué ici : il doit l'être uniquement
    sur le jeu d'entraînement (voir :func:`equilibrer_smote`, étape 7).

    Args:
        df: Dataset brut.
        schema: Schéma détecté ; calculé automatiquement si ``None``.
        clip_outliers: Active la limitation des valeurs aberrantes.

    Returns:
        Un :class:`ResultatPreparation`.

    Raises:
        ValueError: Si aucune variable cible n'est détectée.
    """
    schema = schema or analyser_schema(df)
    if schema.cible is None or schema.cible not in df.columns:
        raise ValueError(
            "Variable cible introuvable : impossible de préparer les données."
        )

    df_propre = nettoyer_dataframe(df, schema, clip_outliers=clip_outliers)
    df_enrichi = ajouter_features(df_propre)

    y = df_enrichi[schema.cible]
    X = df_enrichi.drop(columns=[schema.cible])

    preprocesseur = construire_preprocesseur(df_enrichi, schema.cible)
    numeriques, categorielles = separer_colonnes(df_enrichi, schema.cible)

    return ResultatPreparation(
        X=X,
        y=y,
        preprocesseur=preprocesseur,
        colonnes_numeriques=numeriques,
        colonnes_categorielles=categorielles,
    )
