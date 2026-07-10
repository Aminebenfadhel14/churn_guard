"""Orchestrateur du Retention Copilot (V1).

Squelette **déterministe** qui enchaîne les outils ChurnGuard de façon fiable
(predict -> explain -> recommend), puis rédige une **synthèse** en langage
naturel via le LLM (repli déterministe si aucun LLM n'est configuré).

Aucun envoi d'email : le copilot prépare le plan et le brouillon, l'humain valide.
"""

from __future__ import annotations

import json
from typing import Any

from app.copilot import tools
from app.copilot.llm import completer, llm_disponible
from app.copilot.prompts import SYSTEME_SYNTHESE


def traiter_client(client: dict[str, Any]) -> dict[str, Any]:
    """Traite un client de bout en bout et renvoie une synthèse d'aide à la décision.

    Args:
        client: Caractéristiques du client (mêmes champs que /predict).

    Returns:
        Un dictionnaire structuré : risque, facteurs, actions, plan, email,
        décision d'escalade et synthèse rédigée.
    """
    # 1) Prédiction — étape obligatoire. Si elle échoue, on renvoie une erreur claire.
    try:
        prediction = tools.predire(client)
    except tools.OutilChurnGuardError as exc:
        return {"ok": False, "erreur": str(exc)}

    risk_score = float(prediction.get("risk_score", 0.0))
    niveau = str(prediction.get("risk_level", "inconnu"))
    modele = prediction.get("modele")

    # 2) Explication SHAP — best-effort (on continue même si ça échoue).
    try:
        explication = tools.expliquer(client, top_k=6)
    except tools.OutilChurnGuardError:
        explication = {}

    # 3) Recommandations + plan + brouillon d'email — best-effort.
    try:
        reco = tools.recommander(client)
    except tools.OutilChurnGuardError:
        reco = {}

    actions = reco.get("recommendations", [])
    plan = reco.get("plan_retention", {})
    email = reco.get("email_alert", {})

    # 4) Décision d'escalade (règle simple : risque élevé -> priorité).
    escalade = niveau == "eleve"
    decision = (
        "À traiter en priorité (risque élevé)."
        if escalade
        else "Suivi standard — pas d'action urgente."
    )

    # 5) Synthèse : LLM si configuré, sinon version déterministe.
    synthese = _rediger_synthese(prediction, explication, reco, decision)

    return {
        "ok": True,
        "risk_score": risk_score,
        "risk_level": niveau,
        "modele": modele,
        "facteurs": explication.get("features", []),
        "recommendations": actions,
        "plan_retention": plan,
        "email_alerte": email,
        "escalade": escalade,
        "decision": decision,
        "synthese": synthese,
        "source_synthese": "llm" if llm_disponible() else "deterministe",
    }


def _rediger_synthese(
    prediction: dict[str, Any],
    explication: dict[str, Any],
    reco: dict[str, Any],
    decision: str,
) -> str:
    """Rédige la synthèse via le LLM ; repli déterministe si indisponible."""
    contexte = {
        "prediction": prediction,
        "facteurs": explication.get("features", []),
        "recommandations": reco.get("recommendations", []),
        "plan": reco.get("plan_retention", {}),
        "decision": decision,
    }
    messages = [
        {"role": "system", "content": SYSTEME_SYNTHESE},
        {
            "role": "user",
            "content": "Données du client (JSON) :\n"
            + json.dumps(contexte, ensure_ascii=False, indent=2),
        },
    ]
    texte = completer(messages)
    if texte:
        return texte
    return _synthese_deterministe(prediction, explication, reco, decision)


def _synthese_deterministe(
    prediction: dict[str, Any],
    explication: dict[str, Any],
    reco: dict[str, Any],
    decision: str,
) -> str:
    """Synthèse de repli (sans LLM), construite à partir des données brutes."""
    score = prediction.get("risk_score")
    niveau = prediction.get("risk_level")
    lignes = [f"Risque de churn {niveau} ({score}%)."]

    facteurs = explication.get("features", [])
    if facteurs:
        noms = [str(f.get("label") or f.get("feature")) for f in facteurs[:3]]
        lignes.append("Principaux facteurs : " + ", ".join(noms) + ".")

    actions = reco.get("recommendations", [])
    if actions:
        top = " ; ".join(str(a.get("action", "")) for a in actions[:3] if a.get("action"))
        if top:
            lignes.append("Actions recommandées : " + top + ".")

    lignes.append("Décision : " + decision)
    return " ".join(lignes)
