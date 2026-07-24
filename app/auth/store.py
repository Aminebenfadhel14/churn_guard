"""Annuaire d'utilisateurs (Couche Authentification).

Stockage en base de donnees (SQLite en local, Postgres en production —
voir ``app/db.py``). Chaque utilisateur appartient a une ``Organisation``
(tenant) ; le username reste unique globalement (pas de selecteur
d'organisation au login).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth.models import Organisation, Utilisateur
from app.auth.passwords import hacher_mot_de_passe, verifier_mot_de_passe
from app.config import settings

__all__ = [
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
    "trouver_utilisateur_par_identifiant",
]


def trouver_utilisateur(db: Session, username: str) -> Utilisateur | None:
    return db.query(Utilisateur).filter(Utilisateur.username == username).first()


def trouver_utilisateur_par_email(db: Session, email: str) -> Utilisateur | None:
    return db.query(Utilisateur).filter(Utilisateur.email == email).first()


def trouver_utilisateur_par_identifiant(db: Session, identifiant: str) -> Utilisateur | None:
    """Cherche par email d'abord (comptes crees par un admin : username == email),
    puis par username (comptes plus anciens, ou admin auto-amorce sans email)."""
    utilisateur = trouver_utilisateur_par_email(db, identifiant.lower())
    if utilisateur is not None:
        return utilisateur
    return trouver_utilisateur(db, identifiant)


def authentifier(db: Session, identifiant: str, mot_de_passe: str) -> Utilisateur | None:
    utilisateur = trouver_utilisateur_par_identifiant(db, identifiant)
    if utilisateur is None:
        return None
    if not verifier_mot_de_passe(mot_de_passe, utilisateur.mot_de_passe_hash):
        return None
    return utilisateur


def creer_utilisateur(
    db: Session,
    organisation_id: int,
    username: str,
    mot_de_passe: str,
    nom_complet: str,
    role: str = "operateur",
    email: str | None = None,
    mot_de_passe_temporaire: bool = False,
) -> Utilisateur:
    """Ajoute un compte, rattache a une organisation existante.

    ``mot_de_passe_temporaire`` marque le mot de passe comme provisoire :
    l'utilisateur sera force de le changer a sa premiere connexion (comptes
    crees par un admin, voir app/api/routes.py::creer_employe).
    """
    utilisateur = Utilisateur(
        organisation_id=organisation_id,
        username=username,
        email=email,
        mot_de_passe_hash=hacher_mot_de_passe(mot_de_passe),
        nom_complet=nom_complet,
        role=role,
        mot_de_passe_temporaire=mot_de_passe_temporaire,
    )
    db.add(utilisateur)
    db.commit()
    db.refresh(utilisateur)
    return utilisateur


def creer_organisation_avec_admin(
    db: Session,
    nom_organisation: str,
    username: str,
    mot_de_passe: str,
    nom_complet: str,
    email: str | None = None,
) -> tuple[Organisation, Utilisateur]:
    """Cree une nouvelle organisation avec son premier compte admin (inscription libre-service)."""
    organisation = Organisation(nom=nom_organisation)
    db.add(organisation)
    db.flush()  # attribue organisation.id sans terminer la transaction
    admin = Utilisateur(
        organisation_id=organisation.id,
        username=username,
        email=email,
        mot_de_passe_hash=hacher_mot_de_passe(mot_de_passe),
        nom_complet=nom_complet,
        role="admin",
    )
    db.add(admin)
    db.commit()
    db.refresh(organisation)
    db.refresh(admin)
    return organisation, admin


def modifier_utilisateur(
    db: Session,
    organisation_id: int,
    username: str,
    nom_complet: str | None = None,
    role: str | None = None,
    mot_de_passe: str | None = None,
    email: str | None = None,
    mot_de_passe_temporaire: bool | None = None,
) -> Utilisateur | None:
    """Met a jour un compte de l'organisation donnee. Renvoie None si introuvable.

    Seuls les champs fournis (non None) sont modifies. ``mot_de_passe_temporaire``
    est explicite (et non deduit du changement de mot de passe) car sa valeur
    depend de l'appelant : un admin qui reinitialise le remet a True, un
    utilisateur qui change lui-meme le remet a False.
    """
    utilisateur = (
        db.query(Utilisateur)
        .filter(Utilisateur.organisation_id == organisation_id, Utilisateur.username == username)
        .first()
    )
    if utilisateur is None:
        return None
    if nom_complet is not None:
        utilisateur.nom_complet = nom_complet
    if role is not None:
        utilisateur.role = role
    if mot_de_passe is not None:
        utilisateur.mot_de_passe_hash = hacher_mot_de_passe(mot_de_passe)
    if email is not None:
        utilisateur.email = email
    if mot_de_passe_temporaire is not None:
        utilisateur.mot_de_passe_temporaire = mot_de_passe_temporaire
    db.commit()
    db.refresh(utilisateur)
    return utilisateur


def supprimer_utilisateur(db: Session, organisation_id: int, username: str) -> bool:
    """Supprime un compte de l'organisation donnee. Renvoie False si introuvable."""
    utilisateur = (
        db.query(Utilisateur)
        .filter(Utilisateur.organisation_id == organisation_id, Utilisateur.username == username)
        .first()
    )
    if utilisateur is None:
        return False
    db.delete(utilisateur)
    db.commit()
    return True


def amorcer_organisation_defaut(db: Session) -> None:
    """Cree l'organisation "Default" et son admin (depuis settings) si la base est vide.

    Preserve le comportement historique (admin unique auto-cree au premier
    demarrage) pour les deploiements qui n'utilisent pas l'inscription
    libre-service.
    """
    if db.query(Organisation).first() is not None:
        return
    creer_organisation_avec_admin(
        db,
        nom_organisation="Default",
        username=settings.admin_username,
        mot_de_passe=settings.admin_password,
        nom_complet="Administrateur",
    )
