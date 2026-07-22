"""Codes de verification a usage unique, envoyes par email a la connexion.

Reutilise le hachage PBKDF2 existant (app/auth/passwords.py) plutot que
d'introduire un nouveau primitive de hachage : le cout (~260k iterations)
est negligeable pour une verification unitaire d'un code a 6 chiffres.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.auth.models import CodeOtp, Utilisateur
from app.auth.passwords import hacher_mot_de_passe, verifier_mot_de_passe
from app.config import settings

StatutOtp = Literal["ok", "invalide", "expire", "trop_de_tentatives"]


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def generer_code_otp(db: Session, utilisateur: Utilisateur) -> str:
    """Cree un nouveau code OTP pour l'utilisateur, invalide les precedents.

    Renvoie le code en clair (a transmettre par email immediatement) — seul
    son hash est conserve en base.
    """
    db.query(CodeOtp).filter(
        CodeOtp.utilisateur_id == utilisateur.id, CodeOtp.utilise.is_(False)
    ).update({"utilise": True})

    code = "".join(str(secrets.randbelow(10)) for _ in range(settings.otp_length))
    db.add(
        CodeOtp(
            utilisateur_id=utilisateur.id,
            code_hash=hacher_mot_de_passe(code),
            expires_at=_maintenant() + timedelta(minutes=settings.otp_expire_minutes),
        )
    )
    db.commit()
    return code


def valider_code_otp(db: Session, utilisateur: Utilisateur, code: str) -> StatutOtp:
    """Verifie le code fourni contre le dernier code actif de l'utilisateur."""
    otp = (
        db.query(CodeOtp)
        .filter(CodeOtp.utilisateur_id == utilisateur.id, CodeOtp.utilise.is_(False))
        .order_by(CodeOtp.created_at.desc())
        .first()
    )
    if otp is None:
        return "invalide"
    if otp.expires_at < _maintenant():
        otp.utilise = True
        db.commit()
        return "expire"
    if otp.tentatives >= settings.otp_max_attempts:
        otp.utilise = True
        db.commit()
        return "trop_de_tentatives"

    if not verifier_mot_de_passe(code, otp.code_hash):
        otp.tentatives += 1
        db.commit()
        return "invalide"

    otp.utilise = True
    db.commit()
    return "ok"


def peut_renvoyer_otp(db: Session, utilisateur: Utilisateur) -> bool:
    """Applique un delai minimal entre deux envois (anti-spam)."""
    dernier = (
        db.query(CodeOtp)
        .filter(CodeOtp.utilisateur_id == utilisateur.id)
        .order_by(CodeOtp.created_at.desc())
        .first()
    )
    if dernier is None:
        return True
    delai = timedelta(seconds=settings.otp_resend_cooldown_seconds)
    return _maintenant() >= dernier.created_at + delai
