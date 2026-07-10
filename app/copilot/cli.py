"""Interface en ligne de commande du Retention Copilot.

Usage :
    # 1) client passé en argument JSON
    python -m app.copilot.cli '{"CreditScore":546,"Geography":"Germany",...}'

    # 2) client lu depuis un fichier
    python -m app.copilot.cli --fichier client.json

Prérequis : l'API FastAPI doit tourner (le copilot appelle ses endpoints).
"""

from __future__ import annotations

import json
import sys
from typing import Any

from app.copilot.agent import traiter_client


def _lire_client(args: list[str]) -> dict[str, Any]:
    """Récupère le client depuis un fichier (--fichier) ou un argument JSON."""
    if len(args) >= 2 and args[0] == "--fichier":
        with open(args[1], encoding="utf-8") as f:
            return json.load(f)
    if args:
        return json.loads(args[0])
    # Sinon : lecture sur l'entrée standard.
    return json.load(sys.stdin)


def main() -> None:
    """Point d'entrée CLI."""
    try:
        client = _lire_client(sys.argv[1:])
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Entrée invalide : {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    resultat = traiter_client(client)

    if not resultat.get("ok", False):
        print(f"Échec : {resultat.get('erreur', 'erreur inconnue')}", file=sys.stderr)
        raise SystemExit(1)

    # Affichage lisible : la synthèse d'abord, puis le détail JSON.
    print("=" * 60)
    print(f"RISQUE : {resultat['risk_score']}% ({resultat['risk_level']})")
    print(f"DÉCISION : {resultat['decision']}")
    print("=" * 60)
    print("\nSYNTHÈSE :\n")
    print(resultat["synthese"])
    print("\n" + "-" * 60)
    print("Détail complet (JSON) :")
    print(json.dumps(resultat, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
