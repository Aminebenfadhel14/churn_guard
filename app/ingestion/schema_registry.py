"""Schéma universel versionné (Couche 1 — Ingestion).

Produit une description complète et agnostique au secteur d'un dataset :
pour chaque colonne, son TYPE (numérique / catégoriel / booléen / date / texte),
son RÔLE (cible / identifiant / fuite / feature), ses valeurs possibles ou ses
bornes, et son taux de valeurs manquantes.

Ce schéma sert de source de vérité unique : le préprocessing, l'API et le
formulaire du frontend s'y réfèrent — aucun nom de colonne n'est codé en dur.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.ingestion.schema import (
    detecter_cible,
    detecter_colonnes_id,
    detecter_fuites,
)

# Types de colonnes reconnus.
TYPE_NUMERIQUE = "numerique"
TYPE_CATEGORIEL = "categoriel"
TYPE_BOOLEEN = "booleen"
TYPE_DATE = "date"
TYPE_TEXTE = "texte"

# Rôles de colonnes.
ROLE_CIBLE = "cible"
ROLE_ID = "identifiant"
ROLE_FUITE = "fuite"
ROLE_FEATURE = "feature"

# Nombre max de valeurs listées pour une colonne catégorielle.
MAX_VALEURS_LISTEES = 50

SCHEMA_VERSION = 1


def inferer_type(serie: pd.Series) -> str:
    """Infère le type d'une colonne à partir de son contenu."""
    n = len(serie)
    n_uniques = serie.nunique(dropna=True)

    if pd.api.types.is_bool_dtype(serie):
        return TYPE_BOOLEEN
    if pd.api.types.is_datetime64_any_dtype(serie):
        return TYPE_DATE
    if pd.api.types.is_numeric_dtype(serie):
        # 2 valeurs distinctes → drapeau binaire.
        return TYPE_BOOLEEN if n_uniques <= 2 else TYPE_NUMERIQUE

    # Colonnes textuelles : on tente d'abord la conversion en date.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        essai_date = pd.to_datetime(serie, errors="coerce")
    if n and essai_date.notna().mean() > 0.9:
        return TYPE_DATE

    # Faible cardinalité → catégoriel ; forte cardinalité → texte libre.
    ratio = n_uniques / n if n else 0.0
    if n_uniques <= 2:
        return TYPE_BOOLEEN
    if ratio < 0.5 and n_uniques <= MAX_VALEURS_LISTEES:
        return TYPE_CATEGORIEL
    return TYPE_TEXTE


@dataclass
class ColonneSchema:
    """Description d'une colonne du dataset."""

    nom: str
    type: str
    role: str
    taux_manquant: float
    valeurs: list[Any] | None = None      # pour catégoriel / booléen
    min: float | None = None              # pour numérique
    max: float | None = None              # pour numérique


@dataclass
class SchemaComplet:
    """Schéma complet et versionné d'un dataset."""

    version: int
    date: str
    n_lignes: int
    n_colonnes: int
    cible: str | None
    type_probleme: str | None
    colonnes: list[ColonneSchema] = field(default_factory=list)

    def features(self) -> list[ColonneSchema]:
        """Colonnes réellement utilisées comme variables d'entrée."""
        return [c for c in self.colonnes if c.role == ROLE_FEATURE]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def sauvegarder(self, chemin: str | Path) -> Path:
        """Écrit le schéma au format JSON."""
        chemin = Path(chemin)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return chemin


def construire_schema(
    df: pd.DataFrame, cible: str | None = None
) -> SchemaComplet:
    """Construit le schéma complet d'un dataset.

    Args:
        df: Le dataset à décrire.
        cible: Nom de la cible ; détection automatique si ``None``.

    Returns:
        Un :class:`SchemaComplet`.
    """
    n = len(df)
    cible = cible or detecter_cible(df)
    colonnes_id = set(detecter_colonnes_id(df, cible))
    fuites = set(detecter_fuites(df, cible, list(colonnes_id)))

    colonnes: list[ColonneSchema] = []
    for nom in df.columns:
        serie = df[nom]
        type_col = inferer_type(serie)
        taux_manquant = round(float(serie.isna().mean()) * 100, 2)

        # Détermination du rôle.
        if nom == cible:
            role = ROLE_CIBLE
        elif nom in fuites:
            role = ROLE_FUITE
        elif nom in colonnes_id:
            role = ROLE_ID
        else:
            role = ROLE_FEATURE

        col = ColonneSchema(
            nom=nom, type=type_col, role=role, taux_manquant=taux_manquant
        )

        # Valeurs possibles (catégoriel / booléen) ou bornes (numérique).
        if type_col in (TYPE_CATEGORIEL, TYPE_BOOLEEN):
            valeurs = serie.dropna().unique().tolist()[:MAX_VALEURS_LISTEES]
            # Conversion en types JSON simples.
            col.valeurs = [
                int(v) if isinstance(v, bool) else
                (v.item() if hasattr(v, "item") else v)
                for v in valeurs
            ]
        elif type_col == TYPE_NUMERIQUE:
            col.min = float(serie.min())
            col.max = float(serie.max())

        colonnes.append(col)

    # Type de problème (basé sur la cardinalité de la cible).
    type_probleme: str | None = None
    if cible is not None and cible in df.columns:
        n_classes = df[cible].nunique(dropna=True)
        type_probleme = "binaire" if n_classes == 2 else "multiclasse"

    return SchemaComplet(
        version=SCHEMA_VERSION,
        date=datetime.now(timezone.utc).isoformat(),
        n_lignes=n,
        n_colonnes=df.shape[1],
        cible=cible,
        type_probleme=type_probleme,
        colonnes=colonnes,
    )
