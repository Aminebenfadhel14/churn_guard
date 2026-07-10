"""Service de schéma pour l'API (Couche 4 — Serving).

Charge le schéma du modèle actif et valide dynamiquement les entrées de
``/predict`` contre ce schéma (types, valeurs autorisées). Aucune colonne
n'est codée en dur : tout dépend du dataset entraîné.
"""

from __future__ import annotations

import json
from typing import Any

from app.config import settings


def charger_schema_actif() -> dict[str, Any]:
    """Charge le schéma du modèle actif (``models/schema.json``).

    Raises:
        FileNotFoundError: Si aucun modèle n'a encore été entraîné.
    """
    chemin = settings.models_dir / "schema.json"
    if not chemin.exists():
        raise FileNotFoundError(
            "Aucun schéma actif. Entraîne d'abord un modèle : "
            "`python scripts/train_model.py`."
        )
    return json.loads(chemin.read_text(encoding="utf-8"))


def charger_drift_reference() -> dict[str, Any] | None:
    """Charge la référence de distribution du modèle actif (drift de dataset).

    Retourne ``None`` si aucune référence n'a encore été calculée (modèle
    entraîné avant l'introduction de la détection de drift, ou aucun modèle
    actif) : le drift est alors simplement ignoré, jamais bloquant.
    """
    chemin = settings.models_dir / "drift_reference.json"
    if not chemin.exists():
        return None
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def features_publiques(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Retourne les colonnes de rôle ``feature`` (celles saisies par l'utilisateur)."""
    return [c for c in schema.get("colonnes", []) if c.get("role") == "feature"]


def valider_entree(payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Valide et normalise une entrée de prédiction contre le schéma actif.

    - Vérifie que chaque feature est présente.
    - Vérifie le type (numérique → nombre) et l'appartenance aux valeurs autorisées
      (catégoriel / booléen).

    Returns:
        Un dictionnaire propre {feature: valeur} prêt pour la prédiction.

    Raises:
        ValueError: Si une ou plusieurs valeurs sont invalides.
    """
    erreurs: list[str] = []
    record: dict[str, Any] = {}

    for col in features_publiques(schema):
        nom, type_col = col["nom"], col["type"]

        if nom not in payload or payload[nom] is None or payload[nom] == "":
            erreurs.append(f"Champ requis manquant : {nom}")
            continue

        valeur = payload[nom]

        if type_col == "numerique":
            try:
                record[nom] = float(valeur)
            except (TypeError, ValueError):
                erreurs.append(f"« {nom} » doit être un nombre.")
        elif type_col in ("categoriel", "booleen"):
            valeurs = col.get("valeurs")
            if valeurs and valeur not in valeurs and str(valeur) not in [str(v) for v in valeurs]:
                erreurs.append(
                    f"« {nom} » : valeur '{valeur}' non autorisée "
                    f"(attendu : {valeurs})."
                )
            elif valeurs:
                # Coercition vers la valeur typée d'origine (ex. "1" -> 1).
                record[nom] = next(
                    (v for v in valeurs if v == valeur or str(v) == str(valeur)), valeur
                )
            else:
                record[nom] = valeur
        else:
            record[nom] = valeur

    if erreurs:
        raise ValueError(" ; ".join(erreurs))
    return record
