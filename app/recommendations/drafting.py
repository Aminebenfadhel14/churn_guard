"""Moteur local de redaction pour les recommandations de retention.

Ce module ne depend d'aucune API externe. Il prend les actions issues de
l'IA experte (ou du message de secours) et les transforme en deux livrables
lisibles :

- un plan de retention personnalise pour l'equipe retention ;
- un brouillon d'email d'alerte naturel, pret a copier ou ouvrir en mailto.

Ce module reste volontairement deterministe : la redaction vient de templates
adaptes au score, aux actions fournies et au profil client.
"""

from __future__ import annotations

from typing import Any


EMPTY_VALUES = {"", "none", "null", "nan", "nat"}

IDENTITY_KEYS = (
    "CustomerId",
    "customerID",
    "ClientId",
    "client_id",
    "id",
    "Surname",
    "name",
    "Name",
    "Email",
    "email",
)

IMPORTANT_KEYS = (
    "Age",
    "Tenure",
    "Balance",
    "NumOfProducts",
    "IsActiveMember",
    "CreditScore",
    "OverTime",
    "JobSatisfaction",
    "WorkLifeBalance",
    "YearsSinceLastPromotion",
    "MonthlyCharges",
    "TotalCharges",
    "Contract",
    "tenure",
    "MonthlyCharge",
    "Satisfaction",
)


def _valeur_affichable(valeur: Any) -> str:
    """Convertit une valeur client en texte court et lisible."""
    if valeur is None:
        return ""
    if isinstance(valeur, float):
        return f"{valeur:.2f}".rstrip("0").rstrip(".")
    return str(valeur)


def _est_renseignee(valeur: Any) -> bool:
    texte = _valeur_affichable(valeur).strip().lower()
    return texte not in EMPTY_VALUES


def _format_score(risk_score: float) -> str:
    return f"{risk_score:.0f}%"


def niveau_risque(risk_score: float) -> str:
    """Retourne le niveau de risque utilise par l'API et le frontend."""
    if risk_score > 70:
        return "eleve"
    if risk_score >= 30:
        return "moyen"
    return "faible"


def _libelle_niveau(niveau: str) -> str:
    """Libellé affichable (avec accents) pour un niveau de risque interne."""
    return {
        "eleve": "élevé",
        "moyen": "moyen",
        "faible": "faible",
    }.get(niveau, niveau)


def _identifier_client(client: dict[str, Any]) -> str:
    for cle in IDENTITY_KEYS:
        valeur = client.get(cle)
        if _est_renseignee(valeur):
            return f"{cle} {_valeur_affichable(valeur)}"
    return "ce client"


def _signaux_client(client: dict[str, Any], limite: int = 6) -> list[str]:
    """Selectionne quelques caracteristiques utiles sans supposer un schema fixe."""
    signaux: list[str] = []
    deja_vus: set[str] = set()

    for cle in IMPORTANT_KEYS:
        if cle in client and _est_renseignee(client[cle]):
            signaux.append(f"{cle}: {_valeur_affichable(client[cle])}")
            deja_vus.add(cle)
        if len(signaux) >= limite:
            return signaux

    for cle, valeur in client.items():
        if cle in deja_vus or not _est_renseignee(valeur):
            continue
        signaux.append(f"{cle}: {_valeur_affichable(valeur)}")
        if len(signaux) >= limite:
            break

    return signaux


def _actions_prioritaires(
    actions: list[dict[str, Any]],
    limite: int = 4,
) -> list[dict[str, Any]]:
    return [a for a in actions if a.get("action")][:limite]


def _phrase_cadence(niveau: str) -> str:
    if niveau == "eleve":
        return "Déclencher une prise de contact sous 24 à 48 heures, puis vérifier l'évolution du risque sous une semaine."
    if niveau == "moyen":
        return "Planifier une action proactive cette semaine et suivre l'évolution au prochain point client."
    return "Maintenir une surveillance régulière et réactiver le plan si de nouveaux signaux faibles apparaissent."


_ORIGINE_ACTIONS = {
    "rag": "générées par l'IA à partir de tes playbooks de rétention et des facteurs de risque propres à ce client",
    "regles_secours": "issues du moteur de règles de secours (IA momentanément indisponible)",
    # Anciens libellés conservés pour compatibilité.
    "ia_experte": "générées par l'analyse experte IA à partir des facteurs de risque propres à ce client",
    "degrade": "issues du message de secours (analyse experte IA momentanément indisponible)",
}


def generer_plan_retention(
    client: dict[str, Any],
    risk_score: float,
    actions: list[dict[str, Any]],
    risk_level: str | None = None,
    source_recommandations: str = "ia_experte",
) -> dict[str, Any]:
    """Construit un plan de retention a partir des actions recommandees.

    Args:
        source_recommandations: origine des ``actions`` ("ia_experte" ou
            "degrade"), utilisee uniquement pour la phrase de resume.
    """
    niveau = risk_level or niveau_risque(risk_score)
    score = _format_score(risk_score)
    identite = _identifier_client(client)
    top_actions = _actions_prioritaires(actions)
    signaux = _signaux_client(client)
    origine = _ORIGINE_ACTIONS.get(source_recommandations, _ORIGINE_ACTIONS["rag"])

    resume = (
        f"{identite} présente un risque de churn {_libelle_niveau(niveau)} "
        f"({score}). Le plan ci-dessous priorise les actions {origine} "
        "et les transforme en séquence opérationnelle."
    )

    etapes: list[str] = []
    for index, action in enumerate(top_actions, start=1):
        nom = str(action.get("action", "")).strip()
        detail = str(action.get("detail", "")).strip()
        priorite = str(action.get("priority", "Basse")).strip()
        impact = action.get("impact", 0)

        texte = f"{index}. {nom}"
        if detail:
            texte += f" - {detail}"
        texte += f" Priorité : {priorite}."
        if impact:
            texte += f" Impact estimé : -{impact} points de risque."
        etapes.append(texte)

    if not etapes:
        etapes.append(
            "1. Maintenir un suivi standard et vérifier l'apparition de nouveaux signaux faibles."
        )

    etapes.append(f"{len(etapes) + 1}. {_phrase_cadence(niveau)}")

    message = "\n".join(
        [
            resume,
            "",
            "Signaux utiles:",
            *(f"- {signal}" for signal in signaux),
            "",
            "Plan d'action:",
            *etapes,
        ]
    )

    return {
        "source": "redaction_locale",
        "resume": resume,
        "signaux": signaux,
        "etapes": etapes,
        "message": message,
    }


def rediger_email_alerte(
    client: dict[str, Any],
    risk_score: float,
    actions: list[dict[str, Any]],
    risk_level: str | None = None,
    modele: str | None = None,
) -> dict[str, str]:
    """Redige un brouillon d'email d'alerte base sur les regles."""
    niveau = risk_level or niveau_risque(risk_score)
    score = _format_score(risk_score)
    identite = _identifier_client(client)
    plan = generer_plan_retention(client, risk_score, actions, niveau)
    top_actions = _actions_prioritaires(actions, limite=3)

    sujet = f"Alerte rétention - risque {_libelle_niveau(niveau)} ({score})"

    actions_txt = "\n".join(
        f"{index}. {action.get('action', '')}"
        + (f" - {action.get('detail', '')}" if action.get("detail") else "")
        for index, action in enumerate(top_actions, start=1)
    )
    if not actions_txt:
        actions_txt = "1. Maintenir un suivi standard et réévaluer le client au prochain point."

    signaux_txt = "\n".join(f"- {signal}" for signal in plan["signaux"])
    if not signaux_txt:
        signaux_txt = "- Aucun signal client exploitable n'a été fourni."

    modele_txt = f"\nModèle utilisé : {modele}" if modele else ""

    corps = f"""Bonjour,

ChurnGuard signale un client avec un risque de churn {_libelle_niveau(niveau)} de {score}.
Client concerné : {identite}{modele_txt}

Signaux utiles :
{signaux_txt}

Plan de rétention recommandé :
{actions_txt}

Prochaine étape :
{_phrase_cadence(niveau)}

Merci de prioriser ce suivi et de noter le retour client après contact.

-- ChurnGuard"""

    return {
        "source": "redaction_locale",
        "subject": sujet,
        "body": corps,
    }
