"""Envoi d'emails transactionnels (bienvenue, code de verification).

Le backend est en Python : l'envoi effectif (nodemailer) est delegue a une
route interne du frontend Next.js (voir
frontend/app/api/internal/send-email/route.ts), protegee par un secret
partage transmis en en-tete. Cet appel HTTP synchrone suit la meme
convention que les autres appels sortants du backend (voir
app/api/routes.py, section /llm/status : ``with httpx.Client() as client``).
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_HEADERS = {"X-Internal-Secret": settings.email_service_secret}


def _envoyer(payload: dict[str, str]) -> bool:
    try:
        with httpx.Client(timeout=10) as client:
            reponse = client.post(settings.email_service_url, json=payload, headers=_HEADERS)
        if reponse.status_code >= 400:
            logger.error("Echec envoi email (%s) : %s", payload.get("type"), reponse.status_code)
            return False
        return True
    except httpx.HTTPError:
        logger.exception("Echec envoi email (%s) : service injoignable.", payload.get("type"))
        return False


def envoyer_email_bienvenue(email: str, nom_complet: str, mot_de_passe: str) -> bool:
    """Notifie un utilisateur nouvellement cree par un admin, avec ses identifiants.

    Pas de username separe : l'email sert lui-meme d'identifiant de connexion.
    """
    return _envoyer(
        {
            "type": "bienvenue",
            "to": email,
            "nom_complet": nom_complet,
            "mot_de_passe": mot_de_passe,
        }
    )


def envoyer_email_reinitialisation(email: str, nom_complet: str, mot_de_passe: str) -> bool:
    """Notifie un utilisateur que son mot de passe a ete reinitialise par un admin."""
    return _envoyer(
        {
            "type": "reinitialisation",
            "to": email,
            "nom_complet": nom_complet,
            "mot_de_passe": mot_de_passe,
        }
    )


def envoyer_email_confirmation_creation(
    email_admin: str, nom_admin: str, nom_nouvel_utilisateur: str, email_nouvel_utilisateur: str, role: str
) -> bool:
    """Confirme a l'admin la creation d'un compte (recapitulatif, pas les identifiants)."""
    return _envoyer(
        {
            "type": "confirmation_creation",
            "to": email_admin,
            "nom_admin": nom_admin,
            "nom_nouvel_utilisateur": nom_nouvel_utilisateur,
            "email_nouvel_utilisateur": email_nouvel_utilisateur,
            "role": role,
        }
    )


def envoyer_email_otp(email: str, nom_complet: str, code: str) -> bool:
    """Envoie le code de verification a la connexion."""
    return _envoyer(
        {
            "type": "otp",
            "to": email,
            "nom_complet": nom_complet,
            "code": code,
            "expire_minutes": str(settings.otp_expire_minutes),
        }
    )
