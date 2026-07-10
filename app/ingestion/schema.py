"""Détection automatique du schéma d'un dataset (Couche 1 — Ingestion).

Identifie par heuristiques simples :
- la variable cible (churn),
- les colonnes d'identifiant (à écarter du modèle),
- les fuites de données potentielles (data leakage).

Ces heuristiques constituent une première brique ; une analyse plus fine
via un LLM pourra être branchée ultérieurement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

# Noms fréquents de la variable cible d'un problème de churn.
NOMS_CIBLE_CANDIDATS: tuple[str, ...] = (
    "exited", "churn", "churned", "attrition", "target", "label", "y",
    "is_churn", "has_churned",
)

# Motifs de noms typiques de colonnes d'identifiant.
MOTIF_ID = re.compile(
    r"(^id$|_id$|^id[_-]|number$|^row|customer.?id|client.?id|uuid|guid|"
    r"code$|surname|last[_-]?name|full[_-]?name)",
    re.IGNORECASE,
)

# Seuils heuristiques.
SEUIL_UNICITE_ID = 0.90          # ratio nunique/lignes au-delà duquel c'est un ID
SEUIL_CORR_FUITE = 0.95          # |corrélation| avec la cible au-delà = fuite probable
SEUIL_CARDINALITE_CAT = 0.05     # part de valeurs uniques en-deçà = catégorielle


@dataclass
class RapportSchema:
    """Résultat de l'analyse de schéma d'un dataset."""

    n_lignes: int
    n_colonnes: int
    cible: str | None
    colonnes_id: list[str] = field(default_factory=list)
    colonnes_categorielles: list[str] = field(default_factory=list)
    colonnes_numeriques: list[str] = field(default_factory=list)
    fuites_potentielles: list[str] = field(default_factory=list)

    def resume(self) -> str:
        """Retourne un résumé lisible du rapport."""
        lignes = [
            "RAPPORT DE SCHÉMA",
            "-" * 50,
            f"Dimensions          : {self.n_lignes:,} lignes × {self.n_colonnes} colonnes",
            f"Variable cible      : {self.cible or '(non détectée)'}",
            f"Colonnes d'ID       : {self.colonnes_id or '(aucune)'}",
            f"Colonnes catégoriel.: {self.colonnes_categorielles or '(aucune)'}",
            f"Colonnes numériques : {self.colonnes_numeriques or '(aucune)'}",
            f"Fuites potentielles : {self.fuites_potentielles or '(aucune)'}",
        ]
        return "\n".join(lignes)


def detecter_cible(df: pd.DataFrame) -> str | None:
    """Devine la colonne cible.

    Stratégie : d'abord une correspondance par nom (insensible à la casse),
    ensuite un repli sur une colonne binaire dont le nom évoque le churn.
    """
    colonnes_min = {c.lower(): c for c in df.columns}

    # 1) Correspondance exacte sur un nom candidat.
    for candidat in NOMS_CIBLE_CANDIDATS:
        if candidat in colonnes_min:
            return colonnes_min[candidat]

    # 2) Repli : colonne binaire (2 valeurs) au nom évocateur.
    for col in df.columns:
        if df[col].nunique(dropna=True) == 2 and re.search(
            r"exit|churn|attrit|target|label", col, re.IGNORECASE
        ):
            return col

    return None


def detecter_colonnes_id(df: pd.DataFrame, cible: str | None) -> list[str]:
    """Identifie les colonnes d'identifiant.

    Une colonne est considérée comme un ID si son nom correspond à un motif
    connu, ou si (pour un entier/texte) elle est quasi entièrement composée
    de valeurs uniques. Les flottants continus (ex. salaire) sont exclus de
    la règle d'unicité. La cible n'est jamais retournée.
    """
    n = len(df)
    ids: list[str] = []
    for col in df.columns:
        if col == cible:
            continue
        serie = df[col]
        # La règle "quasi-unique = ID" ne vaut que pour les entiers et le texte :
        # une variable flottante continue (ex. salaire) est aussi quasi-unique
        # mais n'est PAS un identifiant.
        est_type_id = pd.api.types.is_integer_dtype(serie) or (
            not pd.api.types.is_numeric_dtype(serie)
        )
        ratio_unicite = serie.nunique(dropna=True) / n if n else 0.0
        if MOTIF_ID.search(col) or (est_type_id and ratio_unicite >= SEUIL_UNICITE_ID):
            ids.append(col)
    return ids


def detecter_fuites(
    df: pd.DataFrame, cible: str | None, colonnes_id: list[str]
) -> list[str]:
    """Repère les fuites de données potentielles.

    Heuristiques :
    - forte corrélation numérique avec la cible (|corr| >= seuil),
    - prédicteur quasi parfait : chaque valeur de la colonne mène à une
      cible unique (utile pour les colonnes catégorielles).
    Les colonnes d'ID et la cible sont exclues.
    """
    if cible is None or cible not in df.columns:
        return []

    fuites: list[str] = []
    y = df[cible]
    a_exclure = set(colonnes_id) | {cible}

    # Cible numérisée pour le calcul de corrélation.
    y_num = pd.to_numeric(y, errors="coerce")

    for col in df.columns:
        if col in a_exclure:
            continue

        serie = df[col]

        # Cas numérique : corrélation de Pearson.
        if pd.api.types.is_numeric_dtype(serie) and y_num.notna().any():
            corr = serie.corr(y_num)
            if pd.notna(corr) and abs(corr) >= SEUIL_CORR_FUITE:
                fuites.append(col)
                continue

        # Cas général : prédicteur quasi parfait de la cible.
        # (chaque valeur de la colonne mène à une cible unique)
        # On restreint aux colonnes de cardinalité modérée : sinon un flottant
        # continu (chaque valeur ~ unique) apparaît a tort comme prédicteur parfait.
        n_uniques = serie.nunique(dropna=True)
        if 1 < n_uniques <= max(20, len(df) // 10):
            classes_par_valeur = df.groupby(col, observed=True)[cible].nunique()
            if classes_par_valeur.mean() <= 1.0:
                fuites.append(col)

    return fuites


def analyser_schema(df: pd.DataFrame) -> RapportSchema:
    """Analyse complète du schéma d'un dataset.

    Args:
        df: Le dataset à analyser.

    Returns:
        Un :class:`RapportSchema` récapitulant cible, IDs, types et fuites.
    """
    cible = detecter_cible(df)
    colonnes_id = detecter_colonnes_id(df, cible)
    fuites = detecter_fuites(df, cible, colonnes_id)

    # Classement des colonnes restantes en catégorielles / numériques.
    a_exclure = set(colonnes_id) | ({cible} if cible else set())
    categorielles: list[str] = []
    numeriques: list[str] = []
    n = len(df)
    for col in df.columns:
        if col in a_exclure:
            continue
        serie = df[col]
        if pd.api.types.is_numeric_dtype(serie):
            # Un numérique à très faible cardinalité est traité comme catégoriel.
            ratio = serie.nunique(dropna=True) / n if n else 0.0
            if ratio <= SEUIL_CARDINALITE_CAT and serie.nunique(dropna=True) <= 10:
                categorielles.append(col)
            else:
                numeriques.append(col)
        else:
            categorielles.append(col)

    return RapportSchema(
        n_lignes=n,
        n_colonnes=df.shape[1],
        cible=cible,
        colonnes_id=colonnes_id,
        colonnes_categorielles=categorielles,
        colonnes_numeriques=numeriques,
        fuites_potentielles=fuites,
    )
