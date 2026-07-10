"""Model registry versionné (Couche 3 — Modeling).

Chaque entraînement produit une **version** stockée dans ``models/registry/<version>/``
avec : le pipeline (``model.joblib``), le schéma du dataset (``schema.json``) et les
métadonnées (``meta.json``). Un pointeur ``models/active.json`` désigne la version
active, et des copies « à plat » (``best_model.joblib``, ``schema.json``,
``model_meta.json``) exposent le modèle actif pour l'API et la prédiction.
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
    """Écrit via ``ecrire(tmp)`` dans un fichier temporaire puis le renomme.

    ``os.replace`` est atomique : le fichier final est soit l'ancien complet,
    soit le nouveau complet — jamais un fichier tronqué (si l'écriture est
    interrompue, ``chemin`` garde sa version précédente intacte).
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
) -> dict[str, Any]:
    """Enregistre une nouvelle version de modèle et la rend active.

    Args:
        pipeline: Pipeline entraîné (préprocesseur + modèle).
        schema: Schéma du dataset ayant servi à l'entraînement.
        resultats: Liste des métriques par modèle comparé.
        meilleur_modele: Nom du modèle sélectionné.
        classes: Valeurs de la cible dans l'ordre encodé (index = classe).
        raison_selection: Explication lisible du choix du meilleur modèle.
        dossier_modeles: Racine des modèles (défaut : ``settings.models_dir``).
        reference_drift: Distribution de référence du dataset d'entraînement
            (``app.monitoring.drift.construire_reference``), utilisée pour
            détecter le drift des futurs datasets uploadés. Optionnel.

    Returns:
        Le dictionnaire de métadonnées de la version enregistrée.
    """
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
    }

    meta_json = json.dumps(meta, indent=2, ensure_ascii=False)

    # 1) Écriture de la version dans le registre (écritures atomiques).
    _remplacer_atomique(lambda t: joblib.dump(pipeline, t), dossier_version / "model.joblib")
    _remplacer_atomique(schema.sauvegarder, dossier_version / "schema.json")
    _remplacer_atomique(
        lambda t: t.write_text(meta_json, encoding="utf-8"),
        dossier_version / "meta.json",
    )

    # 2) Exposition du modèle actif (copies à plat, lues par l'API/predict).
    # Écritures atomiques : jamais de fichier tronqué même si interrompu.
    _remplacer_atomique(lambda t: joblib.dump(pipeline, t), dossier / "best_model.joblib")
    _remplacer_atomique(schema.sauvegarder, dossier / "schema.json")
    _remplacer_atomique(
        lambda t: t.write_text(meta_json, encoding="utf-8"),
        dossier / "model_meta.json",
    )

    # 3) Référence de drift (optionnelle) : version + copie active, même schéma
    # d'écriture atomique que le reste.
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

    # active.json en dernier : le pointeur ne bascule qu'une fois tout écrit.
    _remplacer_atomique(
        lambda t: t.write_text(
            json.dumps({"version": version, "date": meta["date"]}, indent=2),
            encoding="utf-8",
        ),
        dossier / "active.json",
    )
    return meta


def lister_versions(dossier_modeles: Path | None = None) -> list[str]:
    """Retourne les versions disponibles dans le registre (les plus récentes d'abord)."""
    dossier = (dossier_modeles or settings.models_dir) / "registry"
    if not dossier.exists():
        return []
    return sorted((p.name for p in dossier.iterdir() if p.is_dir()), reverse=True)


def version_active(dossier_modeles: Path | None = None) -> str | None:
    """Retourne l'identifiant de la version active, ou ``None``."""
    chemin = (dossier_modeles or settings.models_dir) / "active.json"
    if chemin.exists():
        return json.loads(chemin.read_text(encoding="utf-8")).get("version")
    return None
