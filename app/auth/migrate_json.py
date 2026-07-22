"""Migration unique : importe l'ancien annuaire JSON (``users.json``) dans la
base de donnees, sous une organisation "Default".

Les hashs de mot de passe (PBKDF2, voir app/auth/passwords.py) sont copies
tels quels : aucun mot de passe n'a besoin d'etre re-saisi.

Usage :
    python -m app.auth.migrate_json
"""

from __future__ import annotations

import json

from app.auth.models import Organisation, Utilisateur
from app.config import settings
from app.db import SessionLocal


def migrer() -> None:
    chemin = settings.users_file
    if not chemin.exists():
        print(f"Aucun fichier {chemin} trouve : rien a migrer.")
        return

    brut: dict[str, dict[str, str]] = json.loads(chemin.read_text(encoding="utf-8"))
    if not brut:
        print("users.json est vide : rien a migrer.")
        return

    db = SessionLocal()
    try:
        organisation = db.query(Organisation).filter(Organisation.nom == "Default").first()
        if organisation is None:
            organisation = Organisation(nom="Default")
            db.add(organisation)
            db.flush()

        migres, ignores = 0, 0
        for username, donnees in brut.items():
            if db.query(Utilisateur).filter(Utilisateur.username == username).first() is not None:
                print(f"  - {username} : deja present en base, ignore.")
                ignores += 1
                continue
            db.add(
                Utilisateur(
                    organisation_id=organisation.id,
                    username=username,
                    mot_de_passe_hash=donnees["mot_de_passe_hash"],
                    nom_complet=donnees.get("nom_complet", username),
                    role=donnees.get("role", "operateur"),
                )
            )
            migres += 1
        db.commit()
        print(f"Migration terminee : {migres} compte(s) importe(s), {ignores} ignore(s).")
    finally:
        db.close()


if __name__ == "__main__":
    migrer()
