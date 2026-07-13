"""Client LLM agnostique pour le Retention Copilot.

Utilise une API **compatible OpenAI** (``/chat/completions``), ce qui couvre
Groq, OpenAI, Ollama (mode OpenAI) et Gemini (endpoint compatible). Le
fournisseur se change uniquement via ``.env`` (clé, modèle, base_url).

Si aucune clé n'est configurée ou si l'appel échoue, ``completer`` renvoie
``None`` : l'orchestrateur bascule alors en **mode dégradé** (synthèse
déterministe sans LLM). Aucune erreur ne remonte à l'utilisateur.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


def llm_disponible() -> bool:
    """Indique si un LLM est configuré (clé API présente)."""
    return bool(settings.llm_api_key)


def _payload(messages: list[dict[str, str]], temperature: float) -> dict[str, Any]:
    """Construit le corps de requete ; effort de raisonnement minimal pour gpt-oss."""
    corps: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
    }
    if "gpt-oss" in settings.llm_model:
        corps["reasoning_effort"] = "low"
    return corps


def completer(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    timeout: float = 60.0,
) -> str | None:
    """Appelle le LLM et renvoie le texte de la réponse, ou ``None`` si indisponible.

    Args:
        messages: Liste de messages au format OpenAI ({"role", "content"}).
        temperature: Créativité (faible = plus factuel).
        timeout: Délai max en secondes.
    """
    if not settings.llm_api_key:
        return None
    try:
        with httpx.Client() as client:
            reponse = client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=_payload(messages, temperature),
                timeout=timeout,
            )
        reponse.raise_for_status()
        data: dict[str, Any] = reponse.json()
        texte = data["choices"][0]["message"]["content"].strip()
        return texte or None
    except Exception:  # noqa: BLE001 — toute erreur LLM -> mode dégradé
        return None
