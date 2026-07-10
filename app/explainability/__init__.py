"""Couche d'explicabilité — SHAP.

Explique chaque prédiction individuelle (TreeExplainer) avec un repli simple
si SHAP échoue.
"""

from app.explainability.explain import expliquer_prediction

__all__ = ["expliquer_prediction"]
