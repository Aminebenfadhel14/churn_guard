"""Entraînement, comparaison et sélection automatique de modèles (Couche 3).

Générique et piloté par le schéma : aucune colonne n'est codée en dur, la cible
est encodée automatiquement (numérique ou texte), et le meilleur modèle est
sauvegardé avec son schéma dans le model registry.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.base import clone
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.preprocessing import LabelEncoder

from app.config import settings
from app.ingestion.schema import RapportSchema
from app.ingestion.schema_registry import construire_schema
from app.modeling.models import modeles_disponibles
from app.modeling.registry import enregistrer_modele
from app.monitoring.drift import construire_reference
from app.processing import est_desequilibre, preparer_donnees


@dataclass
class ResultatModele:
    """Métriques d'un modèle évalué."""

    nom: str
    cv_roc_auc: float
    cv_roc_auc_std: float
    cv_f1: float
    cv_f1_std: float
    cv_accuracy: float
    cv_accuracy_std: float
    test_roc_auc: float
    test_f1: float
    test_accuracy: float
    test_precision: float
    test_recall: float

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ResultatEntrainement:
    """Résultat global de l'entraînement."""

    meilleur_modele: str
    resultats: list[ResultatModele] = field(default_factory=list)
    raison_selection: str = ""
    chemin_modele: str = ""
    chemin_meta: str = ""
    version: str = ""


def formater_resultat_entrainement(
    resultat: ResultatEntrainement,
    *,
    fichier: str | None = None,
) -> dict[str, Any]:
    """Prepare une reponse JSON detaillee pour l'API et le frontend."""
    if not resultat.resultats:
        raise ValueError("Aucun resultat de modele a formater.")

    meilleur = next(
        (r for r in resultat.resultats if r.nom == resultat.meilleur_modele),
        None,
    )
    if meilleur is None:
        meilleur = max(resultat.resultats, key=lambda r: (r.test_roc_auc, r.test_f1))
    resultats_tries = sorted(
        resultat.resultats,
        key=lambda r: (r.test_roc_auc, r.test_f1),
        reverse=True,
    )
    reponse: dict[str, Any] = {
        "meilleur_modele": resultat.meilleur_modele,
        "version": resultat.version,
        "raison_selection": resultat.raison_selection,
        "test_roc_auc": round(meilleur.test_roc_auc, 4),
        "test_f1": round(meilleur.test_f1, 4),
        "test_accuracy": round(meilleur.test_accuracy, 4),
        "modeles_compares": [r.nom for r in resultats_tries],
        "resultats_modeles": [
            {
                "nom": r.nom,
                "selectionne": r.nom == resultat.meilleur_modele,
                "cv_roc_auc": round(r.cv_roc_auc, 4),
                "cv_roc_auc_std": round(r.cv_roc_auc_std, 4),
                "cv_f1": round(r.cv_f1, 4),
                "cv_f1_std": round(r.cv_f1_std, 4),
                "cv_accuracy": round(r.cv_accuracy, 4),
                "cv_accuracy_std": round(r.cv_accuracy_std, 4),
                "test_roc_auc": round(r.test_roc_auc, 4),
                "test_f1": round(r.test_f1, 4),
                "test_accuracy": round(r.test_accuracy, 4),
                "test_precision": round(r.test_precision, 4),
                "test_recall": round(r.test_recall, 4),
            }
            for r in resultats_tries
        ],
    }
    if fichier is not None:
        reponse["fichier"] = fichier
    return reponse


def construire_pipeline(
    preprocesseur, modele, *, appliquer_smote: bool, random_state: int = 42
) -> ImbPipeline:
    """Assemble le pipeline préprocesseur -> (SMOTE) -> modèle."""
    etapes = [("preprocesseur", clone(preprocesseur))]
    if appliquer_smote:
        from imblearn.over_sampling import SMOTE

        etapes.append(("smote", SMOTE(random_state=random_state)))
    etapes.append(("modele", modele))
    return ImbPipeline(steps=etapes)


def _modele_pour_cv(modele: Any) -> Any:
    """Clone un modèle en désactivant son parallélisme interne (``n_jobs=1``).

    Évite la sur-souscription : la validation croisée parallélise déjà les folds.
    Sans ça, ``cross_validate(n_jobs=-1)`` × modèle ``n_jobs=-1`` lance
    (folds × cœurs) processus/threads → explosion mémoire et crash sur gros
    dataset. On borne ici le parallélisme au seul niveau des folds.
    """
    m = clone(modele)
    if "n_jobs" in m.get_params():
        m.set_params(n_jobs=1)
    return m


def _n_jobs_cv(n_splits: int) -> int:
    """Nombre de workers pour la validation croisée, borné pour rester stable.

    On plafonne au min(nombre de folds, moitié des cœurs) afin de garder de la
    RAM et des cœurs disponibles pour le reste (API, etc.).
    """
    n_cpu = os.cpu_count() or 2
    return max(1, min(n_splits, n_cpu // 2 or 1))


def _encoder_cible(y_brut: pd.Series) -> tuple[pd.Series, list[Any]]:
    """Encode la cible en entiers 0..K-1 (générique, tout secteur).

    Retourne la cible encodée et la liste des classes (index = valeur encodée).
    """
    if pd.api.types.is_numeric_dtype(y_brut):
        y = y_brut.astype(int)
        classes = sorted(pd.unique(y).tolist())
        return y, [int(c) for c in classes]
    encodeur = LabelEncoder()
    y = pd.Series(encodeur.fit_transform(y_brut), index=y_brut.index)
    return y, [str(c) for c in encodeur.classes_]


def _expliquer_selection(resultats: list[ResultatModele], meilleur_modele: str) -> str:
    """Explique le choix du meilleur modele avec le critere de selection."""
    if not resultats:
        return ""

    tries = sorted(
        resultats,
        key=lambda r: (r.test_roc_auc, r.test_f1),
        reverse=True,
    )
    meilleur = tries[0]
    second = tries[1] if len(tries) > 1 else None

    raison = (
        f"{meilleur_modele} a ete choisi car il obtient le meilleur ROC-AUC test "
        f"({meilleur.test_roc_auc:.4f}), avec F1={meilleur.test_f1:.4f} "
        f"et accuracy={meilleur.test_accuracy:.4f}. Le ROC-AUC est le critere "
        "principal car il mesure la capacite a classer les clients a risque, "
        "meme quand les classes churn/non-churn sont desequilibrees; le F1 sert "
        "de departage si deux modeles sont proches."
    )
    if second is not None:
        raison += (
            f" Le modele suivant est {second.nom} "
            f"(ROC-AUC={second.test_roc_auc:.4f}, F1={second.test_f1:.4f}, "
            f"accuracy={second.test_accuracy:.4f})."
        )
    return raison


def entrainer_et_selectionner(
    df: pd.DataFrame,
    schema: RapportSchema | None = None,
    *,
    test_size: float = 0.2,
    cv: int = 3,
    random_state: int = 42,
    modeles: dict[str, Any] | None = None,
    dossier_modeles: Path | None = None,
    nom_dataset: str | None = None,
) -> ResultatEntrainement:
    """Entraîne, compare, sélectionne le meilleur modèle et l'enregistre.

    Fonctionne pour n'importe quel dataset : cible numérique ou textuelle,
    colonnes détectées automatiquement via le schéma.
    """
    prep = preparer_donnees(df, schema)
    X = prep.X
    y, classes = _encoder_cible(prep.y)
    appliquer_smote = est_desequilibre(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state
    )

    skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=random_state)
    modeles = modeles or modeles_disponibles(random_state=random_state)
    mlflow = _init_mlflow()
    n_jobs_cv = _n_jobs_cv(cv)

    resultats: list[ResultatModele] = []
    meilleur: tuple[float, float, str, ImbPipeline] | None = None

    for nom, modele in modeles.items():
        # Parallélisme borné : folds en parallèle, modèle mono-thread (anti-crash).
        pipe = construire_pipeline(
            prep.preprocesseur, _modele_pour_cv(modele),
            appliquer_smote=appliquer_smote, random_state=random_state,
        )
        scores = cross_validate(
            pipe, X_train, y_train, cv=skf,
            scoring=["roc_auc", "f1", "accuracy"], n_jobs=n_jobs_cv,
        )
        pipe.fit(X_train, y_train)
        proba = pipe.predict_proba(X_test)[:, 1]
        pred = pipe.predict(X_test)
        res = ResultatModele(
            nom=nom,
            cv_roc_auc=float(scores["test_roc_auc"].mean()),
            cv_roc_auc_std=float(scores["test_roc_auc"].std()),
            cv_f1=float(scores["test_f1"].mean()),
            cv_f1_std=float(scores["test_f1"].std()),
            cv_accuracy=float(scores["test_accuracy"].mean()),
            cv_accuracy_std=float(scores["test_accuracy"].std()),
            test_roc_auc=float(roc_auc_score(y_test, proba)),
            test_f1=float(f1_score(y_test, pred)),
            test_accuracy=float(accuracy_score(y_test, pred)),
            test_precision=float(precision_score(y_test, pred, zero_division=0)),
            test_recall=float(recall_score(y_test, pred, zero_division=0)),
        )
        resultats.append(res)

        if mlflow is not None:
            with mlflow.start_run(run_name=nom):
                mlflow.log_param("modele", nom)
                mlflow.log_param("smote", appliquer_smote)
                mlflow.log_metrics({
                    "cv_roc_auc": res.cv_roc_auc, "cv_f1": res.cv_f1,
                    "cv_accuracy": res.cv_accuracy,
                    "test_roc_auc": res.test_roc_auc, "test_f1": res.test_f1,
                    "test_accuracy": res.test_accuracy,
                    "test_precision": res.test_precision, "test_recall": res.test_recall,
                })

        cle = (res.test_roc_auc, res.test_f1)
        if meilleur is None or cle > (meilleur[0], meilleur[1]):
            meilleur = (res.test_roc_auc, res.test_f1, nom, pipe)

    assert meilleur is not None, "Aucun modèle entraîné."
    _, _, nom_best, _ = meilleur
    raison_selection = _expliquer_selection(resultats, nom_best)

    # Ré-entraînement du meilleur modèle sur toutes les données (production).
    pipe_final = construire_pipeline(
        prep.preprocesseur, modeles[nom_best],
        appliquer_smote=appliquer_smote, random_state=random_state,
    )
    pipe_final.fit(X, y)

    # Schéma complet du dataset + référence de drift + enregistrement dans le registry.
    schema_complet = construire_schema(df, cible=prep.y.name)
    reference_drift = construire_reference(df, [c.nom for c in schema_complet.features()])
    meta = enregistrer_modele(
        pipe_final, schema_complet,
        [r.as_dict() for r in resultats], nom_best, classes, raison_selection,
        dossier_modeles=dossier_modeles,
        reference_drift=reference_drift,
        nom_dataset=nom_dataset,
    )

    dossier = dossier_modeles or settings.models_dir
    return ResultatEntrainement(
        meilleur_modele=nom_best,
        resultats=resultats,
        raison_selection=raison_selection,
        chemin_modele=str(dossier / "best_model.joblib"),
        chemin_meta=str(dossier / "model_meta.json"),
        version=meta["version"],
    )


def _init_mlflow():
    """Initialise MLflow si disponible, sinon retourne ``None``."""
    try:
        import mlflow

        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(settings.mlflow_experiment_name)
        return mlflow
    except Exception:
        return None
