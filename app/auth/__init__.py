"""Authentification — sessions utilisateur du frontend web.

Mécanisme additif à la clé API (``x-api-key``) existante : cette dernière
reste le canal d'accès programmatique (MCP, scripts), tandis que ce package
gère les sessions des utilisateurs humains via login + token JWT.

Point d'entrée principal : :func:`app.auth.store.authentifier` puis
:func:`app.auth.tokens.creer_token`.
"""

from __future__ import annotations

from app.auth.store import Utilisateur, authentifier, creer_utilisateur, trouver_utilisateur
from app.auth.tokens import creer_token, decoder_token

__all__ = [
    "Utilisateur",
    "authentifier",
    "creer_utilisateur",
    "trouver_utilisateur",
    "creer_token",
    "decoder_token",
]
