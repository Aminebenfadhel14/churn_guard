"""Serveur MCP ChurnGuard.

Expose ChurnGuard a Claude Desktop via des outils en langage naturel. Les outils
appellent l'API FastAPI locale configuree par ``CHURNGUARD_API_BASE_URL``.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastmcp import FastMCP

from app.config import settings


mcp = FastMCP("ChurnGuard")


def _get_headers() -> dict[str, str]:
    """Construit les en-tetes HTTP pour appeler l'API ChurnGuard."""
    headers = {"Content-Type": "application/json"}
    if settings.api_key and settings.api_key != "change-me-please":
        headers["x-api-key"] = settings.api_key
    return headers


def _handle_request_error(e: Exception) -> str:
    """Formate les erreurs de connexion a l'API pour Claude Desktop."""
    return (
        f"Impossible de se connecter a l'API ChurnGuard sur {settings.api_base_url}.\n"
        "Verifie que le backend FastAPI est demarre avec :\n"
        "  .\\venv\\Scripts\\python.exe -m uvicorn app.main:app --reload\n\n"
        f"Detail de l'erreur : {e}"
    )


@mcp.tool()
def predict_churn(client: dict[str, Any]) -> str:
    """Predit le risque de churn d'un client a partir de ses caracteristiques."""
    url = f"{settings.api_base_url}/predict"
    try:
        with httpx.Client() as http_client:
            res = http_client.post(url, json=client, headers=_get_headers(), timeout=15.0)

        if res.status_code == 200:
            data = res.json()
            prediction = "Depart probable (churn)" if data["prediction"] == 1 else "Fidele (non-churn)"
            return (
                "### Prediction de churn\n"
                f"- **Score de risque** : {data['risk_score']}%\n"
                f"- **Niveau de risque** : {data['risk_level'].upper()}\n"
                f"- **Prediction finale** : {prediction}\n"
                f"- **Modele actif** : {data['modele']}"
            )
        return f"Erreur de l'API (Code {res.status_code}) : {res.text}"
    except httpx.RequestError as exc:
        return _handle_request_error(exc)


@mcp.tool()
def explain_prediction(client: dict[str, Any], top_k: int = 5) -> str:
    """Explique une prediction de churn avec SHAP ou le fallback d'ablation."""
    url = f"{settings.api_base_url}/explain"
    payload = dict(client)
    payload["top_k"] = top_k
    try:
        with httpx.Client() as http_client:
            res = http_client.post(url, json=payload, headers=_get_headers(), timeout=20.0)

        if res.status_code == 200:
            data = res.json()
            lines = [
                f"### Explication de la prediction ({data['method'].upper()})",
                f"- **Score de risque global** : {data['risk_score']}% ({data['risk_level']})",
                "",
                "**Principaux facteurs influents :**",
            ]
            for i, feature in enumerate(data.get("features", []), 1):
                signe = "+" if feature["contribution"] > 0 else ""
                lines.append(
                    f"{i}. {signe}{feature['contribution']} pts : "
                    f"**{feature['label']}** ({feature['feature']}) - {feature['description']}"
                )
            return "\n".join(lines)
        return f"Erreur de l'API (Code {res.status_code}) : {res.text}"
    except httpx.RequestError as exc:
        return _handle_request_error(exc)


@mcp.tool()
def recommend_actions(client: dict[str, Any]) -> str:
    """Suggere un plan de retention priorise pour un client a risque.

    Utilise l'endpoint enrichi : actions generees par l'IA experte (Groq) a
    partir des facteurs de risque du client, plan local de retention et
    brouillon email naturel.
    """
    url = f"{settings.api_base_url}/recommend/enriched"
    try:
        with httpx.Client() as http_client:
            res = http_client.post(url, json=client, headers=_get_headers(), timeout=15.0)

        if res.status_code == 200:
            data = res.json()
            plan = data.get("plan_retention") or {}
            email = data.get("email_alert") or {}
            lines = [
                "### Plan de retention recommande",
                f"- **Score actuel** : {data['risk_score']}% ({data['risk_level']})",
                "",
            ]

            if plan.get("resume"):
                lines.extend(["**Resume du plan :**", str(plan["resume"]), ""])

            if plan.get("signaux"):
                lines.append("**Signaux utiles :**")
                for signal in plan.get("signaux", [])[:5]:
                    lines.append(f"- {signal}")
                lines.append("")

            lines.append("**Actions prioritaires :**")
            for reco in data.get("recommendations", []):
                lines.append(
                    f"- **[{reco['priority'].upper()}] {reco['action']}** "
                    f"(impact estime : -{reco['impact']} pts)\n"
                    f"  {reco['detail']}"
                )

            if email.get("subject") and email.get("body"):
                lines.extend([
                    "",
                    "**Brouillon email :**",
                    f"Objet : {email['subject']}",
                    "",
                    str(email["body"]),
                ])

            return "\n".join(lines)

        return f"Erreur de l'API (Code {res.status_code}) : {res.text}"
    except httpx.RequestError as exc:
        return _handle_request_error(exc)


@mcp.tool()
def simulate_what_if(client: dict[str, Any], overrides: dict[str, Any]) -> str:
    """Simule l'impact de modifications client sur le score de risque."""
    url = f"{settings.api_base_url}/what-if"
    payload = {"client": client, "overrides": overrides}
    try:
        with httpx.Client() as http_client:
            res = http_client.post(url, json=payload, headers=_get_headers(), timeout=15.0)

        if res.status_code == 200:
            data = res.json()
            orig = data["original"]
            sim = data["simulated"]
            delta = data["delta"]
            delta_str = f"+{delta} pts (risque accru)" if delta > 0 else f"{delta} pts (risque reduit)"
            if delta == 0:
                delta_str = "Aucun changement (0.0 pts)"

            return (
                "### Simulation What-If\n"
                f"- **Score original** : {orig['risk_score']}% ({orig['risk_level']})\n"
                f"- **Score apres modifications** : {sim['risk_score']}% ({sim['risk_level']})\n"
                f"- **Delta** : {delta_str}\n\n"
                f"**Variables modifiees** : {overrides}"
            )
        return f"Erreur de l'API (Code {res.status_code}) : {res.text}"
    except httpx.RequestError as exc:
        return _handle_request_error(exc)


@mcp.tool()
def list_high_risk_clients(limit: int = 10) -> str:
    """Liste les clients ayant les scores de churn les plus eleves."""
    url = f"{settings.api_base_url}/clients/high-risk?limit={limit}"
    try:
        with httpx.Client() as http_client:
            res = http_client.get(url, headers=_get_headers(), timeout=25.0)

        if res.status_code == 200:
            data = res.json()
            lines = [
                f"### Top {data['limit']} clients a haut risque (source : {data['dataset']})",
                f"Total clients analyses : {data['total_clients']}",
                "",
                "| ID | Nom/identifiant | Score de risque | Statut |",
                "|---|---|---|---|",
            ]
            for client_item in data.get("clients", []):
                statut = "Eleve" if client_item["risk_score"] > 70 else "Moyen"
                lines.append(
                    f"| `{client_item['id']}` | {client_item['name']} | "
                    f"{client_item['risk_score']}% | {statut} |"
                )
            return "\n".join(lines)
        return f"Erreur de l'API (Code {res.status_code}) : {res.text}"
    except httpx.RequestError as exc:
        return _handle_request_error(exc)


@mcp.tool()
def get_dashboard_summary() -> str:
    """Retourne un resume global du dashboard ChurnGuard."""
    url = f"{settings.api_base_url}/dashboard"
    try:
        with httpx.Client() as http_client:
            res = http_client.get(url, headers=_get_headers(), timeout=25.0)

        if res.status_code == 200:
            data = res.json()
            stats = data.get("stats", {})
            lines = [
                "### Resume dashboard ChurnGuard",
                f"- Dataset : {data.get('dataset')}",
                f"- Total clients : {stats.get('total')}",
                f"- Clients a risque eleve : {stats.get('at_risk_count')} ({stats.get('at_risk_pct')}%)",
                f"- Score moyen : {stats.get('avg_score')}%",
                f"- Taux de churn moyen estime : {stats.get('avg_churn_rate')}%",
                "",
                "**Repartition du risque :**",
            ]
            for bucket in data.get("distribution", []):
                lines.append(f"- {bucket.get('level')} : {bucket.get('count')}")

            top_clients = data.get("top_clients", [])
            if top_clients:
                lines.extend(["", "**Top clients a risque :**"])
                for client_item in top_clients[:5]:
                    lines.append(f"- `{client_item.get('id')}` : {client_item.get('risk_score')}%")

            return "\n".join(lines)
        return f"Erreur de l'API (Code {res.status_code}) : {res.text}"
    except httpx.RequestError as exc:
        return _handle_request_error(exc)


if __name__ == "__main__":
    mcp.run()
