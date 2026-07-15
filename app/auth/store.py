"""Annuaire d'utilisateurs (Couche Authentification).

Stockage JSON local (``settings.users_file``), dans le même esprit que le
reste du projet (pas de base de données). Un compte admin est créé
automatiquement au premier démarrage, à partir de
``settings.admin_username`` / ``settings.admin_password``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.auth.passwords import hacher_mot_de_passe, verifier_mot_de_passe
from app.config import settings


@dataclass
class Utilisateur:
    username: str
    mot_de_passe_hash: str
    nom_complet: str
    role: str = "operateur"

    def public(self) -> dict[str, str]:
        return {"username": self.username, "nom_complet": self.nom_complet, "role": self.role}


def _chemin() -> Path:
    return settings.users_file


def _amorcer_si_absent(chemin: Path) -> None:
    """Crée l'annuaire avec un unique compte admin s'il n'existe pas encore."""
    if chemin.exists():
        return
    chemin.parent.mkdir(parents=True, exist_ok=True)
    admin = Utilisateur(
        username=settings.admin_username,
        mot_de_passe_hash=hacher_mot_de_passe(settings.admin_password),
        nom_complet="Administrateur",
        role="admin",
    )
    chemin.write_text(json.dumps({admin.username: asdict(admin)}, indent=2, ensure_ascii=False), encoding="utf-8")


def charger_utilisateurs() -> dict[str, Utilisateur]:
    chemin = _chemin()
    _amorcer_si_absent(chemin)
    brut: dict[str, dict[str, str]] = json.loads(chemin.read_text(encoding="utf-8"))
    return {nom: Utilisateur(**donnees) for nom, donnees in brut.items()}


def _sauvegarder(utilisateurs: dict[str, Utilisateur]) -> None:
    chemin = _chemin()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    brut = {nom: asdict(u) for nom, u in utilisateurs.items()}
    chemin.write_text(json.dumps(brut, indent=2, ensure_ascii=False), encoding="utf-8")


def trouver_utilisateur(username: str) -> Utilisateur | None:
    return charger_utilisateurs().get(username)


def authentifier(username: str, mot_de_passe: str) -> Utilisateur | None:
    utilisateur = trouver_utilisateur(username)
    if utilisateur is None:
        return None
    if not verifier_mot_de_passe(mot_de_passe, utilisateur.mot_de_passe_hash):
        return None
    return utilisateur


def creer_utilisateur(username: str, mot_de_passe: str, nom_complet: str, role: str = "operateur") -> Utilisateur:
    """Ajoute (ou remplace) un compte dans l'annuaire."""
    utilisateurs = charger_utilisateurs()
    utilisateur = Utilisateur(
        username=username,
        mot_de_passe_hash=hacher_mot_de_passe(mot_de_passe),
        nom_complet=nom_complet,
        role=role,
    )
    utilisateurs[username] = utilisateur
    _sauvegarder(utilisateurs)
    return utilisateur
