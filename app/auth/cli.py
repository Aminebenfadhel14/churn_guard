"""CLI d'administration des comptes utilisateur (Couche Authentification).

Usage :
    python -m app.auth.cli create <username> <mot_de_passe> [--nom "Nom complet"] [--role admin] [--organisation-id 1]

Sans ``--organisation-id``, le compte est rattaché à l'organisation
"Default" (créée automatiquement au premier démarrage de l'API).
"""

from __future__ import annotations

import argparse

from app.auth.models import Organisation
from app.auth.store import creer_utilisateur
from app.db import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Gestion des comptes ChurnGuard.")
    sous_commandes = parser.add_subparsers(dest="commande", required=True)

    creer = sous_commandes.add_parser("create", help="Crée un compte utilisateur.")
    creer.add_argument("username")
    creer.add_argument("mot_de_passe")
    creer.add_argument("--nom", default=None, help="Nom complet affiché (défaut : identique au username).")
    creer.add_argument("--role", default="operateur")
    creer.add_argument(
        "--email", default=None, help="Email (active la connexion en 2 étapes avec code de vérification)."
    )
    creer.add_argument(
        "--organisation-id",
        type=int,
        default=None,
        help="ID de l'organisation (défaut : l'organisation 'Default').",
    )

    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.commande == "create":
            organisation_id = args.organisation_id
            if organisation_id is None:
                defaut = db.query(Organisation).filter(Organisation.nom == "Default").first()
                if defaut is None:
                    raise SystemExit(
                        "Aucune organisation 'Default' trouvée : démarrez l'API une première "
                        "fois (elle l'amorce automatiquement) ou passez --organisation-id."
                    )
                organisation_id = defaut.id

            utilisateur = creer_utilisateur(
                db,
                organisation_id=organisation_id,
                username=args.username,
                mot_de_passe=args.mot_de_passe,
                nom_complet=args.nom or args.username,
                role=args.role,
                email=args.email,
            )
            print(f"Compte créé : {utilisateur.username} ({utilisateur.role}, org {organisation_id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
