"""Moteur de recommandations — Next Best Actions.

Recommandations generees par un LLM expert relation client (Groq), a partir
des facteurs de risque SHAP du client et des VRAIES colonnes du dataset
charge. Un filet de securite minimal (``recommandations_de_secours``) prend
le relais si le LLM est indisponible.
"""

from __future__ import annotations

from app.recommendations.expert import (
    generer_recommandations_expertes,
    recommandations_de_secours,
)

__all__ = ["generer_recommandations_expertes", "recommandations_de_secours"]
