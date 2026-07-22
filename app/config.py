"""Configuration centrale de ChurnGuard.

Toutes les valeurs sont surchargeables via des variables d'environnement
(prefixe ``CHURNGUARD_``) ou un fichier ``.env`` place a la racine du projet.
Aucun secret ne doit etre ecrit en dur : voir ``.env.example``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Racine du projet (dossier contenant ce package "app").
BASE_DIR: Path = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Parametres applicatifs charges depuis l'environnement / .env."""

    # ----- Metadonnees de l'application -----
    app_name: str = "ChurnGuard"
    app_version: str = "0.1.0"
    debug: bool = False

    # ----- Securite de l'API -----
    # Cle attendue dans l'en-tete HTTP des requetes protegees.
    api_key: str = "change-me-please"

    # ----- Authentification (sessions utilisateur du frontend web) -----
    # Compte admin cree automatiquement au premier demarrage si users.json
    # n'existe pas encore (voir app/auth/store.py). A changer en production.
    admin_username: str = "admin"
    admin_password: str = "change-me-please"
    # Cle de signature des tokens de session (JWT). A changer en production.
    jwt_secret_key: str = "change-me-please"
    jwt_expire_minutes: int = 1440  # 24h
    # Duree de vie d'une session "se connecter en tant que" (admin -> employe,
    # voir POST /auth/users/{username}/impersonate) : plus courte qu'une
    # session normale, car c'est une session de support ponctuelle.
    impersonation_expire_minutes: int = 30
    # Ancien annuaire JSON (legacy) : conserve uniquement pour la migration
    # unique vers la base de donnees, voir app/auth/migrate_json.py.
    users_file: Path = BASE_DIR / "users.json"

    # ----- Base de donnees (comptes utilisateur multi-organisation) -----
    # SQLite en local par defaut ; en production, pointer vers Postgres via
    # CHURNGUARD_DATABASE_URL (ex: postgresql+psycopg://user:pwd@host/db).
    database_url: str = f"sqlite:///{BASE_DIR / 'churnguard.db'}"

    # ----- Code de verification (OTP) a la connexion -----
    # Envoye par email lorsque l'utilisateur a une adresse renseignee (sinon
    # la connexion reste a une seule etape). Voir app/auth/otp.py.
    otp_length: int = 6
    otp_expire_minutes: int = 10
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60
    # Duree de vie du jeton intermediaire emis apres verification du mot de
    # passe, avant la verification du code (app/auth/tokens.py::creer_token_otp).
    otp_challenge_expire_minutes: int = 10

    # ----- Service d'envoi d'emails -----
    # Le backend est en Python : l'envoi (nodemailer) est delegue a une route
    # interne du frontend Next.js, appelee ici en HTTP avec un secret partage.
    # Doit correspondre a INTERNAL_EMAIL_SECRET cote frontend (voir
    # frontend/.env.local.example).
    email_service_url: str = "http://127.0.0.1:3000/api/internal/send-email"
    email_service_secret: str = "change-me-please"

    # ----- Chemins de travail -----
    data_dir: Path = BASE_DIR / "data"
    models_dir: Path = BASE_DIR / "models"
    knowledge_dir: Path = BASE_DIR / "knowledge"

    # ----- MLflow (suivi des experiences) -----
    mlflow_tracking_uri: str = "file:./mlruns"
    mlflow_experiment_name: str = "churnguard"

    # ----- URL de l'API interne (appelee par la couche MCP) -----
    api_base_url: str = "http://127.0.0.1:8000"

    # ----- LLM du Retention Copilot (API compatible OpenAI : Groq, OpenAI, Ollama, Gemini) -----
    # Vide -> le copilot fonctionne en mode degrade (synthese deterministe, sans LLM).
    # Defaut : Groq + Llama 3.3 70B (gratuit, rapide, bon function-calling).
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"
    llm_base_url: str = "https://api.groq.com/openai/v1"

    # ----- Cache des recommandations IA experte -----
    # Duree (secondes) pendant laquelle les recommandations d'un client sont
    # reutilisees sans rappeler le LLM. 0 desactive le cache.
    recommendation_cache_ttl_seconds: int = 1800

    model_config = SettingsConfigDict(
        env_prefix="CHURNGUARD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instance unique, importable partout : ``from app.config import settings``.
settings = Settings()
