"""Feature engineering (Couche 2 — Processing).

Crée des variables dérivées susceptibles d'améliorer la prédiction du churn.
Chaque transformation est protégée : si les colonnes attendues sont absentes
(dataset d'un autre secteur), elle est simplement ignorée — la couche reste
donc universelle.
"""

from __future__ import annotations

import pandas as pd


def ajouter_features(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute des variables dérivées lorsque les colonnes sources existent.

    Variables créées (si possible) :
    - ``SoldeNul`` : 1 si le solde est nul (signal fort de désengagement bancaire).
    - ``RatioSoldeSalaire`` : solde rapporté au salaire estimé.
    - ``AncienneteRatioAge`` : part de la vie adulte passée avec l'entreprise.
    - ``ProduitsParAnciennete`` : intensité d'équipement dans le temps.
    """
    df = df.copy()
    colonnes = set(df.columns)

    if "Balance" in colonnes:
        df["SoldeNul"] = (df["Balance"] == 0).astype(int)

    if {"Balance", "EstimatedSalary"} <= colonnes:
        df["RatioSoldeSalaire"] = df["Balance"] / (df["EstimatedSalary"].abs() + 1.0)

    if {"Age", "Tenure"} <= colonnes:
        # +1 pour éviter la division par zéro sur de très jeunes âges.
        df["AncienneteRatioAge"] = df["Tenure"] / (df["Age"] + 1.0)

    if {"NumOfProducts", "Tenure"} <= colonnes:
        df["ProduitsParAnciennete"] = df["NumOfProducts"] / (df["Tenure"] + 1.0)

    return df
