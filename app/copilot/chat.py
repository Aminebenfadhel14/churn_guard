"""Assistant conversationnel du Retention Copilot (V2).

Boucle de *tool-calling* : le LLM (Groq / compatible OpenAI) reçoit la demande en
langage naturel + la liste des outils ChurnGuard, **décide** lesquels appeler,
on les exécute, et on lui renvoie les résultats jusqu'à ce qu'il produise une
réponse finale.

Le client courant (rempli dans le formulaire) est injecté en contexte : l'agent
peut donc raisonner dessus (« traite ce client », « et si on le réactive ? »).
Le what-if autonome émerge naturellement : l'agent lit les facteurs de risque
puis appelle ``simuler_what_if`` avec les changements qu'il juge pertinents.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings
from app.copilot import tools

# Schémas des outils au format OpenAI (function-calling).
DEFINITIONS_OUTILS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "predire",
            "description": "Prédit le score de churn (0 à 100) d'un client.",
            "parameters": {
                "type": "object",
                "properties": {"client": {"type": "object", "description": "Caractéristiques du client."}},
                "required": ["client"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "expliquer",
            "description": "Donne les facteurs (SHAP) qui expliquent le risque d'un client.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client": {"type": "object"},
                    "top_k": {"type": "integer", "description": "Nombre de facteurs (défaut 6)."},
                },
                "required": ["client"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommander",
            "description": "Actions de rétention + plan + brouillon d'email pour un client.",
            "parameters": {
                "type": "object",
                "properties": {"client": {"type": "object"}},
                "required": ["client"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simuler_what_if",
            "description": (
                "Simule le score après modification de certaines variables. "
                "Sert à trouver la meilleure action : change les variables qui "
                "augmentent le risque et compare le score avant/après."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client": {"type": "object"},
                    "overrides": {"type": "object", "description": "Variables à changer et leurs nouvelles valeurs."},
                },
                "required": ["client", "overrides"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clients_a_risque",
            "description": "Liste les N clients les plus à risque de churn.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Nombre de clients (défaut 10)."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resume_dashboard",
            "description": "Résumé global du tableau de bord (KPI, répartition, top clients).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

SYSTEME = """Tu es le Retention Copilot de ChurnGuard, un assistant de rétention client.
Tu réponds en français, de façon claire et concise, sans jargon inutile.

Tu disposes d'outils que tu peux appeler pour agir sur la plateforme :
- predire(client) : score de churn d'un client.
- expliquer(client) : facteurs qui expliquent le risque.
- recommander(client) : actions de rétention + plan + email prêt.
- simuler_what_if(client, overrides) : score après changement de variables.
- clients_a_risque(limit) : clients les plus à risque.
- resume_dashboard() : synthèse du tableau de bord.

Règles de raisonnement :
- Choisis TOI-MÊME les outils utiles à la demande, dans l'ordre pertinent.
- Pour trouver la MEILLEURE action de rétention : appelle d'abord expliquer pour
  voir les variables qui augmentent le risque, puis appelle simuler_what_if en
  changeant une ou deux de ces variables vers une meilleure valeur, et compare
  la baisse de risque. Recommande l'action la plus efficace.
- N'invente jamais de chiffres : appuie-toi uniquement sur les résultats des outils.
- Tu ne fais qu'AIDER et PRÉPARER : tu n'envoies aucun email, un humain valide.
- Quand tu as assez d'informations, donne une réponse finale utile et actionnable.
"""


def _executer_outil(nom: str, args: dict[str, Any]) -> Any:
    """Exécute un outil ChurnGuard ; renvoie un dict d'erreur en cas d'échec."""
    try:
        if nom == "predire":
            return tools.predire(args["client"])
        if nom == "expliquer":
            return tools.expliquer(args["client"], int(args.get("top_k", 6)))
        if nom == "recommander":
            return tools.recommander(args["client"])
        if nom == "simuler_what_if":
            return tools.simuler_what_if(args["client"], args.get("overrides", {}))
        if nom == "clients_a_risque":
            return tools.clients_a_risque(int(args.get("limit", 10)))
        if nom == "resume_dashboard":
            return tools.resume_dashboard()
        return {"erreur": f"Outil inconnu : {nom}"}
    except tools.OutilChurnGuardError as exc:
        return {"erreur": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"erreur": f"Erreur outil {nom} : {exc}"}


def _appel_llm(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Un tour d'appel au LLM avec les outils déclarés."""
    with httpx.Client() as client:
        reponse = client.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "messages": messages,
                "tools": DEFINITIONS_OUTILS,
                "tool_choice": "auto",
                "temperature": 0.3,
            },
            timeout=90.0,
        )
    reponse.raise_for_status()
    return reponse.json()


def discuter(
    messages_utilisateur: list[dict[str, str]],
    client: dict[str, Any] | None = None,
    max_tours: int = 6,
) -> dict[str, Any]:
    """Fait tourner la boucle de raisonnement et renvoie la réponse de l'assistant.

    Args:
        messages_utilisateur: Historique de conversation ([{role, content}]).
        client: Client courant (injecté en contexte pour les outils).
        max_tours: Nombre max d'aller-retours avec le LLM.

    Returns:
        ``{"reply": str, "outils": list[str]}``.
    """
    if not settings.llm_api_key:
        return {
            "reply": "L'assistant IA n'est pas configuré (clé LLM manquante dans .env). "
            "Tu peux utiliser le mode Formulaire en attendant.",
            "outils": [],
        }

    contexte = SYSTEME
    if client:
        contexte += (
            "\n\nClient courant (utilise-le pour les outils qui demandent un client) :\n"
            + json.dumps(client, ensure_ascii=False)
        )

    messages: list[dict[str, Any]] = [{"role": "system", "content": contexte}]
    messages.extend(messages_utilisateur)
    outils_utilises: list[str] = []

    try:
        for _ in range(max_tours):
            data = _appel_llm(messages)
            message = data["choices"][0]["message"]
            tool_calls = message.get("tool_calls")

            if not tool_calls:
                texte = (message.get("content") or "").strip()
                return {"reply": texte or "(réponse vide)", "outils": outils_utilises}

            # Le modèle demande des outils : on les exécute et on renvoie les résultats.
            messages.append(message)
            for appel in tool_calls:
                nom = appel["function"]["name"]
                try:
                    args = json.loads(appel["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                resultat = _executer_outil(nom, args)
                outils_utilises.append(nom)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": appel["id"],
                        "name": nom,
                        "content": json.dumps(resultat, ensure_ascii=False),
                    }
                )

        return {
            "reply": "La demande a nécessité trop d'étapes. Peux-tu la reformuler plus simplement ?",
            "outils": outils_utilises,
        }
    except Exception as exc:  # noqa: BLE001
        return {"reply": f"Erreur de l'assistant : {exc}", "outils": outils_utilises}
