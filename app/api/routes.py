"""Routes de l'API REST (Couche 4 — Serving) — génériques et pilotées par le schéma.

- GET  /schema             : décrit les champs attendus (types, valeurs, bornes) du modèle actif.
- POST /predict            : prédit à partir d'un payload dynamique validé contre le schéma.
- POST /explain            : explique une prédiction (SHAP ou fallback d'ablation).
- POST /recommend          : suggère des actions de rétention priorisées (Next Best Actions).
- POST /what-if            : simule des changements de variables et calcule le delta de risque.
- GET  /clients/high-risk  : retourne la liste des clients présentant le plus haut risque de churn.
- POST /upload             : dépose un dataset (CSV/Excel/Parquet) dans data/ + aperçu du schéma.
- POST /train              : (ré)entraîne le pipeline sur le dernier dataset et publie le modèle actif.
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, File, HTTPException, UploadFile, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.schema_service import (
    charger_drift_reference,
    charger_schema_actif,
    features_publiques,
    valider_entree,
)
from app.auth import (
    Organisation,
    Utilisateur,
    authentifier,
    creer_organisation_avec_admin,
    creer_token,
    creer_token_impersonation,
    creer_token_otp,
    creer_utilisateur,
    decoder_token,
    decoder_token_otp,
    generer_code_otp,
    modifier_utilisateur,
    peut_renvoyer_otp,
    supprimer_utilisateur,
    trouver_utilisateur,
    trouver_utilisateur_par_email,
    valider_code_otp,
)
from app.auth.passwords import verifier_mot_de_passe
from app.config import settings
from app.db import get_db
from app.emailing import (
    envoyer_email_bienvenue,
    envoyer_email_confirmation_creation,
    envoyer_email_otp,
    envoyer_email_reinitialisation,
)
from app.ingestion import analyser_qualite, charger_dataset
from app.ingestion.schema_registry import construire_schema
from app.explainability import expliquer_prediction
from app.modeling.predict import charger_meta, charger_modele, predire
from app.monitoring.drift import detecter_drift
from app.recommendations import generer_recommandations_expertes, recommandations_de_secours
from app.recommendations import cache as recommandations_cache

router = APIRouter(tags=["ChurnGuard"])
logger = logging.getLogger(__name__)

EXTENSIONS_OK = {".csv", ".xlsx", ".xls", ".parquet"}

# ----- Configuration de la Sécurité par Clé API -----
API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def verifier_cle_api(api_key: str = Security(api_key_header)) -> str:
    """Dépendance FastAPI pour valider la clé API.

    Si la clé configurée est la valeur par défaut ("change-me-please") ou vide,
    l'accès est autorisé librement pour simplifier le développement local et les tests.
    Sinon, la clé transmise dans l'en-tête 'x-api-key' doit correspondre exactement.
    """
    if settings.api_key and settings.api_key != "change-me-please":
        if not api_key or api_key != settings.api_key:
            raise HTTPException(
                status_code=403,
                detail="Accès refusé : clé API invalide ou absente (en-tête 'x-api-key').",
            )
    return api_key


# ----- Sessions utilisateur (frontend web) -----
# Mécanisme additif à la clé API ci-dessus : les appels programmatiques (MCP,
# scripts) continuent d'utiliser 'x-api-key'. Les utilisateurs humains se
# connectent via /auth/login et obtiennent un token JWT.
bearer_scheme = HTTPBearer(auto_error=False)


def utilisateur_courant(
    identifiants: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> Utilisateur:
    """Dépendance FastAPI : résout l'utilisateur à partir du token de session."""
    username = decoder_token(identifiants.credentials) if identifiants else None
    if not username:
        raise HTTPException(status_code=401, detail="Authentification requise.")
    utilisateur = trouver_utilisateur(db, username)
    if utilisateur is None:
        raise HTTPException(status_code=401, detail="Session invalide.")
    return utilisateur


def utilisateur_admin(utilisateur: Utilisateur = Depends(utilisateur_courant)) -> Utilisateur:
    """Dépendance FastAPI : exige un compte de rôle "admin"."""
    if utilisateur.role != "admin":
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs.")
    return utilisateur


def utilisateur_optionnel(
    identifiants: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> Utilisateur | None:
    """Comme ``utilisateur_courant``, mais renvoie ``None`` au lieu de lever une
    erreur : pour les endpoints accessibles aussi par clé API (accès
    programmatique/MCP, sans session utilisateur), où le marquage de
    propriété (qui a uploadé/entraîné) est simplement absent dans ce cas."""
    username = decoder_token(identifiants.credentials) if identifiants else None
    if not username:
        return None
    return trouver_utilisateur(db, username)


def verifier_acces(
    api_key: str = Security(api_key_header),
    identifiants: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> None:
    """Autorise l'accès si une session utilisateur valide (JWT) est fournie,
    sinon retombe sur la vérification de la clé API existante."""
    if identifiants and decoder_token(identifiants.credentials):
        return
    verifier_cle_api(api_key)


_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _email_valide(email: str) -> bool:
    """Validation de format minimale (pas de verification RFC5322 complete)."""
    return bool(_EMAIL_REGEX.match(email))


def _masquer_email(email: str) -> str:
    """``jean.dupont@exemple.com`` -> ``j*****t@exemple.com`` (affichage cote frontend)."""
    local, _, domaine = email.partition("@")
    if len(local) <= 2:
        masque = local[0] + "*" * (len(local) - 1)
    else:
        masque = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masque}@{domaine}"


@router.post("/auth/login")
def login(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Authentifie un utilisateur.

    Si le compte a un email renseigne, la connexion s'arrete ici a une
    premiere etape : un code de verification est envoye par email, et
    c'est ``POST /auth/login/verify-otp`` qui delivre le vrai token de
    session. Sans email (comptes crees avant cette fonctionnalite), le
    comportement historique (token immediat) est conserve.

    L'identifiant saisi peut etre l'email (comptes crees par un admin,
    ou l'admin lui-meme) ou l'ancien username (comptes plus anciens).
    """
    identifiant = str(payload.get("email") or payload.get("username") or "").strip()
    mot_de_passe = str(payload.get("password", ""))
    utilisateur = authentifier(db, identifiant, mot_de_passe)
    if utilisateur is None:
        raise HTTPException(status_code=401, detail="Identifiants invalides.")

    if not utilisateur.email:
        return {
            "otp_required": False,
            "access_token": creer_token(utilisateur.username),
            "token_type": "bearer",
            "user": utilisateur.public(),
        }

    code = generer_code_otp(db, utilisateur)
    if not envoyer_email_otp(utilisateur.email, utilisateur.nom_complet, code):
        raise HTTPException(
            status_code=503, detail="Impossible d'envoyer le code de vérification, réessayez."
        )
    return {
        "otp_required": True,
        "challenge_token": creer_token_otp(utilisateur.username),
        "email_masque": _masquer_email(utilisateur.email),
    }


@router.post("/auth/login/verify-otp")
def verifier_otp(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Echange un code de verification valide contre un vrai token de session."""
    challenge_token = str(payload.get("challenge_token", ""))
    code = str(payload.get("code", "")).strip()

    username = decoder_token_otp(challenge_token)
    if not username:
        raise HTTPException(status_code=401, detail="Session de vérification expirée, reconnectez-vous.")
    utilisateur = trouver_utilisateur(db, username)
    if utilisateur is None:
        raise HTTPException(status_code=401, detail="Session de vérification expirée, reconnectez-vous.")

    statut = valider_code_otp(db, utilisateur, code)
    messages = {
        "invalide": "Code de vérification incorrect.",
        "expire": "Code de vérification expiré, demandez-en un nouveau.",
        "trop_de_tentatives": "Trop de tentatives, demandez un nouveau code.",
    }
    if statut != "ok":
        raise HTTPException(status_code=401, detail=messages[statut])

    return {
        "access_token": creer_token(utilisateur.username),
        "token_type": "bearer",
        "user": utilisateur.public(),
    }


@router.post("/auth/login/resend-otp")
def renvoyer_otp(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db)) -> dict[str, str]:
    """Renvoie un nouveau code de verification (avec delai anti-spam)."""
    challenge_token = str(payload.get("challenge_token", ""))
    username = decoder_token_otp(challenge_token)
    if not username:
        raise HTTPException(status_code=401, detail="Session de vérification expirée, reconnectez-vous.")
    utilisateur = trouver_utilisateur(db, username)
    if utilisateur is None or not utilisateur.email:
        raise HTTPException(status_code=401, detail="Session de vérification expirée, reconnectez-vous.")

    if not peut_renvoyer_otp(db, utilisateur):
        raise HTTPException(status_code=429, detail="Veuillez patienter avant de redemander un code.")

    code = generer_code_otp(db, utilisateur)
    if not envoyer_email_otp(utilisateur.email, utilisateur.nom_complet, code):
        raise HTTPException(
            status_code=503, detail="Impossible d'envoyer le code de vérification, réessayez."
        )
    return {"detail": "Code renvoyé."}


@router.get("/auth/me")
def me(utilisateur: Utilisateur = Depends(utilisateur_courant)) -> dict[str, str | None]:
    """Retourne l'utilisateur courant à partir du token de session (restauration de session)."""
    return utilisateur.public()


@router.patch("/auth/me")
def modifier_mon_compte(
    payload: dict[str, Any] = Body(...),
    utilisateur: Utilisateur = Depends(utilisateur_courant),
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    """Modification libre-service du compte connecté (nom, email, mot de passe).

    Contrairement à ``PATCH /auth/users/{username}`` (réservé aux admins),
    ici l'utilisateur modifie son propre compte : changer l'email ou le mot
    de passe exige de reconfirmer le mot de passe actuel, pour empêcher
    qu'une session volée ne verrouille durablement le vrai propriétaire.
    """
    nom_complet = payload.get("nom_complet")
    email = payload.get("email")
    nouveau_mot_de_passe = payload.get("password") or None
    mot_de_passe_actuel = str(payload.get("mot_de_passe_actuel", ""))

    champ_sensible = email is not None or nouveau_mot_de_passe is not None
    if champ_sensible and not verifier_mot_de_passe(mot_de_passe_actuel, utilisateur.mot_de_passe_hash):
        raise HTTPException(status_code=401, detail="Mot de passe actuel incorrect.")

    if email is not None:
        email = str(email).strip().lower()
        if not _email_valide(email):
            raise HTTPException(status_code=400, detail="Adresse email invalide.")
        autre = trouver_utilisateur_par_email(db, email)
        if autre is not None and autre.username != utilisateur.username:
            raise HTTPException(status_code=409, detail="Cette adresse email est déjà utilisée.")

    utilisateur_maj = modifier_utilisateur(
        db,
        organisation_id=utilisateur.organisation_id,
        username=utilisateur.username,
        nom_complet=str(nom_complet).strip() if nom_complet else None,
        mot_de_passe=str(nouveau_mot_de_passe) if nouveau_mot_de_passe else None,
        email=email,
    )
    assert utilisateur_maj is not None  # le compte courant existe forcement
    return utilisateur_maj.public()


@router.get("/auth/organisation")
def mon_organisation(
    utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Nom de l'organisation courante et nombre de membres."""
    organisation = db.query(Organisation).filter(Organisation.id == utilisateur.organisation_id).first()
    membres = (
        db.query(Utilisateur).filter(Utilisateur.organisation_id == utilisateur.organisation_id).count()
    )
    return {"nom": organisation.nom if organisation else "", "membres": membres}


@router.patch("/auth/organisation")
def renommer_organisation(
    payload: dict[str, Any] = Body(...),
    admin: Utilisateur = Depends(utilisateur_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Renomme l'organisation de l'admin connecté."""
    nom = str(payload.get("nom", "")).strip()
    if not nom:
        raise HTTPException(status_code=400, detail="Le nom de l'organisation est requis.")
    organisation = db.query(Organisation).filter(Organisation.id == admin.organisation_id).first()
    if organisation is None:
        raise HTTPException(status_code=404, detail="Organisation introuvable.")
    organisation.nom = nom
    db.commit()
    return {"nom": organisation.nom}


@router.post("/auth/signup")
def signup(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Inscription libre-service : crée une nouvelle organisation et son premier compte admin."""
    organisation_nom = str(payload.get("organisation_nom", "")).strip()
    username = str(payload.get("username", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    mot_de_passe = str(payload.get("password", ""))
    nom_complet = str(payload.get("nom_complet", "")).strip() or username

    if not organisation_nom or not username or not email or not mot_de_passe:
        raise HTTPException(
            status_code=400, detail="organisation_nom, username, email et password sont requis."
        )
    if not _email_valide(email):
        raise HTTPException(status_code=400, detail="Adresse email invalide.")
    if trouver_utilisateur(db, username) is not None:
        raise HTTPException(status_code=409, detail="Ce nom d'utilisateur est déjà pris.")
    if trouver_utilisateur_par_email(db, email) is not None:
        raise HTTPException(status_code=409, detail="Cette adresse email est déjà utilisée.")

    _organisation, admin = creer_organisation_avec_admin(
        db,
        nom_organisation=organisation_nom,
        username=username,
        mot_de_passe=mot_de_passe,
        nom_complet=nom_complet,
        email=email,
    )
    return {
        "access_token": creer_token(admin.username),
        "token_type": "bearer",
        "user": admin.public(),
    }


@router.post("/auth/users")
def creer_employe(
    background_tasks: BackgroundTasks,
    payload: dict[str, Any] = Body(...),
    admin: Utilisateur = Depends(utilisateur_admin),
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    """Crée un compte employé ("opérateur"), rattaché à l'organisation de l'admin connecté.

    Seul l'email est demandé : il sert aussi d'identifiant de connexion
    (``username`` = email), l'utilisateur n'a pas de nom d'utilisateur
    séparé à retenir. ``organisation_id`` et ``role`` sont fixés côté
    serveur (jamais depuis le payload client) : c'est ce qui garantit
    l'isolation entre organisations. Un email de bienvenue (identifiants
    inclus) est envoyé en tâche de fond à l'utilisateur, et un email de
    confirmation (sans les identifiants) à l'admin qui a créé le compte —
    un incident SMTP ne doit jamais empêcher la création du compte.
    """
    email = str(payload.get("email", "")).strip().lower()
    mot_de_passe = str(payload.get("password", ""))
    nom_complet = str(payload.get("nom_complet", "")).strip() or email

    if not email or not mot_de_passe:
        raise HTTPException(status_code=400, detail="email et password sont requis.")
    if not _email_valide(email):
        raise HTTPException(status_code=400, detail="Adresse email invalide.")
    if trouver_utilisateur_par_email(db, email) is not None:
        raise HTTPException(status_code=409, detail="Cette adresse email est déjà utilisée.")
    # L'email sert aussi de username : verifier ce champ aussi, car un
    # compte plus ancien (cree avant l'ajout de l'email) peut deja avoir
    # cette valeur comme username alors que son email est vide.
    if trouver_utilisateur(db, email) is not None:
        raise HTTPException(status_code=409, detail="Cette adresse email est déjà utilisée.")

    utilisateur = creer_utilisateur(
        db,
        organisation_id=admin.organisation_id,
        username=email,
        mot_de_passe=mot_de_passe,
        nom_complet=nom_complet,
        role="operateur",
        email=email,
    )
    background_tasks.add_task(envoyer_email_bienvenue, email, nom_complet, mot_de_passe)
    if admin.email:
        background_tasks.add_task(
            envoyer_email_confirmation_creation,
            admin.email,
            admin.nom_complet,
            nom_complet,
            email,
            "operateur",
        )
    return utilisateur.public()


@router.get("/auth/users")
def lister_employes(
    admin: Utilisateur = Depends(utilisateur_admin), db: Session = Depends(get_db)
) -> list[dict[str, str | None]]:
    """Liste les comptes de l'organisation de l'admin connecté."""
    membres = (
        db.query(Utilisateur)
        .filter(Utilisateur.organisation_id == admin.organisation_id)
        .order_by(Utilisateur.created_at)
        .all()
    )
    return [m.public() for m in membres]


ROLES_AUTORISES = {"admin", "operateur"}


@router.patch("/auth/users/{username}")
def modifier_employe(
    background_tasks: BackgroundTasks,
    username: str,
    payload: dict[str, Any] = Body(...),
    admin: Utilisateur = Depends(utilisateur_admin),
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    """Modifie un compte de l'organisation de l'admin connecté (nom, email, rôle, mot de passe).

    Si l'admin change le mot de passe, un email en avertit le titulaire du
    compte (sinon lui seul ne saurait jamais quel est son nouveau mot de
    passe) — même logique que l'email de bienvenue à la création.
    """
    nom_complet = payload.get("nom_complet")
    role = payload.get("role")
    mot_de_passe = payload.get("password") or None
    email = payload.get("email") or None

    if role is not None and role not in ROLES_AUTORISES:
        raise HTTPException(status_code=400, detail=f"Rôle invalide (attendu: {', '.join(ROLES_AUTORISES)}).")
    if username == admin.username and role is not None and role != "admin":
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas retirer votre propre rôle admin.")
    if email is not None:
        email = str(email).strip().lower()
        if not _email_valide(email):
            raise HTTPException(status_code=400, detail="Adresse email invalide.")
        autre = trouver_utilisateur_par_email(db, email)
        if autre is not None and autre.username != username:
            raise HTTPException(status_code=409, detail="Cette adresse email est déjà utilisée.")

    utilisateur = modifier_utilisateur(
        db,
        organisation_id=admin.organisation_id,
        username=username,
        nom_complet=str(nom_complet).strip() if nom_complet else None,
        role=role,
        mot_de_passe=str(mot_de_passe) if mot_de_passe else None,
        email=email,
    )
    if utilisateur is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    if mot_de_passe and utilisateur.email:
        background_tasks.add_task(
            envoyer_email_reinitialisation, utilisateur.email, utilisateur.nom_complet, str(mot_de_passe)
        )
    return utilisateur.public()


@router.delete("/auth/users/{username}")
def supprimer_employe(
    username: str,
    admin: Utilisateur = Depends(utilisateur_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Supprime un compte de l'organisation de l'admin connecté."""
    if username == admin.username:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte.")
    if not supprimer_utilisateur(db, organisation_id=admin.organisation_id, username=username):
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    return {"detail": "Utilisateur supprimé."}


@router.post("/auth/users/{username}/impersonate")
def se_connecter_en_tant_que(
    username: str,
    admin: Utilisateur = Depends(utilisateur_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ouvre une session sur le compte d'un employé, pour le support/dépannage.

    Aucun mot de passe ni code OTP requis : l'admin est déjà authentifié et
    autorisé sur son organisation, cette action ne fait qu'échanger son
    identité de session contre celle de l'employé, pour une durée limitée
    (voir ``settings.impersonation_expire_minutes``). Réservé aux comptes
    "opérateur" de la même organisation : un admin ne peut pas se connecter
    à la place d'un autre admin.
    """
    if username == admin.username:
        raise HTTPException(status_code=400, detail="Vous êtes déjà connecté à ce compte.")
    cible = (
        db.query(Utilisateur)
        .filter(Utilisateur.organisation_id == admin.organisation_id, Utilisateur.username == username)
        .first()
    )
    if cible is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    if cible.role == "admin":
        raise HTTPException(
            status_code=403, detail="Impossible de se connecter à la place d'un autre administrateur."
        )
    logger.info("Impersonation : admin %s -> utilisateur %s", admin.username, cible.username)
    return {
        "access_token": creer_token_impersonation(cible.username),
        "token_type": "bearer",
        "user": cible.public(),
    }


@router.get("/schema")
def get_schema() -> dict[str, Any]:
    """Schéma du modèle actif (utilisé par le frontend pour générer le formulaire)."""
    try:
        schema = charger_schema_actif()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "cible": schema.get("cible"),
        "type_probleme": schema.get("type_probleme"),
        "n_lignes": schema.get("n_lignes"),
        "features": [
            {
                "nom": c["nom"], "type": c["type"], "valeurs": c.get("valeurs"),
                "min": c.get("min"), "max": c.get("max"),
            }
            for c in features_publiques(schema)
        ],
    }


@router.post("/predict", dependencies=[Depends(verifier_acces)])
def predict(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Prédit à partir d'un payload dynamique (champs = schéma actif)."""
    try:
        schema = charger_schema_actif()
        record = valider_entree(payload, schema)
        return predire(record)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Erreur de prédiction : {exc}") from exc


@router.post("/explain", dependencies=[Depends(verifier_acces)])
def explain(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Explique une prédiction : contributions SHAP (ou fallback d'ablation).

    Accepte le même payload dynamique que ``/predict``. Paramètre optionnel
    ``top_k`` (défaut 5) pour limiter le nombre de facteurs retournés.
    """
    try:
        schema = charger_schema_actif()
        data = dict(payload)
        top_k = int(data.pop("top_k", 5))
        record = valider_entree(data, schema)
        return expliquer_prediction(record, top_k=top_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Erreur d'explication : {exc}") from exc


def _generer_recommandations(
    record: dict[str, Any],
    risk_score: float,
    risk_level: str,
) -> tuple[list[dict[str, Any]], str]:
    """Génère les recommandations de rétention via l'IA experte (Groq).

    L'IA reçoit les facteurs de risque SHAP exprimés avec les vraies colonnes
    du dataset chargé et rédige des actions concrètes, spécifiques au client
    et au métier déduit du schéma. Si le LLM est indisponible ou que l'appel
    échoue, repli silencieux sur un message de secours minimal (pas de
    moteur de règles).

    Un cache en mémoire (``app.recommendations.cache``) évite de rappeler le
    LLM pour un client déjà traité récemment : la clé combine son identifiant
    (si disponible) et son score de risque arrondi.
    """
    cle_cache = recommandations_cache.construire_cle(record, risk_score)
    en_cache = recommandations_cache.obtenir(cle_cache)
    if en_cache is not None:
        return en_cache

    try:
        explication = expliquer_prediction(record, top_k=6)
        recos_ia = generer_recommandations_expertes(
            risk_score, risk_level, explication.get("features", [])
        )
    except Exception:  # noqa: BLE001 — repli silencieux sur le message de secours
        recos_ia = None

    if recos_ia:
        resultat = (recos_ia, "rag")
    else:
        resultat = (recommandations_de_secours(risk_score, risk_level), "regles_secours")

    recommandations_cache.enregistrer(cle_cache, *resultat)
    return resultat


@router.post("/recommend", dependencies=[Depends(verifier_acces)])
def recommend(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Suggère des actions de rétention (Next Best Actions) priorisées pour un client.

    Accepte le même payload dynamique de caractéristiques client que ``/predict``.
    """
    try:
        schema = charger_schema_actif()
        record = valider_entree(payload, schema)

        # Effectue la prédiction pour obtenir le score de risque
        prediction = predire(record)
        risk_score = float(prediction["risk_score"])

        recos, source_recommendations = _generer_recommandations(
            record, risk_score, prediction["risk_level"]
        )

        return {
            "risk_score": risk_score,
            "risk_level": prediction["risk_level"],
            "prediction": prediction["prediction"],
            "modele": prediction["modele"],
            "recommendations": recos,
            "source_recommendations": source_recommendations,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Erreur de recommandation : {exc}") from exc


@router.post("/recommend/enriched", dependencies=[Depends(verifier_acces)])
def recommend_enriched(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Recommandations **enrichies** : actions de l'IA experte + plan de
    rétention rédigé par le moteur local de redaction.

    Seule la génération des actions appelle le LLM (Groq) ; le plan et
    l'email sont ensuite produits localement, sans appel externe.
    """
    try:
        schema = charger_schema_actif()
        record = valider_entree(payload, schema)

        prediction = predire(record)
        risk_score = float(prediction["risk_score"])
        recos, source_recommendations = _generer_recommandations(
            record, risk_score, prediction["risk_level"]
        )

        from app.recommendations.drafting import (
            generer_plan_retention,
            rediger_email_alerte,
        )

        plan = generer_plan_retention(
            record,
            risk_score,
            recos,
            risk_level=prediction["risk_level"],
            source_recommandations=source_recommendations,
        )
        email = rediger_email_alerte(
            record,
            risk_score,
            recos,
            risk_level=prediction["risk_level"],
            modele=prediction["modele"],
        )

        return {
            "risk_score": risk_score,
            "risk_level": prediction["risk_level"],
            "prediction": prediction["prediction"],
            "modele": prediction["modele"],
            "recommendations": recos,
            "plan_retention": plan,
            "email_alert": email,
            "source_plan": plan["source"],
            "source_email": email["source"],
            "source_recommendations": source_recommendations,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Erreur de recommandation enrichie : {exc}"
        ) from exc


@router.post("/copilot", dependencies=[Depends(verifier_acces)])
def copilot(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """**Retention Copilot** : traite un client de bout en bout.

    Enchaîne predict -> explain -> recommend, décide de l'escalade et renvoie
    une synthèse rédigée (par le LLM si configuré, sinon déterministe).
    Le payload est le même que ``/predict`` (les caractéristiques du client).
    """
    from app.copilot.agent import traiter_client

    resultat = traiter_client(payload)
    if not resultat.get("ok", False):
        raise HTTPException(status_code=400, detail=resultat.get("erreur", "Erreur copilot."))
    return resultat


@router.post("/copilot/chat", dependencies=[Depends(verifier_acces)])
def copilot_chat(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Assistant conversationnel du copilot : chat en langage naturel + tool-calling.

    Payload : ``{"messages": [{"role","content"}], "client": {...}}``.
    Le LLM choisit lui-même les outils (predict/explain/recommend/what-if…) et
    rédige une réponse. ``client`` (optionnel) fournit le client courant en contexte.
    """
    from app.copilot.chat import discuter

    messages = payload.get("messages", [])
    client = payload.get("client")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=422, detail="Champ 'messages' requis (liste non vide).")
    return discuter(messages, client=client if isinstance(client, dict) else None)


@router.post("/what-if", dependencies=[Depends(verifier_acces)])
def what_if(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Simule le score de risque d'un client suite à des modifications de variables.

    Format attendu :
    {
      "client": { ... caractéristiques actuelles du client ... },
      "overrides": { "nom_variable": nouvelle_valeur, ... }
    }
    """
    try:
        schema = charger_schema_actif()
        client_data = payload.get("client")
        overrides = payload.get("overrides")

        if client_data is None:
            raise ValueError("Le paramètre 'client' contenant le profil de base est obligatoire.")
        if overrides is None:
            raise ValueError("Le paramètre 'overrides' contenant les surcharges est obligatoire.")

        # Valider le profil d'origine
        record_orig = valider_entree(client_data, schema)

        # Créer et valider le profil modifié
        record_mod = dict(record_orig)
        for k, v in overrides.items():
            record_mod[k] = v
        record_mod = valider_entree(record_mod, schema)

        # Prédictions sur les deux états
        pred_orig = predire(record_orig)
        pred_mod = predire(record_mod)

        score_orig = float(pred_orig["risk_score"])
        score_mod = float(pred_mod["risk_score"])

        return {
            "original": {
                "risk_score": score_orig,
                "risk_level": pred_orig["risk_level"],
                "prediction": pred_orig["prediction"],
            },
            "simulated": {
                "risk_score": score_mod,
                "risk_level": pred_mod["risk_level"],
                "prediction": pred_mod["prediction"],
            },
            "delta": round(score_mod - score_orig, 2),
            "modele": pred_orig["modele"],
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Erreur de simulation What-If : {exc}") from exc


def _json_safe(v: Any) -> Any:
    """Convertit une valeur (potentiellement numpy) en type JSON-sérialisable."""
    import numpy as np
    import pandas as pd

    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def _dataset_du_modele_actif() -> Path:
    """Retourne le CSV de ``data/`` **compatible avec le modèle actif**.

    Le modèle attend des colonnes précises (rôle ``feature`` du schéma
    d'entraînement). On choisit donc le dataset qui les contient toutes, plutôt
    que le simple « dernier fichier uploadé » (qui peut correspondre à un autre
    modèle). À défaut de correspondance, on prend le plus récent.
    """
    from app.api.schema_service import charger_schema_actif, features_publiques

    csvs = sorted(
        settings.data_dir.glob("*.csv"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    if not csvs:
        raise HTTPException(
            status_code=400,
            detail="Aucun dataset. Uploade puis entraîne un modèle d'abord.",
        )

    try:
        requis = {c["nom"] for c in features_publiques(charger_schema_actif())}
    except Exception:  # noqa: BLE001 — schéma absent ou corrompu : repli sur le plus récent
        requis = set()

    if requis:
        for chemin in csvs:
            try:
                colonnes = set(charger_dataset(chemin).columns)
            except Exception:  # noqa: BLE001
                continue
            if requis <= colonnes:
                return chemin
    return csvs[0]


@router.get("/clients", dependencies=[Depends(verifier_acces)])
def get_clients(
    limit: int = 20,
    offset: int = 0,
    risk: str = "all",
    q: str = "",
) -> dict[str, Any]:
    """Liste **paginée** des clients du dataset actif, avec leur score de churn.

    Générique : fonctionne sur n'importe quel dataset. Score toutes les lignes
    avec le modèle actif, puis renvoie un identifiant de ligne, le score de
    risque, et une sélection de colonnes réelles à afficher.

    Args:
        limit: Nombre de lignes par page.
        offset: Décalage (pagination).
        risk: Filtre par niveau — ``all`` | ``faible`` | ``moyen`` | ``eleve``.
        q: Recherche plein-texte sur les colonnes affichées + l'identifiant.
    """
    try:
        from app.processing.features import ajouter_features
        from app.ingestion.schema import detecter_colonnes_id
        import pandas as pd
        import numpy as np

        chemin = _dataset_du_modele_actif()

        df = charger_dataset(chemin).copy()
        meta = charger_meta()
        cible = meta.get("cible", "")

        # Scoring vectorisé de toutes les lignes.
        pipeline = charger_modele()
        probas = pipeline.predict_proba(ajouter_features(df))[:, 1]
        df["risk_score"] = np.round(probas * 100, 1)

        # Identifiant de ligne + colonnes réelles à afficher (max 6).
        colonnes_id = detecter_colonnes_id(df, cible)
        id_col = colonnes_id[0] if colonnes_id else None
        exclues = set(colonnes_id) | {cible, "risk_score"}
        colonnes_affichage = [c for c in df.columns if c not in exclues][:6]

        # Filtre par niveau de risque (mêmes seuils que le badge du frontend :
        # faible < 30, moyen 30–70, élevé > 70).
        seuils = {"faible": (0.0, 30.0), "moyen": (30.0, 70.0001), "eleve": (70.0001, 101.0)}
        if risk in seuils:
            lo, hi = seuils[risk]
            df = df[(df["risk_score"] >= lo) & (df["risk_score"] < hi)]

        # Recherche plein-texte simple.
        if q.strip():
            ql = q.strip().lower()
            cols_rech = colonnes_affichage + ([id_col] if id_col else [])
            if cols_rech:
                masque = (
                    df[cols_rech].astype(str)
                    .apply(lambda s: s.str.lower().str.contains(ql, na=False))
                    .any(axis=1)
                )
                df = df[masque]

        # Tri par risque décroissant + pagination.
        df = df.sort_values(by="risk_score", ascending=False)
        total = int(len(df))
        page = df.iloc[max(0, offset): max(0, offset) + max(1, limit)]

        clients: list[dict[str, Any]] = []
        for idx, row in page.iterrows():
            rid = str(row[id_col]) if id_col else str(idx)
            clients.append({
                "id": rid,
                "risk_score": float(row["risk_score"]),
                "values": {c: _json_safe(row[c]) for c in colonnes_affichage},
            })

        return {
            "dataset": chemin.name,
            "cible": cible,
            "id_col": id_col,
            "colonnes": colonnes_affichage,
            "total": total,
            "offset": offset,
            "limit": limit,
            "clients": clients,
        }
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Aucun modèle actif. Lance un entraînement d'abord.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du listing des clients : {exc}",
        ) from exc


@router.get("/dashboard", dependencies=[Depends(verifier_acces)])
def get_dashboard() -> dict[str, Any]:
    """Agrégats du tableau de bord, calculés sur le dataset actif scoré.

    Générique et dynamique : KPI, répartition par niveau de risque, histogramme
    des scores et top-10 des clients à risque. Se met à jour à chaque changement
    de modèle actif.
    """
    try:
        from app.processing.features import ajouter_features
        from app.ingestion.schema import detecter_colonnes_id
        import numpy as np

        chemin = _dataset_du_modele_actif()
        df = charger_dataset(chemin).copy()
        meta = charger_meta()
        cible = meta.get("cible", "")

        pipeline = charger_modele()
        scores = np.round(pipeline.predict_proba(ajouter_features(df))[:, 1] * 100, 1)
        df["risk_score"] = scores
        total = int(len(df))

        # Répartition par niveau (mêmes seuils que le badge : <30, 30-70, >70).
        faible = int((scores < 30).sum())
        eleve = int((scores > 70).sum())
        moyen = total - faible - eleve
        distribution = [
            {"level": "Faible", "count": faible, "key": "faible"},
            {"level": "Moyen", "count": moyen, "key": "moyen"},
            {"level": "Élevé", "count": eleve, "key": "eleve"},
        ]

        # Histogramme : 10 tranches de 0 à 100.
        histogram = []
        for b in range(0, 100, 10):
            haut = (b + 10) if b < 90 else 100.1
            c = int(((scores >= b) & (scores < haut)).sum())
            histogram.append({"tranche": f"{b}–{b + 10}", "count": c})

        # KPI.
        churners = int((scores > 50).sum())
        stats = {
            "total": total,
            "at_risk_count": eleve,
            "at_risk_pct": round(eleve / total * 100, 1) if total else 0.0,
            "avg_churn_rate": round(churners / total * 100, 1) if total else 0.0,
            "avg_score": round(float(scores.mean()), 1) if total else 0.0,
        }

        # Top-10 clients à risque (générique : id + quelques colonnes réelles).
        colonnes_id = detecter_colonnes_id(df, cible)
        id_col = colonnes_id[0] if colonnes_id else None
        exclues = set(colonnes_id) | {cible, "risk_score"}
        colonnes = [c for c in df.columns if c not in exclues][:4]
        top = df.sort_values("risk_score", ascending=False).head(10)
        top_clients = [
            {
                "id": str(row[id_col]) if id_col else str(idx),
                "risk_score": float(row["risk_score"]),
                "values": {c: _json_safe(row[c]) for c in colonnes},
            }
            for idx, row in top.iterrows()
        ]

        return {
            "dataset": chemin.name,
            "cible": cible,
            "stats": stats,
            "distribution": distribution,
            "histogram": histogram,
            "id_col": id_col,
            "colonnes": colonnes,
            "top_clients": top_clients,
        }
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Aucun modèle actif. Lance un entraînement d'abord.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Erreur du tableau de bord : {exc}",
        ) from exc


@router.get("/clients/high-risk", dependencies=[Depends(verifier_acces)])
def get_high_risk_clients(limit: int = 10) -> dict[str, Any]:
    """Retourne la liste des clients présentant le plus haut risque de churn.

    Lit le dataset actif de manière vectorisée et renvoie le top `limit` des clients à haut risque.
    """
    try:
        from app.processing.features import ajouter_features
        import pandas as pd
        import numpy as np

        # Dataset compatible avec le modèle actif (pas juste le dernier uploadé).
        chemin = _dataset_du_modele_actif()

        df = charger_dataset(chemin)
        meta = charger_meta()
        cible = meta.get("cible", "")

        # Déterminer les colonnes d'identifiant pour l'affichage
        from app.ingestion.schema import detecter_colonnes_id
        colonnes_id = detecter_colonnes_id(df, cible)

        col_affichage = list(colonnes_id)
        if "Surname" in df.columns:
            col_affichage.append("Surname")
        if "Gender" in df.columns:
            col_affichage.append("Gender")
        if "Age" in df.columns:
            col_affichage.append("Age")

        # Prédiction vectorisée rapide sur tout le DataFrame
        pipeline = charger_modele()
        df_feats = ajouter_features(df)
        probas = pipeline.predict_proba(df_feats)[:, 1]
        df["risk_score"] = np.round(probas * 100, 1)

        # Trier par risque décroissant
        df_tri = df.sort_values(by="risk_score", ascending=False).head(limit)

        # Structurer la réponse JSON
        clients = []
        for idx, row in df_tri.iterrows():
            client_dict = row.to_dict()
            client_clean = {k: (None if pd.isna(v) else v) for k, v in client_dict.items()}

            id_client = str(client_clean.get(col_affichage[0])) if col_affichage else str(idx)
            nom_client = str(client_clean.get("Surname", f"Client {id_client}"))

            clients.append({
                "id": id_client,
                "name": nom_client,
                "risk_score": client_clean["risk_score"],
                "details": client_clean,
            })

        return {
            "dataset": chemin.name,
            "total_clients": len(df),
            "limit": limit,
            "clients": clients,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du listing des clients à risque : {exc}",
        ) from exc


def _ecrire_dataset(destination: Path, contenu: bytes) -> Path:
    """Écrit le dataset uploadé de façon robuste sous Windows.

    Gère le cas fréquent où le fichier cible existe déjà et est verrouillé
    (ouvert dans Excel) ou en lecture seule (``PermissionError``) :
    1) on tente de retirer l'attribut lecture seule puis d'écrire ;
    2) si l'écriture échoue quand même, on écrit sous un nom horodaté unique
       afin de ne jamais bloquer l'upload.
    Retourne le chemin réellement écrit.
    """
    def _tenter_ecriture(chemin: Path) -> None:
        if chemin.exists():
            try:  # retire un éventuel attribut "lecture seule"
                os.chmod(chemin, stat.S_IWRITE)
            except OSError:
                pass
        chemin.write_bytes(contenu)

    try:
        _tenter_ecriture(destination)
        return destination
    except PermissionError:
        horodatage = time.strftime("%Y%m%d_%H%M%S")
        secours = destination.with_name(
            f"{destination.stem}_{horodatage}{destination.suffix}"
        )
        _tenter_ecriture(secours)
        return secours


@router.post("/upload", dependencies=[Depends(verifier_acces)])
def upload(
    file: UploadFile = File(...),
    auto_train: bool = False,
    utilisateur: Utilisateur | None = Depends(utilisateur_optionnel),
) -> dict[str, Any]:
    """Dépose un dataset dans data/ et renvoie un aperçu du schéma détecté.

    L'entraînement **n'est pas** lancé automatiquement : il est déclenché
    ensuite par l'utilisateur via ``POST /train/start`` (bouton du frontend).

    Args:
        file: Le dataset (CSV/Excel/Parquet).
        auto_train: Optionnel. Si vrai, lance aussi l'entraînement dès l'upload
            (désactivé par défaut). Le suivi se fait via ``GET /train/status``.
    """
    nom = file.filename or "dataset.csv"
    ext = "." + nom.rsplit(".", 1)[-1].lower() if "." in nom else ""
    if ext not in EXTENSIONS_OK:
        raise HTTPException(
            status_code=422,
            detail=f"Format non supporté ({ext}). Attendu : {sorted(EXTENSIONS_OK)}.",
        )

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    destination = _ecrire_dataset(settings.data_dir / nom, file.file.read())
    nom = destination.name

    try:
        df = charger_dataset(destination)
        schema = construire_schema(df)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Fichier illisible : {exc}") from exc

    # Drift vs le dataset ayant servi à entraîner le modèle actif (s'il existe).
    # Purement informatif : un échec de calcul ne doit jamais bloquer l'upload.
    drift = None
    reference_drift = charger_drift_reference()
    if reference_drift:
        try:
            drift = detecter_drift(df, reference_drift)
        except Exception:  # noqa: BLE001
            drift = None

    reponse: dict[str, Any] = {
        "fichier": nom,
        "lignes": int(df.shape[0]),
        "colonnes": int(df.shape[1]),
        "cible_detectee": schema.cible,
        "type_probleme": schema.type_probleme,
        "features": [c.nom for c in schema.features()],
        "entrainement": "ignore",
        "drift": drift,
        "qualite": analyser_qualite(df, schema),
    }

    # Déclenche l'entraînement en arrière-plan : la requête répond tout de suite.
    if auto_train:
        from app.api.training_state import lancer_entrainement

        etat = lancer_entrainement(
            destination,
            username=utilisateur.username if utilisateur else None,
            organisation_id=utilisateur.organisation_id if utilisateur else None,
        )
        reponse["entrainement"] = etat["statut"]

    return reponse


@router.get("/train/status")
def train_status() -> dict[str, Any]:
    """Retourne l'état de l'entraînement en cours ou du dernier entraînement.

    Le frontend interroge ce endpoint après avoir lancé l'entraînement pour
    suivre la progression (statut ``en_cours`` → ``termine`` / ``echec``) et
    récupérer les métriques.
    """
    from app.api.training_state import etat_courant

    return etat_courant()


@router.post("/train/start", dependencies=[Depends(verifier_acces)])
def train_start(
    payload: dict[str, Any] = Body(default={}),
    utilisateur: Utilisateur | None = Depends(utilisateur_optionnel),
) -> dict[str, Any]:
    """Lance l'entraînement **en arrière-plan** sur le dataset choisi.

    Déclenché par le bouton « Lancer l'entraînement » du frontend. Répond
    immédiatement (pas de blocage) ; le suivi se fait via ``GET /train/status``.

    Args:
        payload: ``{"fichier": "<nom>"}`` pour cibler un fichier précis de
            ``data/`` ; sinon le dataset le plus récent est utilisé.
    """
    from app.api.training_state import lancer_entrainement

    fichier = payload.get("fichier")
    if fichier:
        chemin = settings.data_dir / fichier
        if not chemin.exists():
            raise HTTPException(status_code=404, detail=f"Fichier introuvable : {fichier}")
    else:
        csvs = sorted(
            settings.data_dir.glob("*.csv"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        if not csvs:
            raise HTTPException(
                status_code=400,
                detail="Aucun dataset dans data/. Uploade un fichier d'abord.",
            )
        chemin = csvs[0]

    return lancer_entrainement(
        chemin,
        username=utilisateur.username if utilisateur else None,
        organisation_id=utilisateur.organisation_id if utilisateur else None,
    )


@router.post("/train", dependencies=[Depends(verifier_acces)])
def train(
    payload: dict[str, Any] = Body(default={}),
    utilisateur: Utilisateur | None = Depends(utilisateur_optionnel),
) -> dict[str, Any]:
    """(Ré)entraîne le pipeline sur le dataset le plus récent de data/.

    Entraînement synchrone : peut prendre plusieurs minutes selon la taille.
    """
    from app.modeling.train import entrainer_et_selectionner, formater_resultat_entrainement

    fichier = payload.get("fichier")
    if fichier:
        chemin = settings.data_dir / fichier
        if not chemin.exists():
            raise HTTPException(status_code=404, detail=f"Fichier introuvable : {fichier}")
    else:
        csvs = sorted(
            settings.data_dir.glob("*.csv"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        if not csvs:
            raise HTTPException(status_code=400, detail="Aucun dataset dans data/. Uploade un fichier d'abord.")
        chemin = csvs[0]

    try:
        df = charger_dataset(chemin)
        res = entrainer_et_selectionner(
            df,
            nom_dataset=chemin.name,
            username=utilisateur.username if utilisateur else None,
            organisation_id=utilisateur.organisation_id if utilisateur else None,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Échec de l'entraînement : {exc}") from exc

    charger_modele.cache_clear()
    charger_meta.cache_clear()
    recommandations_cache.vider()

    return formater_resultat_entrainement(res, fichier=chemin.name)


# ----- Gestion multi-modeles (selecteur : banque, RH, telecom...) -----

# Libelles lisibles selon la cible du modele (extensible, sinon on retombe sur la cible).
_LABELS_CIBLE = {
    "Exited": "Banque - Churn client",
    "Attrition": "RH - Depart employe",
    # "Churn" est trop generique (telecom, e-commerce, SaaS...) : on ne le fige
    # pas ici, le libelle est alors deduit du nom du fichier du dataset.
}


def _libelle_modele(meta: dict[str, Any]) -> str:
    """Construit un libelle lisible pour un modele a partir de ses metadonnees.

    Ordre de priorite :
    1. Libelle sectoriel connu (banque / RH / telecom) selon la cible.
    2. Sinon, nom du fichier du dataset, nettoye (ex. "assurance_clients.csv"
       -> "Assurance Clients"), avec la cible entre parentheses.
    3. Sinon, un libelle deduit de la cible ("Prediction Lapse").
    Ainsi, meme un dataset jamais prevu obtient un nom clair dans le selecteur.
    """
    cible = str(meta.get("cible", "") or "").strip()
    base = _LABELS_CIBLE.get(cible)
    if base:
        return base

    fichier = str(meta.get("dataset", "") or "").strip()
    if fichier:
        nom = os.path.splitext(fichier)[0].replace("_", " ").replace("-", " ").strip()
        if nom:
            joli = nom.title()
            return f"{joli} ({cible})" if cible else joli

    return f"Prediction {cible}" if cible else "Modele"


def _modele_visible(meta: dict[str, Any], utilisateur: Utilisateur | None) -> bool:
    """Determine si un modele doit apparaitre dans la liste de cet utilisateur.

    - Acces programmatique (pas de session, ex. cle API/MCP) : tout est
      visible, comportement historique inchange pour ne pas casser les
      integrations existantes.
    - Operateur : uniquement les modeles qu'il a lui-meme entraines.
    - Admin : tous les modeles de sa propre organisation, y compris les
      anciens non rattaches a une organisation (entraines avant l'ajout de
      ce marquage) — jamais ceux d'une autre organisation.
    """
    if utilisateur is None:
        return True
    meta_org = meta.get("organisation_id")
    if utilisateur.role == "admin":
        return meta_org is None or meta_org == utilisateur.organisation_id
    return meta.get("username") == utilisateur.username


@router.get("/models", dependencies=[Depends(verifier_acces)])
def list_models(
    utilisateur: Utilisateur | None = Depends(utilisateur_optionnel),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Liste les modeles entraines disponibles dans le registre, filtree par
    utilisateur : un operateur ne voit que ses propres modeles, un admin voit
    tous ceux de son organisation (voir ``_modele_visible``).

    Chaque entree : version, libelle lisible, cible, algorithme, nb de variables,
    date, proprietaire et si c'est le modele actuellement actif. Le frontend
    s'en sert pour proposer un selecteur de modele (bascule banque / RH sans
    re-entrainer) ; un admin y voit en plus qui a entraine chaque modele.
    """
    from app.modeling.registry import lister_versions, version_active

    # Pour un admin, on resout le nom complet des proprietaires (les meta.json
    # ne stockent que le username/email) afin d'afficher "entraine par X" dans
    # le selecteur plutot qu'un identifiant technique.
    noms_complets: dict[str, str] = {}
    if utilisateur is not None and utilisateur.role == "admin":
        membres = (
            db.query(Utilisateur)
            .filter(Utilisateur.organisation_id == utilisateur.organisation_id)
            .all()
        )
        noms_complets = {m.username: m.nom_complet for m in membres}

    active = version_active()
    modeles: list[dict[str, Any]] = []
    for version in lister_versions():
        meta_path = settings.models_dir / "registry" / version / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not _modele_visible(meta, utilisateur):
            continue
        meta_username = meta.get("username")
        modeles.append(
            {
                "version": version,
                "label": _libelle_modele(meta),
                "cible": meta.get("cible"),
                "algorithme": meta.get("meilleur_modele"),
                "n_features": len(meta.get("colonnes_features", []) or []),
                "date": meta.get("date"),
                "actif": version == active,
                "username": meta_username,
                "proprietaire": noms_complets.get(meta_username) if meta_username else None,
            }
        )
    # Si le modele globalement actif n'est pas visible par cet utilisateur
    # (appartient a quelqu'un d'autre / une autre organisation), ne pas le
    # rapporter comme "actif" ici : le frontend n'a alors aucune entree
    # marquee "actif" (le <select> reste sur le premier de la liste filtree).
    active_visible = active if any(m["version"] == active for m in modeles) else None
    return {"active": active_visible, "total": len(modeles), "models": modeles}


@router.post("/models/activate", dependencies=[Depends(verifier_acces)])
def activate_model(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Bascule le modele actif vers une version du registre, sans re-entrainer.

    Body : {"version": "<id>"}. Recopie la version choisie en modele actif, puis
    vide les caches pour que prediction, explication et dashboard basculent
    immediatement (sans redemarrer l'API).
    """
    from app.modeling.registry import activer_version

    version = str(payload.get("version", "") or "").strip()
    if not version:
        raise HTTPException(status_code=422, detail="Champ requis manquant : version.")

    try:
        meta = activer_version(version)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Echec du changement de modele : {exc}") from exc

    charger_modele.cache_clear()
    charger_meta.cache_clear()
    recommandations_cache.vider()

    return {
        "ok": True,
        "active": version,
        "label": _libelle_modele(meta),
        "cible": meta.get("cible"),
        "algorithme": meta.get("meilleur_modele"),
    }


@router.delete("/models/{version}")
def delete_model(version: str, admin: Utilisateur = Depends(utilisateur_admin)) -> dict[str, str]:
    """Supprime une version entraînée du registre (admin uniquement).

    Réservé aux modèles de la propre organisation de l'admin (isolation
    multi-tenant, voir ``_modele_visible``) ; refuse de supprimer le modèle
    actuellement actif (il faut d'abord en activer un autre).
    """
    from app.modeling.registry import supprimer_version, version_active

    meta_path = settings.models_dir / "registry" / version / "meta.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Modèle introuvable.")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Métadonnées illisibles : {exc}") from exc

    if not _modele_visible(meta, admin):
        raise HTTPException(status_code=404, detail="Modèle introuvable.")
    if version == version_active():
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer le modèle actif : activez-en un autre d'abord.",
        )

    try:
        supprimer_version(version)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"detail": "Modèle supprimé."}


# ----- RAG (base de connaissances de retention) -----

@router.get("/rag/status", dependencies=[Depends(verifier_acces)])
def rag_status() -> dict[str, Any]:
    """Etat du RAG : dossier knowledge/, nombre d'extraits indexes, actif ou non."""
    from app.copilot import rag

    return rag.statut()


@router.post("/rag/reindex", dependencies=[Depends(verifier_acces)])
def rag_reindex() -> dict[str, Any]:
    """Force la reconstruction de l'index apres ajout/modif de documents."""
    from app.copilot import rag

    return rag.reindexer()




@router.get("/llm/status")
def llm_status(test: bool = True) -> dict[str, Any]:
    """Diagnostic : etat du LLM DANS LE PROCESS EN COURS + appel test reel a Groq.

    Ouvre http://127.0.0.1:8000/llm/status dans le navigateur. Si ``test=true``
    (defaut), fait un vrai appel minimal au LLM et renvoie le resultat ou
    l'erreur EXACTE de Groq (utile pour comprendre un fallback silencieux).
    """
    import httpx
    from app.copilot.llm import llm_disponible

    cle = settings.llm_api_key or ""
    infos: dict[str, Any] = {
        "llm_disponible": llm_disponible(),
        "cle_presente": bool(cle),
        "cle_debut": (cle[:4] + "...") if cle else "(vide)",
        "modele": settings.llm_model,
        "base_url": settings.llm_base_url,
    }

    if test and cle:
        try:
            with httpx.Client() as client:
                r = client.post(
                    f"{settings.llm_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {cle}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.llm_model,
                        "messages": [{"role": "user", "content": "Reponds juste: OK"}],
                        "temperature": 0.0,
                    },
                    timeout=30.0,
                )
            infos["test_http_status"] = r.status_code
            if r.status_code == 200:
                infos["test_ok"] = True
                infos["test_reponse"] = r.json()["choices"][0]["message"].get("content", "")[:120]
            else:
                infos["test_ok"] = False
                try:
                    infos["test_erreur"] = r.json().get("error", {}).get("message", r.text[:400])
                except Exception:  # noqa: BLE001
                    infos["test_erreur"] = r.text[:400]
        except Exception as exc:  # noqa: BLE001
            infos["test_ok"] = False
            infos["test_erreur"] = f"{type(exc).__name__}: {exc}"

    return infos


# Fin des routes ChurnGuard.
