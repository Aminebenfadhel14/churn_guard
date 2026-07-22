"""Émission et vérification des tokens de session (Couche Authentification).

JWT (HS256) signés avec ``settings.jwt_secret_key`` — sessions sans état,
adaptées à une API sans base de données.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


def creer_token(username: str) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": username, "exp": expiration}, settings.jwt_secret_key, algorithm="HS256")


def decoder_token(token: str) -> str | None:
    """Retourne le username porté par le token, ou ``None`` s'il est invalide/expiré."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


def creer_token_impersonation(username: str) -> str:
    """Token de session pour "se connecter en tant que" (admin -> employe).

    Un vrai token de session (decodable par ``decoder_token``, meme forme),
    mais avec une duree de vie plus courte : c'est une session de support
    ponctuelle, pas une connexion normale.
    """
    expiration = datetime.now(timezone.utc) + timedelta(minutes=settings.impersonation_expire_minutes)
    return jwt.encode({"sub": username, "exp": expiration}, settings.jwt_secret_key, algorithm="HS256")


def creer_token_otp(username: str) -> str:
    """Jeton intermédiaire "mot de passe vérifié, code OTP en attente".

    Distinct du token de session (``creer_token``) par le claim ``purpose`` :
    il ne peut pas servir à s'authentifier sur les endpoints protégés, seulement
    à prouver — le temps de sa courte durée de vie — que le mot de passe vient
    d'être vérifié, avant l'échange contre un vrai token via
    ``POST /auth/login/verify-otp``.
    """
    expiration = datetime.now(timezone.utc) + timedelta(minutes=settings.otp_challenge_expire_minutes)
    return jwt.encode(
        {"sub": username, "purpose": "otp", "exp": expiration}, settings.jwt_secret_key, algorithm="HS256"
    )


def decoder_token_otp(token: str) -> str | None:
    """Retourne le username porté par un token OTP valide, ou ``None`` sinon."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("purpose") != "otp":
        return None
    return payload.get("sub")
