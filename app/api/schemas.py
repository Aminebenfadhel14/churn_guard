"""Schémas Pydantic de l'API (Couche 4 — Serving)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ClientInput(BaseModel):
    """Caractéristiques brutes d'un client pour la prédiction."""

    CreditScore: int = Field(..., ge=300, le=900, examples=[619])
    Geography: Literal["France", "Spain", "Germany"] = Field(..., examples=["France"])
    Gender: Literal["Male", "Female"] = Field(..., examples=["Female"])
    Age: int = Field(..., ge=18, le=100, examples=[42])
    Tenure: int = Field(..., ge=0, le=15, examples=[2])
    Balance: float = Field(..., ge=0, examples=[0.0])
    NumOfProducts: int = Field(..., ge=1, le=4, examples=[1])
    HasCrCard: int = Field(..., ge=0, le=1, examples=[1])
    IsActiveMember: int = Field(..., ge=0, le=1, examples=[1])
    EstimatedSalary: float = Field(..., ge=0, examples=[101348.88])


class PredictionOutput(BaseModel):
    """Résultat d'une prédiction de churn."""

    risk_score: float = Field(..., description="Score de risque de 0 à 100.")
    prediction: int = Field(..., description="1 = churn probable, 0 = fidèle.")
    risk_level: Literal["faible", "moyen", "eleve"]
    modele: str = Field(..., description="Nom du modèle utilisé.")
