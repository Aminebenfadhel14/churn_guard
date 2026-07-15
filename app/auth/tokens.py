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
