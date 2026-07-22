"""Analyse de qualité des données (Couche 1 — Ingestion).

Calculs rapides effectués juste après l'upload, avant l'entraînement : repérer
les problèmes qui biaiseraient un modèle (valeurs manquantes, classes
déséquilibrées) sans attendre la fin d'un entraînement pour les découvrir.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.ingestion.schema_registry import SchemaComplet

SEUIL_MANQUANT_CRITIQUE = 30.0  # % au-dela duquel une colonne est signalee "critique"
SEUIL_MINORITE_FORT = 15.0  # % de la classe minoritaire en-dessous duquel le desequilibre est "fort"
SEUIL_MINORITE_MODERE = 35.0  # ... en-dessous duquel il est "modere"
CARDINALITE_MAX_CIBLE = 10  # au-dela, la cible n'est pas traitee comme categorielle


def analyser_qualite(df: pd.DataFrame, schema: SchemaComplet) -> dict[str, Any]:
    """Résumé de qualité : valeurs manquantes par colonne + équilibre des classes.

    Le taux de valeurs manquantes par colonne est déjà calculé dans le schéma
    (``ColonneSchema.taux_manquant``) — ici on ne fait que le trier/filtrer et
    ajouter l'équilibre des classes de la cible, absent du schéma.
    """
    colonnes_manquantes = sorted(
        (
            {"colonne": c.nom, "taux_manquant": c.taux_manquant}
            for c in schema.colonnes
            if c.taux_manquant > 0
        ),
        key=lambda c: c["taux_manquant"],
        reverse=True,
    )
    colonnes_critiques = [
        c["colonne"] for c in colonnes_manquantes if c["taux_manquant"] >= SEUIL_MANQUANT_CRITIQUE
    ]

    return {
        "colonnes_manquantes": colonnes_manquantes,
        "colonnes_critiques": colonnes_critiques,
        "equilibre_classes": _equilibre_classes(df, schema.cible),
    }


def _equilibre_classes(df: pd.DataFrame, cible: str | None) -> dict[str, Any] | None:
    if not cible or cible not in df.columns:
        return None
    if df[cible].nunique(dropna=True) not in range(2, CARDINALITE_MAX_CIBLE + 1):
        return None

    effectifs = df[cible].value_counts(dropna=True)
    total = int(effectifs.sum())
    if total == 0:
        return None

    repartition = [
        {"classe": str(classe), "pourcentage": round(float(effectif) / total * 100, 2)}
        for classe, effectif in effectifs.items()
    ]
    minorite = min(r["pourcentage"] for r in repartition)
    if minorite < SEUIL_MINORITE_FORT:
        niveau = "fort"
    elif minorite < SEUIL_MINORITE_MODERE:
        niveau = "modere"
    else:
        niveau = "equilibre"

    return {"repartition": repartition, "niveau": niveau}
