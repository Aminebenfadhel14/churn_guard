"""Couche 1 — Ingestion.

Chargement des datasets (CSV, Excel, Parquet) avec détection automatique
de l'encodage, détection du schéma (cible, IDs, fuites) et construction d'un
schéma universel versionné (type + rôle + valeurs par colonne).
"""

from app.ingestion.loader import charger_dataset, detecter_encodage
from app.ingestion.quality import analyser_qualite
from app.ingestion.schema import (
    RapportSchema,
    analyser_schema,
    detecter_cible,
    detecter_colonnes_id,
    detecter_fuites,
)
from app.ingestion.schema_registry import (
    ColonneSchema,
    SchemaComplet,
    construire_schema,
    inferer_type,
)

__all__ = [
    "charger_dataset",
    "detecter_encodage",
    "analyser_qualite",
    "RapportSchema",
    "analyser_schema",
    "detecter_cible",
    "detecter_colonnes_id",
    "detecter_fuites",
    "ColonneSchema",
    "SchemaComplet",
    "construire_schema",
    "inferer_type",
]
