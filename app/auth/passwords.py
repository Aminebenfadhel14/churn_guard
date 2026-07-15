"""Hachage des mots de passe (Couche Authentification).

PBKDF2-HMAC-SHA256 via la bibliothèque standard : pas de dépendance
supplémentaire, suffisant pour un petit annuaire d'utilisateurs local.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 260_000


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    """Retourne un hash au format ``sel$hash`` (les deux en hexadécimal)."""
    sel = secrets.token_hex(16)
    empreinte = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), bytes.fromhex(sel), _ITERATIONS)
    return f"{sel}${empreinte.hex()}"


def verifier_mot_de_passe(mot_de_passe: str, hash_stocke: str) -> bool:
    """Compare un mot de passe en clair au hash stocké (temps constant)."""
    try:
        sel, empreinte_attendue = hash_stocke.split("$", 1)
    except ValueError:
        return False
    empreinte = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), bytes.fromhex(sel), _ITERATIONS)
    return hmac.compare_digest(empreinte.hex(), empreinte_attendue)
