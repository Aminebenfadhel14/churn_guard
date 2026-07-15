"""CLI d'administration des comptes utilisateur (Couche Authentification).

Usage :
    python -m app.auth.cli create <username> <mot_de_passe> [--nom "Nom complet"] [--role admin]
"""

from __future__ import annotations

import argparse

from app.auth.store import creer_utilisateur


def main() -> None:
    parser = argparse.ArgumentParser(description="Gestion des comptes ChurnGuard.")
    sous_commandes = parser.add_subparsers(dest="commande", required=True)

    creer = sous_commandes.add_parser("create", help="Crée ou remplace un compte utilisateur.")
    creer.add_argument("username")
    creer.add_argument("mot_de_passe")
    creer.add_argument("--nom", default=None, help="Nom complet affiché (défaut : identique au username).")
    creer.add_argument("--role", default="operateur")

    args = parser.parse_args()

    if args.commande == "create":
        utilisateur = creer_utilisateur(
            username=args.username,
            mot_de_passe=args.mot_de_passe,
            nom_complet=args.nom or args.username,
            role=args.role,
        )
        print(f"Compte créé : {utilisateur.username} ({utilisateur.role})")


if __name__ == "__main__":
    main()
