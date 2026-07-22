"""Authentification — sessions utilisateur du frontend web.

Mécanisme additif à la clé API (``x-api-key``) existante : cette dernière
reste le canal d'accès programmatique (MCP, scripts), tandis que ce package
gère les sessions des utilisateurs humains via login + token JWT.

Multi-organisation : chaque utilisateur appartient à une ``Organisation``
(tenant) — voir ``app/auth/models.py``.

Point d'entrée principal : :func:`app.auth.store.authentifier` puis
:func:`app.auth.tokens.creer_token`.
"""

from __future__ import annotations

from app.auth.models import CodeOtp
from app.auth.otp import generer_code_otp, peut_renvoyer_otp, valider_code_otp
from app.auth.store import (
    Organisation,
    Utilisateur,
    amorcer_organisation_defaut,
    authentifier,
    creer_organisation_avec_admin,
    creer_utilisateur,
    modifier_utilisateur,
    supprimer_utilisateur,
    trouver_utilisateur,
    trouver_utilisateur_par_email,
)
from app.auth.tokens import (
    creer_token,
    creer_token_impersonation,
    creer_token_otp,
    decoder_token,
    decoder_token_otp,
)

__all__ = [
    "CodeOtp",
    "Organisation",
    "Utilisateur",
    "amorcer_organisation_defaut",
    "authentifier",
    "creer_organisation_avec_admin",
    "creer_utilisateur",
    "modifier_utilisateur",
    "supprimer_utilisateur",
    "trouver_utilisateur",
    "trouver_utilisateur_par_email",
    "creer_token",
    "creer_token_impersonation",
    "creer_token_otp",
    "decoder_token",
    "decoder_token_otp",
    "generer_code_otp",
    "peut_renvoyer_otp",
    "valider_code_otp",
]
