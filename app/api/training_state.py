"""Suivi d'état d'un entraînement lancé en arrière-plan (thread-safe).

L'upload d'un dataset déclenche l'entraînement dans un thread séparé afin que la
requête HTTP réponde immédiatement (pas de blocage/timeout côté frontend, pas de
crash de la boucle serveur). Ce module conserve l'état courant de l'entraînement,
consultable via ``GET /train/status``.
"""

from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings
from app.ingestion import charger_dataset
from app.modeling.predict import vider_caches_modele
from app.modeling.train import entrainer_et_selectionner, formater_resultat_entrainement
from app.recommendations import cache as recommandations_cache

# Verrou protégeant l'accès concurrent à l'état partagé.
_verrou = threading.Lock()

# État courant de l'entraînement.
# statut : "idle" | "en_cours" | "termine" | "echec"
_etat: dict[str, Any] = {
    "statut": "idle",
    "fichier": None,
    "message": "Aucun entraînement lancé.",
    "resultat": None,
    "erreur": None,
    "demarre_a": None,
    "termine_a": None,
}


def etat_courant() -> dict[str, Any]:
    """Retourne une copie de l'état courant de l'entraînement."""
    with _verrou:
        return dict(_etat)


def _maj(**champs: Any) -> None:
    """Met à jour l'état partagé de façon atomique."""
    with _verrou:
        _etat.update(champs)


def entrainement_en_cours() -> bool:
    """Indique si un entraînement est déjà en cours (évite les lancements multiples)."""
    with _verrou:
        return _etat["statut"] == "en_cours"


def _executer(
    chemin: Path,
    username: str | None = None,
    organisation_id: int | None = None,
    dossier_actif: Path | None = None,
) -> None:
    """Exécute l'entraînement et met à jour l'état (appelé dans un thread).

    ``username``/``organisation_id`` sont passés en valeurs simples (pas via
    une dépendance FastAPI) car ce thread n'a pas accès à la requête HTTP
    d'origine — voir app/api/routes.py::train_start pour leur résolution.
    ``dossier_actif`` : où écrire les fichiers du modèle actif (dossier
    personnel de l'opérateur, ou racine pour l'admin/clé API) — le registre,
    lui, reste toujours partagé à la racine (voir app/modeling/registry.py).
    """
    try:
        df: pd.DataFrame = charger_dataset(chemin)
        res = entrainer_et_selectionner(
            df,
            nom_dataset=chemin.name,
            username=username,
            organisation_id=organisation_id,
            dossier_actif=dossier_actif,
        )

        # Invalide les caches pour que l'API serve immédiatement le nouveau modèle.
        vider_caches_modele()
        recommandations_cache.vider()

        _maj(
            statut="termine",
            message=f"Entraînement terminé : {res.meilleur_modele} sélectionné.",
            resultat=formater_resultat_entrainement(res, fichier=chemin.name),
            erreur=None,
            termine_a=time.time(),
        )
    except Exception as exc:  # noqa: BLE001
        _maj(
            statut="echec",
            message="Échec de l'entraînement.",
            erreur=f"{type(exc).__name__}: {exc}",
            termine_a=time.time(),
        )
        traceback.print_exc()


def lancer_entrainement(
    chemin: Path,
    username: str | None = None,
    organisation_id: int | None = None,
    dossier_actif: Path | None = None,
) -> dict[str, Any]:
    """Démarre un entraînement en arrière-plan sur le fichier donné.

    Retourne immédiatement l'état initial. Si un entraînement est déjà en cours,
    ne fait rien et retourne l'état courant. ``dossier_actif`` : voir ``_executer``.
    """
    if entrainement_en_cours():
        return etat_courant()

    _maj(
        statut="en_cours",
        fichier=chemin.name,
        message="Entraînement en cours… (comparaison des modèles)",
        resultat=None,
        erreur=None,
        demarre_a=time.time(),
        termine_a=None,
    )

    thread = threading.Thread(
        target=_executer,
        args=(chemin, username, organisation_id, dossier_actif),
        daemon=True,
    )
    thread.start()
    return etat_courant()
