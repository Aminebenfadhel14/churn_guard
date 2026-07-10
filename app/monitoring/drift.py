"""Détection de drift de dataset (Couche Monitoring).

Compare la distribution d'un nouveau dataset uploadé à celle du dataset ayant
servi à entraîner le modèle actif, via le **Population Stability Index (PSI)**
— un indicateur standard en MLOps, calculable sans dépendance supplémentaire
(pas besoin de scipy : uniquement des quantiles pandas + un log).

Repères usuels (par colonne) :
- PSI < 0.10          : distribution stable.
- 0.10 <= PSI < 0.25  : dérive modérée, à surveiller.
- PSI >= 0.25         : dérive forte — le modèle actif risque d'être obsolète
  pour ce nouveau dataset ; un réentraînement est recommandé.

Usage :
- ``construire_reference`` est appelée une fois, juste après l'entraînement
  (``app.modeling.train``), et persistée par le model registry.
- ``detecter_drift`` est appelée à chaque nouvel upload (``POST /upload``)
  pour comparer le fichier déposé à cette référence.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

NB_BINS = 10
EPSILON = 1e-4
SEUIL_MODERE = 0.10
SEUIL_FORT = 0.25
MAX_COLONNES_RAPPORTEES = 15


def _est_numerique_continue(serie: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(serie) and serie.nunique(dropna=True) > 2


def _bornes_quantiles(serie: pd.Series) -> list[float]:
    """Bornes de déciles (uniques) pour découper une colonne numérique en classes.

    Les bornes extrêmes sont étendues à ±inf : une valeur inédite hors de la
    plage d'entraînement doit gonfler la classe extrême plutôt que d'être
    silencieusement ignorée (c'est justement le signal de drift le plus net).
    """
    valeurs = serie.dropna()
    if valeurs.empty:
        return [float("-inf"), float("inf")]

    quantiles = valeurs.quantile([i / NB_BINS for i in range(NB_BINS + 1)]).tolist()
    bornes = sorted({round(float(b), 10) for b in quantiles})
    if len(bornes) < 2:
        bornes = [float(valeurs.min()), float(valeurs.max())]
        if bornes[0] == bornes[1]:
            bornes[1] += 1e-9

    bornes[0] = float("-inf")
    bornes[-1] = float("inf")
    return bornes


def _proportions_numeriques(serie: pd.Series, bornes: list[float]) -> dict[str, float]:
    valeurs = serie.dropna()
    if valeurs.empty:
        return {}
    tranches = pd.cut(valeurs, bins=bornes, include_lowest=True, duplicates="drop")
    compte = tranches.value_counts(normalize=True, sort=False, dropna=True)
    return {str(k): float(v) for k, v in compte.items()}


def _proportions_categorielles(serie: pd.Series) -> dict[str, float]:
    valeurs = serie.dropna().astype(str)
    if valeurs.empty:
        return {}
    return valeurs.value_counts(normalize=True).to_dict()


def construire_reference(df: pd.DataFrame, colonnes: list[str]) -> dict[str, Any]:
    """Calcule la distribution de référence (par colonne) d'un dataset d'entraînement.

    Args:
        df: Dataset ayant servi à l'entraînement.
        colonnes: Colonnes à surveiller (typiquement les ``feature`` du schéma).

    Returns:
        Structure JSON-sérialisable persistée par le model registry.
    """
    colonnes_ref: dict[str, Any] = {}
    for nom in colonnes:
        if nom not in df.columns:
            continue
        serie = df[nom]
        if _est_numerique_continue(serie):
            bornes = _bornes_quantiles(serie)
            colonnes_ref[nom] = {
                "type": "numerique",
                "bornes": bornes,
                "proportions": _proportions_numeriques(serie, bornes),
            }
        else:
            colonnes_ref[nom] = {
                "type": "categoriel",
                "proportions": _proportions_categorielles(serie),
            }
    return {"n_lignes": int(len(df)), "colonnes": colonnes_ref}


def _psi(proportions_ref: dict[str, float], proportions_nouveau: dict[str, float]) -> float:
    """Population Stability Index entre deux distributions de proportions.

    ``epsilon`` évite les divisions par zéro / log(0) quand une classe est
    absente d'une des deux distributions (ex: nouvelle catégorie jamais vue
    à l'entraînement — cas qui doit justement faire grimper le PSI).
    """
    cles = set(proportions_ref) | set(proportions_nouveau)
    psi = 0.0
    for cle in cles:
        p_ref = max(proportions_ref.get(cle, 0.0), EPSILON)
        p_new = max(proportions_nouveau.get(cle, 0.0), EPSILON)
        psi += (p_new - p_ref) * math.log(p_new / p_ref)
    return psi


def _niveau(psi: float) -> str:
    if psi >= SEUIL_FORT:
        return "fort"
    if psi >= SEUIL_MODERE:
        return "modere"
    return "stable"


def detecter_drift(df_nouveau: pd.DataFrame, reference: dict[str, Any]) -> dict[str, Any]:
    """Compare un nouveau dataset à la référence d'entraînement (PSI par colonne).

    Args:
        df_nouveau: Dataset fraîchement uploadé.
        reference: Sortie de :func:`construire_reference` pour le modèle actif.

    Returns:
        ``{"niveau_global", "psi_moyen", "n_colonnes_analysees", "colonnes"}``,
        ``colonnes`` triées par PSI décroissant (les plus dérivées d'abord).
    """
    colonnes_drift: list[dict[str, Any]] = []
    for nom, ref_col in reference.get("colonnes", {}).items():
        if nom not in df_nouveau.columns:
            continue
        serie = df_nouveau[nom]
        if ref_col["type"] == "numerique":
            proportions_nouveau = _proportions_numeriques(serie, ref_col["bornes"])
        else:
            proportions_nouveau = _proportions_categorielles(serie)

        if not proportions_nouveau:
            continue

        psi = _psi(ref_col["proportions"], proportions_nouveau)
        colonnes_drift.append({
            "colonne": nom,
            "psi": round(psi, 4),
            "niveau": _niveau(psi),
        })

    colonnes_drift.sort(key=lambda c: c["psi"], reverse=True)
    n = len(colonnes_drift)
    psi_moyen = sum(c["psi"] for c in colonnes_drift) / n if n else 0.0
    n_fort = sum(1 for c in colonnes_drift if c["niveau"] == "fort")
    n_modere = sum(1 for c in colonnes_drift if c["niveau"] == "modere")

    if n_fort > 0:
        niveau_global = "fort"
    elif n_modere > 0:
        niveau_global = "modere"
    else:
        niveau_global = "stable"

    return {
        "niveau_global": niveau_global,
        "psi_moyen": round(psi_moyen, 4),
        "n_colonnes_analysees": n,
        "colonnes": colonnes_drift[:MAX_COLONNES_RAPPORTEES],
    }
