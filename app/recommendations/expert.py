"""Expert LLM de recommandations de retention (Couche 4 — Recommendations).

Seule source de recommandations de ChurnGuard : un LLM (Groq) joue le role
d'un expert relation client / customer success senior. Il recoit les
facteurs de risque (SHAP) exprimes avec les VRAIES colonnes du dataset
charge et redige des actions de retention concretes, specifiques a ce
client et au metier deduit du schema (banque, telecom, RH, SaaS...) —
jamais des indications statistiques du type "augmenter X, diminuer Y".

Repli : si aucun LLM n'est configure ou si l'appel/parsing echoue,
``generer_recommandations_expertes`` renvoie ``None`` et l'appelant utilise
``recommandations_de_secours`` (message de secours minimal, base uniquement
sur le score de risque, sans regle metier).
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.copilot.llm import completer, llm_disponible

PRIORITES_VALIDES = {"Haute", "Moyenne", "Basse"}

SYSTEME_EXPERT = """Tu es un expert relation client / customer success senior, specialise dans la retention client. Tu interviens sur des datasets de secteurs varies (banque, telecom, RH, SaaS, retail...) sans connaitre le domaine a l'avance : tu le deduis des noms de colonnes et de leurs valeurs.

On te fournit, pour UN client precis :
- son score et niveau de risque de churn,
- les facteurs qui expliquent le plus ce risque (analyse SHAP), avec le nom REEL de la colonne du dataset, sa valeur pour ce client, et si elle augmente ou diminue le risque.

Ta mission : proposer des actions de retention CONCRETES et SPECIFIQUES a ce client et a ce type d'activite (deduit des colonnes), comme le ferait un vrai charge de compte : appel cible, geste commercial, ajustement contractuel, accompagnement personnalise, offre adaptee...

CALIBRE le NOMBRE d'actions selon le niveau de risque, sans surreagir :
- risque FAIBLE : le client est fidele. Propose UNE seule action legere (simple surveillance ou petit geste de fidelisation), et indique dans son detail qu'aucune action prioritaire n'est necessaire. N'invente pas de plan d'urgence.
- risque MOYEN : 2 a 3 actions ciblees de prevention.
- risque ELEVE : 3 a 5 actions, plan complet et prioritaire.

Interdits :
- Pas de conseil statistique generique du type "augmenter X" ou "diminuer Y".
- Pas de blabla ni de recommandation qui ne s'appuie pas sur les facteurs fournis.

Reponds UNIQUEMENT avec un tableau JSON (pas de texte autour, pas de bloc markdown), au format :
[
  {"action": "Titre court de l'action", "detail": "Explication concrete de l'action et pourquoi, en 1-2 phrases", "priority": "Haute|Moyenne|Basse", "impact": 0-20}
]
"""


def _formater_facteurs(features: list[dict[str, Any]]) -> str:
    lignes = []
    for f in features:
        try:
            contribution = float(f.get("contribution", 0) or 0)
        except (TypeError, ValueError):
            contribution = 0.0
        sens = "augmente" if contribution > 0 else "diminue"
        lignes.append(
            f"- {f.get('label', f.get('feature'))} = {f.get('value')} "
            f"({sens} le risque, contribution {f.get('contribution')} pts)"
        )
    return "\n".join(lignes) if lignes else "- Aucun facteur SHAP disponible."


def _extraire_json(texte: str) -> Any:
    """Extrait un tableau JSON d'une reponse LLM (tolere les blocs ```json)."""
    texte = texte.strip()
    if texte.startswith("```"):
        texte = re.sub(r"^```(?:json)?", "", texte).strip()
        texte = re.sub(r"```$", "", texte).strip()
    return json.loads(texte)


def _valider_recommandations(brut: Any) -> list[dict[str, Any]] | None:
    if not isinstance(brut, list) or not brut:
        return None

    recos: list[dict[str, Any]] = []
    for index, item in enumerate(brut):
        if not isinstance(item, dict) or not item.get("action"):
            continue
        priorite = str(item.get("priority", "Moyenne")).strip().capitalize()
        if priorite not in PRIORITES_VALIDES:
            priorite = "Moyenne"
        try:
            impact = max(0, min(20, int(float(item.get("impact", 5)))))
        except (TypeError, ValueError):
            impact = 5
        recos.append({
            "id": f"r_ia_expert_{index}",
            "action": str(item["action"]).strip(),
            "detail": str(item.get("detail", "")).strip(),
            "priority": priorite,
            "impact": impact,
        })

    return recos or None


def generer_recommandations_expertes(
    risk_score: float,
    risk_level: str,
    features: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """Genere des recommandations sur mesure via LLM a partir des facteurs SHAP.

    Args:
        risk_score: Score de risque estime (0-100).
        risk_level: Niveau de risque ("eleve", "moyen", "faible").
        features: Facteurs SHAP renvoyes par ``expliquer_prediction`` (triés
            par importance), avec les noms de colonnes reels du dataset.

    Returns:
        Une liste de recommandations au format
        ``[{"id", "action", "detail", "priority", "impact"}]``,
        ou ``None`` si aucun LLM n'est configure ou si l'appel/parsing echoue.
    """
    if not llm_disponible():
        return None

    contexte = (
        f"Score de risque : {risk_score:.0f}/100 (niveau {risk_level}).\n\n"
        "Facteurs de risque (SHAP), du plus important au moins important :\n"
        f"{_formater_facteurs(features)}"
    )

    # RAG : injecte les playbooks de retention pertinents pour ancrer les actions
    # sur des bonnes pratiques ecrites. Sans corpus, ne change rien.
    try:
        from app.copilot import rag

        requete = f"{risk_level} " + " ".join(
            str(f.get("label", f.get("feature", ""))) + " " + str(f.get("value", ""))
            for f in features
        )
        playbooks = rag.contexte_pour_prompt(requete, k=3)
        if playbooks:
            contexte += (
                "\n\nPlaybooks de retention pertinents (appuie tes actions dessus quand "
                "c'est adapte, et cite la source .md entre parentheses dans le detail) :\n"
                + playbooks
            )
    except Exception:  # noqa: BLE001 — le RAG ne doit jamais casser la generation
        pass

    messages = [
        {"role": "system", "content": SYSTEME_EXPERT},
        {"role": "user", "content": contexte},
    ]

    texte = completer(messages, temperature=0.4)
    if not texte:
        return None

    try:
        brut = _extraire_json(texte)
    except (json.JSONDecodeError, TypeError):
        return None

    return _valider_recommandations(brut)


def recommandations_de_secours(risk_score: float, risk_level: str) -> list[dict[str, Any]]:
    """Filet de securite minimal quand l'IA experte est indisponible.

    N'implemente aucune regle metier : une seule action generique par
    niveau de risque, utilisee uniquement le temps que le LLM (ou sa
    configuration) redevienne disponible.
    """
    if risk_level == "eleve" or risk_score > 70:
        return [{
            "id": "r_secours_eleve",
            "action": "Contacter le client en priorite",
            "detail": (
                "Risque de churn eleve. L'analyse experte IA est momentanement "
                "indisponible : planifier un appel de retention et qualifier le "
                "motif de risque manuellement en attendant."
            ),
            "priority": "Haute",
            "impact": 10,
        }]
    if risk_level == "moyen" or risk_score >= 30:
        return [{
            "id": "r_secours_moyen",
            "action": "Lancer un suivi preventif",
            "detail": (
                "Risque de churn moyen. L'analyse experte IA est momentanement "
                "indisponible : verifier les derniers signaux client avant que "
                "le risque augmente."
            ),
            "priority": "Moyenne",
            "impact": 5,
        }]
    return [{
        "id": "r_secours_faible",
        "action": "Maintenir le suivi standard",
        "detail": "Risque de churn faible. Effectuer une surveillance standard periodique.",
        "priority": "Basse",
        "impact": 0,
    }]
