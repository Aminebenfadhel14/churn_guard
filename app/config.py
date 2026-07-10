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

    # ----- Chemins de travail -----
    data_dir: Path = BASE_DIR / "data"
    models_dir: Path = BASE_DIR / "models"

    # ----- MLflow (suivi des experiences) -----
    mlflow_tracking_uri: str = "file:./mlruns"
    mlflow_experiment_name: str = "churnguard"

    # ----- URL de l'API interne (appelee par la couche MCP) -----
    api_base_url: str = "http://127.0.0.1:8000"

    # ----- LLM du Retention Copilot (API compatible OpenAI : Groq, OpenAI, Ollama, Gemini) -----
    # Vide -> le copilot fonctionne en mode degrade (synthese deterministe, sans LLM).
    # Defaut : Groq + Llama 3.3 70B (gratuit, rapide, bon function-calling).
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
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
