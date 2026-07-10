"""Explicabilité des prédictions via SHAP (Couche 4 — Serving).

Calcule les contributions de chaque variable à une prédiction individuelle.
Utilise ``TreeExplainer`` (ou ``LinearExplainer``) lorsque le modèle le permet ;
sinon, bascule sur une méthode d'ablation simple (variation de probabilité).
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from app.api.schema_service import charger_schema_actif, features_publiques
from app.modeling.predict import charger_meta, charger_modele, niveau_risque, predire
from app.processing.features import ajouter_features

# Modèles scikit-learn / tiers compatibles avec TreeExplainer.
_TYPES_ARBRE = (
    "RandomForestClassifier",
    "ExtraTreesClassifier",
    "GradientBoostingClassifier",
    "HistGradientBoostingClassifier",
    "DecisionTreeClassifier",
    "XGBClassifier",
    "LGBMClassifier",
    "CatBoostClassifier",
)
_TYPES_LINEAIRES = ("LogisticRegression", "LinearRegression")


def _preparer_dataframe(record: dict[str, Any]) -> pd.DataFrame:
    """Reproduit le feature engineering appliqué à l'entraînement."""
    df = pd.DataFrame([record])
    return ajouter_features(df)


def _extraire_etapes(pipeline: Any) -> tuple[Any, Any]:
    """Retourne (préprocesseur, modèle) depuis le pipeline entraîné."""
    preprocesseur = pipeline.named_steps.get("preprocesseur")
    modele = pipeline.named_steps.get("modele")
    if preprocesseur is None or modele is None:
        raise ValueError("Pipeline invalide : étapes « preprocesseur » ou « modele » absentes.")
    return preprocesseur, modele


def _type_modele(modele: Any) -> str:
    """Nom de la classe du modèle (dernier estimateur du pipeline)."""
    return type(modele).__name__


def _est_modele_arbre(modele: Any) -> bool:
    return _type_modele(modele) in _TYPES_ARBRE


def _est_modele_lineaire(modele: Any) -> bool:
    return _type_modele(modele) in _TYPES_LINEAIRES


def _nettoyer_nom_colonne(nom: str) -> str:
    """Retire le BOM UTF-8 et les préfixes sklearn (num__, cat__)."""
    nom = nom.lstrip("\ufeff")
    for prefixe in ("num__", "cat__", "remainder__"):
        if nom.startswith(prefixe):
            nom = nom[len(prefixe) :]
    return nom


def _libelle_feature(nom: str) -> str:
    """Convertit un nom technique en libellé lisible (français)."""
    nom_propre = _nettoyer_nom_colonne(nom)
    nom_propre = re.sub(r"([a-z])([A-Z])", r"\1 \2", nom_propre)
    nom_propre = nom_propre.replace("_", " ").strip()
    return nom_propre[:1].upper() + nom_propre[1:] if nom_propre else nom


def _decrire_feature(nom: str, valeur: Any, schema_col: dict[str, Any] | None) -> str:
    """Génère une phrase d'explication contextualisée."""
    libelle = _libelle_feature(nom)
    if schema_col and schema_col.get("type") == "numerique":
        mini, maxi = schema_col.get("min"), schema_col.get("max")
        if mini is not None and maxi is not None:
            return f"{libelle} = {valeur} (plage observée : {mini} – {maxi})."
    if schema_col and schema_col.get("valeurs"):
        return f"{libelle} = « {valeur} » parmi {schema_col['valeurs']}."
    return f"{libelle} = {valeur}."


def _schema_par_feature(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Indexe les métadonnées de schéma par nom de colonne."""
    return {c["nom"]: c for c in features_publiques(schema)}


def _valeur_reference(col: dict[str, Any]) -> Any:
    """Valeur « neutre » utilisée par le fallback d'ablation."""
    if col.get("type") == "numerique":
        mini, maxi = col.get("min"), col.get("max")
        if mini is not None and maxi is not None:
            return (float(mini) + float(maxi)) / 2.0
        return 0.0
    valeurs = col.get("valeurs") or []
    return valeurs[0] if valeurs else ""


def _agreger_shap_vers_brut(
    noms_transformes: np.ndarray,
    shap_vals: np.ndarray,
    record: dict[str, Any],
) -> dict[str, float]:
    """Regroupe les contributions one-hot vers les colonnes brutes."""
    contributions: dict[str, float] = {}
    for nom_tf, val_shap in zip(noms_transformes, shap_vals, strict=True):
        nom_brut = _nettoyer_nom_colonne(str(nom_tf))
        # One-hot : « Geography_France » → « Geography »
        if nom_brut not in record:
            for cle in record:
                if nom_brut.startswith(f"{cle}_") or nom_brut == cle:
                    nom_brut = cle
                    break
        contributions[nom_brut] = contributions.get(nom_brut, 0.0) + float(val_shap)
    return contributions


def _convertir_shap_en_points(
    contributions: dict[str, float],
    risk_score: float,
) -> dict[str, float]:
    """Met à l'échelle les valeurs SHAP en points de score de risque (0–100)."""
    total_abs = sum(abs(v) for v in contributions.values())
    if total_abs <= 1e-12:
        return {k: 0.0 for k in contributions}
    # Proportionnel à l'écart par rapport au seuil médian (50).
    ecart = risk_score - 50.0
    facteur = ecart / total_abs if abs(ecart) > 1e-6 else 1.0 / total_abs
    return {k: round(v * facteur, 2) for k, v in contributions.items()}


def _expliquer_shap(
    pipeline: Any,
    df: pd.DataFrame,
    record: dict[str, Any],
    risk_score: float,
) -> tuple[dict[str, float], float | None]:
    """Tente une explication SHAP sur les features transformées."""
    import shap

    preprocesseur, modele = _extraire_etapes(pipeline)
    X_trans = preprocesseur.transform(df)
    noms = preprocesseur.get_feature_names_out()

    shap_vals: np.ndarray
    base_value: float | None = None

    if _est_modele_arbre(modele):
        explainer = shap.TreeExplainer(modele)
        raw = explainer.shap_values(X_trans)
        base_raw = explainer.expected_value
    elif _est_modele_lineaire(modele):
        explainer = shap.LinearExplainer(modele, X_trans)
        raw = explainer.shap_values(X_trans)
        base_raw = explainer.expected_value
    else:
        raise ValueError(f"Modèle {_type_modele(modele)} non supporté par SHAP.")

    # Classification binaire : SHAP renvoie souvent une liste [classe0, classe1].
    if isinstance(raw, list):
        shap_vals = np.asarray(raw[1 if len(raw) > 1 else 0]).reshape(-1)
        if isinstance(base_raw, (list, np.ndarray)):
            base_value = float(np.asarray(base_raw)[-1])
        else:
            base_value = float(base_raw) if base_raw is not None else None
    else:
        shap_vals = np.asarray(raw).reshape(-1)
        if isinstance(base_raw, (list, np.ndarray)):
            base_value = float(np.mean(base_raw))
        elif base_raw is not None:
            base_value = float(base_raw)

    brutes = _agreger_shap_vers_brut(noms, shap_vals, record)
    return _convertir_shap_en_points(brutes, risk_score), base_value


def _expliquer_fallback(
    record: dict[str, Any],
    schema: dict[str, Any],
    proba_ref: float,
) -> dict[str, float]:
    """Ablation simple : impact de chaque variable vs une valeur de référence."""
    meta_cols = _schema_par_feature(schema)
    contributions: dict[str, float] = {}

    for nom, col in meta_cols.items():
        if nom not in record:
            continue
        modifie = dict(record)
        modifie[nom] = _valeur_reference(col)
        df_mod = _preparer_dataframe(modifie)
        pipeline = charger_modele()
        proba_mod = float(pipeline.predict_proba(df_mod)[0, 1])
        # Positive = la valeur actuelle augmente le risque vs la référence.
        contributions[nom] = round((proba_ref - proba_mod) * 100, 2)

    return contributions


def _construire_reponse_features(
    contributions: dict[str, float],
    record: dict[str, Any],
    schema: dict[str, Any],
    top_k: int,
) -> list[dict[str, Any]]:
    """Formate les top-k contributions pour l'API."""
    meta_cols = _schema_par_feature(schema)
    triees = sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)

    features: list[dict[str, Any]] = []
    for nom, contrib in triees[:top_k]:
        col = meta_cols.get(nom)
        # Cherche aussi sans BOM si le schéma contient un nom encodé.
        if col is None:
            for cle, meta in meta_cols.items():
                if _nettoyer_nom_colonne(cle) == _nettoyer_nom_colonne(nom):
                    col = meta
                    break
        valeur = record.get(nom, record.get(_nettoyer_nom_colonne(nom), ""))
        features.append({
            "feature": _nettoyer_nom_colonne(nom),
            "label": _libelle_feature(nom),
            "contribution": round(contrib, 2),
            "description": _decrire_feature(nom, valeur, col),
            "value": valeur,
        })
    return features


def expliquer_prediction(
    record: dict[str, Any],
    *,
    top_k: int = 5,
) -> dict[str, Any]:
    """Explique une prédiction individuelle.

    Args:
        record: Caractéristiques brutes validées (même format que ``/predict``).
        top_k: Nombre de facteurs les plus influents à retourner.

    Returns:
        Dictionnaire avec score, méthode utilisée (``shap`` ou ``fallback``)
        et la liste des contributions signées (positif = augmente le risque).
    """
    if top_k < 1:
        raise ValueError("top_k doit être >= 1.")

    schema = charger_schema_actif()
    pipeline = charger_modele()
    df = _preparer_dataframe(record)

    prediction = predire(record)
    risk_score = float(prediction["risk_score"])
    proba_ref = risk_score / 100.0

    methode = "fallback"
    base_value: float | None = None
    contributions: dict[str, float]

    try:
        contributions, base_value = _expliquer_shap(pipeline, df, record, risk_score)
        methode = "shap"
    except Exception:
        contributions = _expliquer_fallback(record, schema, proba_ref)

    features = _construire_reponse_features(contributions, record, schema, top_k)

    return {
        "risk_score": risk_score,
        "prediction": prediction["prediction"],
        "risk_level": prediction["risk_level"],
        "modele": prediction["modele"],
        "method": methode,
        "base_value": base_value,
        "features": features,
    }
