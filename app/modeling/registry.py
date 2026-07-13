"""Model registry versionne (Couche 3 - Modeling).

Chaque entrainement produit une version stockee dans models/registry/<version>/
avec : le pipeline (model.joblib), le schema du dataset (schema.json) et les
metadonnees (meta.json). Un pointeur models/active.json designe la version
active, et des copies a plat (best_model.joblib, schema.json, model_meta.json)
exposent le modele actif pour l'API et la prediction.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from app.config import settings
from app.ingestion.schema_registry import SchemaComplet


def _remplacer_atomique(ecrire, chemin: Path) -> None:
    """Ecrit via ecrire(tmp) dans un fichier temporaire puis le renomme.

    os.replace est atomique : le fichier final est soit l'ancien complet, soit
    le nouveau complet, jamais un fichier tronque.
    """
    tmp = chemin.with_name(chemin.name + ".tmp")
    try:
        ecrire(tmp)
        os.replace(tmp, chemin)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def enregistrer_modele(
    pipeline: Any,
    schema: SchemaComplet,
    resultats: list[dict[str, Any]],
    meilleur_modele: str,
    classes: list[Any],
    raison_selection: str = "",
    *,
    dossier_modeles: Path | None = None,
    reference_drift: dict[str, Any] | None = None,
    nom_dataset: str | None = None,
) -> dict[str, Any]:
    """Enregistre une nouvelle version de modele et la rend active."""
    dossier = dossier_modeles or settings.models_dir
    version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dossier_version = dossier / "registry" / version
    dossier_version.mkdir(parents=True, exist_ok=True)

    meta: dict[str, Any] = {
        "version": version,
        "date": datetime.now(timezone.utc).isoformat(),
        "meilleur_modele": meilleur_modele,
        "cible": schema.cible,
        "type_probleme": schema.type_probleme,
        "classes": classes,
        "colonnes_features": [c.nom for c in schema.features()],
        "raison_selection": raison_selection,
        "resultats": resultats,
        "dataset": nom_dataset,
    }

    meta_json = json.dumps(meta, indent=2, ensure_ascii=False)

    _remplacer_atomique(lambda t: joblib.dump(pipeline, t), dossier_version / "model.joblib")
    _remplacer_atomique(schema.sauvegarder, dossier_version / "schema.json")
    _remplacer_atomique(
        lambda t: t.write_text(meta_json, encoding="utf-8"),
        dossier_version / "meta.json",
    )

    _remplacer_atomique(lambda t: joblib.dump(pipeline, t), dossier / "best_model.joblib")
    _remplacer_atomique(schema.sauvegarder, dossier / "schema.json")
    _remplacer_atomique(
        lambda t: t.write_text(meta_json, encoding="utf-8"),
        dossier / "model_meta.json",
    )

    if reference_drift is not None:
        reference_json = json.dumps(reference_drift, indent=2, ensure_ascii=False)
        _remplacer_atomique(
            lambda t: t.write_text(reference_json, encoding="utf-8"),
            dossier_version / "drift_reference.json",
        )
        _remplacer_atomique(
            lambda t: t.write_text(reference_json, encoding="utf-8"),
            dossier / "drift_reference.json",
        )

    _remplacer_atomique(
        lambda t: t.write_text(
            json.dumps({"version": version, "date": meta["date"]}, indent=2),
            encoding="utf-8",
        ),
        dossier / "active.json",
    )
    return meta


def activer_version(version: str, dossier_modeles: Path | None = None) -> dict[str, Any]:
    """Rend active une version deja presente dans le registre, sans re-entrainer.

    Recopie les fichiers de registry/<version>/ vers les copies a plat
    (best_model.joblib, schema.json, model_meta.json et si present
    drift_reference.json) puis met a jour active.json, en ecritures atomiques.
    """
    dossier = dossier_modeles or settings.models_dir
    dossier_version = dossier / "registry" / version
    if not dossier_version.is_dir():
        raise FileNotFoundError(f"Version introuvable dans le registre : {version}")

    src_model = dossier_version / "model.joblib"
    src_schema = dossier_version / "schema.json"
    src_meta = dossier_version / "meta.json"
    for src in (src_model, src_schema, src_meta):
        if not src.exists():
            raise FileNotFoundError(f"Fichier manquant pour la version {version} : {src.name}")

    def _copier(src: Path, dst: Path) -> None:
        contenu = src.read_bytes()
        _remplacer_atomique(lambda t: t.write_bytes(contenu), dst)

    _copier(src_model, dossier / "best_model.joblib")
    _copier(src_schema, dossier / "schema.json")
    _copier(src_meta, dossier / "model_meta.json")

    src_drift = dossier_version / "drift_reference.json"
    if src_drift.exists():
        _copier(src_drift, dossier / "drift_reference.json")

    meta = json.loads(src_meta.read_text(encoding="utf-8"))
    date = meta.get("date", datetime.now(timezone.utc).isoformat())
    _remplacer_atomique(
        lambda t: t.write_text(
            json.dumps({"version": version, "date": date}, indent=2),
            encoding="utf-8",
        ),
        dossier / "active.json",
    )
    return meta


def lister_versions(dossier_modeles: Path | None = None) -> list[str]:
    """Retourne les versions disponibles dans le registre (recentes d'abord)."""
    dossier = (dossier_modeles or settings.models_dir) / "registry"
    if not dossier.exists():
        return []
    return sorted((p.name for p in dossier.iterdir() if p.is_dir()), reverse=True)


def version_active(dossier_modeles: Path | None = None) -> str | None:
    """Retourne l'identifiant de la version active, ou None."""
    chemin = (dossier_modeles or settings.models_dir) / "active.json"
    if chemin.exists():
        return json.loads(chemin.read_text(encoding="utf-8")).get("version")
    return None
