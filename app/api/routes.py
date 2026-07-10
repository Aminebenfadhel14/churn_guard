"""Routes de l'API REST (Couche 4 — Serving) — génériques et pilotées par le schéma.

- GET  /schema             : décrit les champs attendus (types, valeurs, bornes) du modèle actif.
- POST /predict            : prédit à partir d'un payload dynamique validé contre le schéma.
- POST /explain            : explique une prédiction (SHAP ou fallback d'ablation).
- POST /recommend          : suggère des actions de rétention priorisées (Next Best Actions).
- POST /what-if            : simule des changements de variables et calcule le delta de risque.
- GET  /clients/high-risk  : retourne la liste des clients présentant le plus haut risque de churn.
- POST /upload             : dépose un dataset (CSV/Excel/Parquet) dans data/ + aperçu du schéma.
- POST /train              : (ré)entraîne le pipeline sur le dernier dataset et publie le modèle actif.
"""

from __future__ import annotations

import os
import stat
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, File, HTTPException, UploadFile, Depends, Security
from fastapi.security.api_key import APIKeyHeader

from app.api.schema_service import (
    charger_drift_reference,
    charger_schema_actif,
    features_publiques,
    valider_entree,
)
from app.config import settings
from app.ingestion import charger_dataset
from app.ingestion.schema_registry import construire_schema
from app.explainability import expliquer_prediction
from app.modeling.predict import charger_meta, charger_modele, predire
from app.monitoring.drift import detecter_drift
from app.recommendations import generer_recommandations_expertes, recommandations_de_secours
from app.recommendations import cache as recommandations_cache

router = APIRouter(tags=["ChurnGuard"])

EXTENSIONS_OK = {".csv", ".xlsx", ".xls", ".parquet"}

# ----- Configuration de la Sécurité par Clé API -----
API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def verifier_cle_api(api_key: str = Security(api_key_header)) -> str:
    """Dépendance FastAPI pour valider la clé API.

    Si la clé configurée est la valeur par défaut ("change-me-please") ou vide,
    l'accès est autorisé librement pour simplifier le développement local et les tests.
    Sinon, la clé transmise dans l'en-tête 'x-api-key' doit correspondre exactement.
    """
    if settings.api_key and settings.api_key != "change-me-please":
        if not api_key or api_key != settings.api_key:
            raise HTTPException(
                status_code=403,
                detail="Accès refusé : clé API invalide ou absente (en-tête 'x-api-key').",
            )
    return api_key


@router.get("/schema")
def get_schema() -> dict[str, Any]:
    """Schéma du modèle actif (utilisé par le frontend pour générer le formulaire)."""
    try:
        schema = charger_schema_actif()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "cible": schema.get("cible"),
        "type_probleme": schema.get("type_probleme"),
        "n_lignes": schema.get("n_lignes"),
        "features": [
            {
                "nom": c["nom"], "type": c["type"], "valeurs": c.get("valeurs"),
                "min": c.get("min"), "max": c.get("max"),
            }
            for c in features_publiques(schema)
        ],
    }


@router.post("/predict", dependencies=[Depends(verifier_cle_api)])
def predict(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Prédit à partir d'un payload dynamique (champs = schéma actif)."""
    try:
        schema = charger_schema_actif()
        record = valider_entree(payload, schema)
        return predire(record)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Erreur de prédiction : {exc}") from exc


@router.post("/explain", dependencies=[Depends(verifier_cle_api)])
def explain(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Explique une prédiction : contributions SHAP (ou fallback d'ablation).

    Accepte le même payload dynamique que ``/predict``. Paramètre optionnel
    ``top_k`` (défaut 5) pour limiter le nombre de facteurs retournés.
    """
    try:
        schema = charger_schema_actif()
        data = dict(payload)
        top_k = int(data.pop("top_k", 5))
        record = valider_entree(data, schema)
        return expliquer_prediction(record, top_k=top_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Erreur d'explication : {exc}") from exc


def _generer_recommandations(
    record: dict[str, Any],
    risk_score: float,
    risk_level: str,
) -> tuple[list[dict[str, Any]], str]:
    """Génère les recommandations de rétention via l'IA experte (Groq).

    L'IA reçoit les facteurs de risque SHAP exprimés avec les vraies colonnes
    du dataset chargé et rédige des actions concrètes, spécifiques au client
    et au métier déduit du schéma. Si le LLM est indisponible ou que l'appel
    échoue, repli silencieux sur un message de secours minimal (pas de
    moteur de règles).

    Un cache en mémoire (``app.recommendations.cache``) évite de rappeler le
    LLM pour un client déjà traité récemment : la clé combine son identifiant
    (si disponible) et son score de risque arrondi.
    """
    cle_cache = recommandations_cache.construire_cle(record, risk_score)
    en_cache = recommandations_cache.obtenir(cle_cache)
    if en_cache is not None:
        return en_cache

    try:
        explication = expliquer_prediction(record, top_k=6)
        recos_ia = generer_recommandations_expertes(
            risk_score, risk_level, explication.get("features", [])
        )
    except Exception:  # noqa: BLE001 — repli silencieux sur le message de secours
        recos_ia = None

    if recos_ia:
        resultat = (recos_ia, "ia_experte")
    else:
        resultat = (recommandations_de_secours(risk_score, risk_level), "degrade")

    recommandations_cache.enregistrer(cle_cache, *resultat)
    return resultat


@router.post("/recommend", dependencies=[Depends(verifier_cle_api)])
def recommend(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Suggère des actions de rétention (Next Best Actions) priorisées pour un client.

    Accepte le même payload dynamique de caractéristiques client que ``/predict``.
    """
    try:
        schema = charger_schema_actif()
        record = valider_entree(payload, schema)

        # Effectue la prédiction pour obtenir le score de risque
        prediction = predire(record)
        risk_score = float(prediction["risk_score"])

        recos, source_recommendations = _generer_recommandations(
            record, risk_score, prediction["risk_level"]
        )

        return {
            "risk_score": risk_score,
            "risk_level": prediction["risk_level"],
            "prediction": prediction["prediction"],
            "modele": prediction["modele"],
            "recommendations": recos,
            "source_recommendations": source_recommendations,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Erreur de recommandation : {exc}") from exc


@router.post("/recommend/enriched", dependencies=[Depends(verifier_cle_api)])
def recommend_enriched(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Recommandations **enrichies** : actions de l'IA experte + plan de
    rétention rédigé par le moteur local de redaction.

    Seule la génération des actions appelle le LLM (Groq) ; le plan et
    l'email sont ensuite produits localement, sans appel externe.
    """
    try:
        schema = charger_schema_actif()
        record = valider_entree(payload, schema)

        prediction = predire(record)
        risk_score = float(prediction["risk_score"])
        recos, source_recommendations = _generer_recommandations(
            record, risk_score, prediction["risk_level"]
        )

        from app.recommendations.drafting import (
            generer_plan_retention,
            rediger_email_alerte,
        )

        plan = generer_plan_retention(
            record,
            risk_score,
            recos,
            risk_level=prediction["risk_level"],
            source_recommandations=source_recommendations,
        )
        email = rediger_email_alerte(
            record,
            risk_score,
            recos,
            risk_level=prediction["risk_level"],
            modele=prediction["modele"],
        )

        return {
            "risk_score": risk_score,
            "risk_level": prediction["risk_level"],
            "prediction": prediction["prediction"],
            "modele": prediction["modele"],
            "recommendations": recos,
            "plan_retention": plan,
            "email_alert": email,
            "source_plan": plan["source"],
            "source_email": email["source"],
            "source_recommendations": source_recommendations,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Erreur de recommandation enrichie : {exc}"
        ) from exc


@router.post("/copilot", dependencies=[Depends(verifier_cle_api)])
def copilot(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """**Retention Copilot** : traite un client de bout en bout.

    Enchaîne predict -> explain -> recommend, décide de l'escalade et renvoie
    une synthèse rédigée (par le LLM si configuré, sinon déterministe).
    Le payload est le même que ``/predict`` (les caractéristiques du client).
    """
    from app.copilot.agent import traiter_client

    resultat = traiter_client(payload)
    if not resultat.get("ok", False):
        raise HTTPException(status_code=400, detail=resultat.get("erreur", "Erreur copilot."))
    return resultat


@router.post("/copilot/chat", dependencies=[Depends(verifier_cle_api)])
def copilot_chat(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Assistant conversationnel du copilot : chat en langage naturel + tool-calling.

    Payload : ``{"messages": [{"role","content"}], "client": {...}}``.
    Le LLM choisit lui-même les outils (predict/explain/recommend/what-if…) et
    rédige une réponse. ``client`` (optionnel) fournit le client courant en contexte.
    """
    from app.copilot.chat import discuter

    messages = payload.get("messages", [])
    client = payload.get("client")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=422, detail="Champ 'messages' requis (liste non vide).")
    return discuter(messages, client=client if isinstance(client, dict) else None)


@router.post("/what-if", dependencies=[Depends(verifier_cle_api)])
def what_if(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Simule le score de risque d'un client suite à des modifications de variables.

    Format attendu :
    {
      "client": { ... caractéristiques actuelles du client ... },
      "overrides": { "nom_variable": nouvelle_valeur, ... }
    }
    """
    try:
        schema = charger_schema_actif()
        client_data = payload.get("client")
        overrides = payload.get("overrides")

        if client_data is None:
            raise ValueError("Le paramètre 'client' contenant le profil de base est obligatoire.")
        if overrides is None:
            raise ValueError("Le paramètre 'overrides' contenant les surcharges est obligatoire.")

        # Valider le profil d'origine
        record_orig = valider_entree(client_data, schema)

        # Créer et valider le profil modifié
        record_mod = dict(record_orig)
        for k, v in overrides.items():
            record_mod[k] = v
        record_mod = valider_entree(record_mod, schema)

        # Prédictions sur les deux états
        pred_orig = predire(record_orig)
        pred_mod = predire(record_mod)

        score_orig = float(pred_orig["risk_score"])
        score_mod = float(pred_mod["risk_score"])

        return {
            "original": {
                "risk_score": score_orig,
                "risk_level": pred_orig["risk_level"],
                "prediction": pred_orig["prediction"],
            },
            "simulated": {
                "risk_score": score_mod,
                "risk_level": pred_mod["risk_level"],
                "prediction": pred_mod["prediction"],
            },
            "delta": round(score_mod - score_orig, 2),
            "modele": pred_orig["modele"],
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Erreur de simulation What-If : {exc}") from exc


def _json_safe(v: Any) -> Any:
    """Convertit une valeur (potentiellement numpy) en type JSON-sérialisable."""
    import numpy as np
    import pandas as pd

    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def _dataset_du_modele_actif() -> Path:
    """Retourne le CSV de ``data/`` **compatible avec le modèle actif**.

    Le modèle attend des colonnes précises (rôle ``feature`` du schéma
    d'entraînement). On choisit donc le dataset qui les contient toutes, plutôt
    que le simple « dernier fichier uploadé » (qui peut correspondre à un autre
    modèle). À défaut de correspondance, on prend le plus récent.
    """
    from app.api.schema_service import charger_schema_actif, features_publiques

    csvs = sorted(
        settings.data_dir.glob("*.csv"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    if not csvs:
        raise HTTPException(
            status_code=400,
            detail="Aucun dataset. Uploade puis entraîne un modèle d'abord.",
        )

    try:
        requis = {c["nom"] for c in features_publiques(charger_schema_actif())}
    except Exception:  # noqa: BLE001 — schéma absent ou corrompu : repli sur le plus récent
        requis = set()

    if requis:
        for chemin in csvs:
            try:
                colonnes = set(charger_dataset(chemin).columns)
            except Exception:  # noqa: BLE001
                continue
            if requis <= colonnes:
                return chemin
    return csvs[0]


@router.get("/clients", dependencies=[Depends(verifier_cle_api)])
def get_clients(
    limit: int = 20,
    offset: int = 0,
    risk: str = "all",
    q: str = "",
) -> dict[str, Any]:
    """Liste **paginée** des clients du dataset actif, avec leur score de churn.

    Générique : fonctionne sur n'importe quel dataset. Score toutes les lignes
    avec le modèle actif, puis renvoie un identifiant de ligne, le score de
    risque, et une sélection de colonnes réelles à afficher.

    Args:
        limit: Nombre de lignes par page.
        offset: Décalage (pagination).
        risk: Filtre par niveau — ``all`` | ``faible`` | ``moyen`` | ``eleve``.
        q: Recherche plein-texte sur les colonnes affichées + l'identifiant.
    """
    try:
        from app.processing.features import ajouter_features
        from app.ingestion.schema import detecter_colonnes_id
        import pandas as pd
        import numpy as np

        chemin = _dataset_du_modele_actif()

        df = charger_dataset(chemin).copy()
        meta = charger_meta()
        cible = meta.get("cible", "")

        # Scoring vectorisé de toutes les lignes.
        pipeline = charger_modele()
        probas = pipeline.predict_proba(ajouter_features(df))[:, 1]
        df["risk_score"] = np.round(probas * 100, 1)

        # Identifiant de ligne + colonnes réelles à afficher (max 6).
        colonnes_id = detecter_colonnes_id(df, cible)
        id_col = colonnes_id[0] if colonnes_id else None
        exclues = set(colonnes_id) | {cible, "risk_score"}
        colonnes_affichage = [c for c in df.columns if c not in exclues][:6]

        # Filtre par niveau de risque (mêmes seuils que le badge du frontend :
        # faible < 30, moyen 30–70, élevé > 70).
        seuils = {"faible": (0.0, 30.0), "moyen": (30.0, 70.0001), "eleve": (70.0001, 101.0)}
        if risk in seuils:
            lo, hi = seuils[risk]
            df = df[(df["risk_score"] >= lo) & (df["risk_score"] < hi)]

        # Recherche plein-texte simple.
        if q.strip():
            ql = q.strip().lower()
            cols_rech = colonnes_affichage + ([id_col] if id_col else [])
            if cols_rech:
                masque = (
                    df[cols_rech].astype(str)
                    .apply(lambda s: s.str.lower().str.contains(ql, na=False))
                    .any(axis=1)
                )
                df = df[masque]

        # Tri par risque décroissant + pagination.
        df = df.sort_values(by="risk_score", ascending=False)
        total = int(len(df))
        page = df.iloc[max(0, offset): max(0, offset) + max(1, limit)]

        clients: list[dict[str, Any]] = []
        for idx, row in page.iterrows():
            rid = str(row[id_col]) if id_col else str(idx)
            clients.append({
                "id": rid,
                "risk_score": float(row["risk_score"]),
                "values": {c: _json_safe(row[c]) for c in colonnes_affichage},
            })

        return {
            "dataset": chemin.name,
            "cible": cible,
            "id_col": id_col,
            "colonnes": colonnes_affichage,
            "total": total,
            "offset": offset,
            "limit": limit,
            "clients": clients,
        }
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Aucun modèle actif. Lance un entraînement d'abord.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du listing des clients : {exc}",
        ) from exc


@router.get("/dashboard", dependencies=[Depends(verifier_cle_api)])
def get_dashboard() -> dict[str, Any]:
    """Agrégats du tableau de bord, calculés sur le dataset actif scoré.

    Générique et dynamique : KPI, répartition par niveau de risque, histogramme
    des scores et top-10 des clients à risque. Se met à jour à chaque changement
    de modèle actif.
    """
    try:
        from app.processing.features import ajouter_features
        from app.ingestion.schema import detecter_colonnes_id
        import numpy as np

        chemin = _dataset_du_modele_actif()
        df = charger_dataset(chemin).copy()
        meta = charger_meta()
        cible = meta.get("cible", "")

        pipeline = charger_modele()
        scores = np.round(pipeline.predict_proba(ajouter_features(df))[:, 1] * 100, 1)
        df["risk_score"] = scores
        total = int(len(df))

        # Répartition par niveau (mêmes seuils que le badge : <30, 30-70, >70).
        faible = int((scores < 30).sum())
        eleve = int((scores > 70).sum())
        moyen = total - faible - eleve
        distribution = [
            {"level": "Faible", "count": faible, "key": "faible"},
            {"level": "Moyen", "count": moyen, "key": "moyen"},
            {"level": "Élevé", "count": eleve, "key": "eleve"},
        ]

        # Histogramme : 10 tranches de 0 à 100.
        histogram = []
        for b in range(0, 100, 10):
            haut = (b + 10) if b < 90 else 100.1
            c = int(((scores >= b) & (scores < haut)).sum())
            histogram.append({"tranche": f"{b}–{b + 10}", "count": c})

        # KPI.
        churners = int((scores > 50).sum())
        stats = {
            "total": total,
            "at_risk_count": eleve,
            "at_risk_pct": round(eleve / total * 100, 1) if total else 0.0,
            "avg_churn_rate": round(churners / total * 100, 1) if total else 0.0,
            "avg_score": round(float(scores.mean()), 1) if total else 0.0,
        }

        # Top-10 clients à risque (générique : id + quelques colonnes réelles).
        colonnes_id = detecter_colonnes_id(df, cible)
        id_col = colonnes_id[0] if colonnes_id else None
        exclues = set(colonnes_id) | {cible, "risk_score"}
        colonnes = [c for c in df.columns if c not in exclues][:4]
        top = df.sort_values("risk_score", ascending=False).head(10)
        top_clients = [
            {
                "id": str(row[id_col]) if id_col else str(idx),
                "risk_score": float(row["risk_score"]),
                "values": {c: _json_safe(row[c]) for c in colonnes},
            }
            for idx, row in top.iterrows()
        ]

        return {
            "dataset": chemin.name,
            "cible": cible,
            "stats": stats,
            "distribution": distribution,
            "histogram": histogram,
            "id_col": id_col,
            "colonnes": colonnes,
            "top_clients": top_clients,
        }
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Aucun modèle actif. Lance un entraînement d'abord.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Erreur du tableau de bord : {exc}",
        ) from exc


@router.get("/clients/high-risk", dependencies=[Depends(verifier_cle_api)])
def get_high_risk_clients(limit: int = 10) -> dict[str, Any]:
    """Retourne la liste des clients présentant le plus haut risque de churn.

    Lit le dataset actif de manière vectorisée et renvoie le top `limit` des clients à haut risque.
    """
    try:
        from app.processing.features import ajouter_features
        import pandas as pd
        import numpy as np

        # Dataset compatible avec le modèle actif (pas juste le dernier uploadé).
        chemin = _dataset_du_modele_actif()

        df = charger_dataset(chemin)
        meta = charger_meta()
        cible = meta.get("cible", "")

        # Déterminer les colonnes d'identifiant pour l'affichage
        from app.ingestion.schema import detecter_colonnes_id
        colonnes_id = detecter_colonnes_id(df, cible)

        col_affichage = list(colonnes_id)
        if "Surname" in df.columns:
            col_affichage.append("Surname")
        if "Gender" in df.columns:
            col_affichage.append("Gender")
        if "Age" in df.columns:
            col_affichage.append("Age")

        # Prédiction vectorisée rapide sur tout le DataFrame
        pipeline = charger_modele()
        df_feats = ajouter_features(df)
        probas = pipeline.predict_proba(df_feats)[:, 1]
        df["risk_score"] = np.round(probas * 100, 1)

        # Trier par risque décroissant
        df_tri = df.sort_values(by="risk_score", ascending=False).head(limit)

        # Structurer la réponse JSON
        clients = []
        for idx, row in df_tri.iterrows():
            client_dict = row.to_dict()
            client_clean = {k: (None if pd.isna(v) else v) for k, v in client_dict.items()}

            id_client = str(client_clean.get(col_affichage[0])) if col_affichage else str(idx)
            nom_client = str(client_clean.get("Surname", f"Client {id_client}"))

            clients.append({
                "id": id_client,
                "name": nom_client,
                "risk_score": client_clean["risk_score"],
                "details": client_clean,
            })

        return {
            "dataset": chemin.name,
            "total_clients": len(df),
            "limit": limit,
            "clients": clients,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du listing des clients à risque : {exc}",
        ) from exc


def _ecrire_dataset(destination: Path, contenu: bytes) -> Path:
    """Écrit le dataset uploadé de façon robuste sous Windows.

    Gère le cas fréquent où le fichier cible existe déjà et est verrouillé
    (ouvert dans Excel) ou en lecture seule (``PermissionError``) :
    1) on tente de retirer l'attribut lecture seule puis d'écrire ;
    2) si l'écriture échoue quand même, on écrit sous un nom horodaté unique
       afin de ne jamais bloquer l'upload.
    Retourne le chemin réellement écrit.
    """
    def _tenter_ecriture(chemin: Path) -> None:
        if chemin.exists():
            try:  # retire un éventuel attribut "lecture seule"
                os.chmod(chemin, stat.S_IWRITE)
            except OSError:
                pass
        chemin.write_bytes(contenu)

    try:
        _tenter_ecriture(destination)
        return destination
    except PermissionError:
        horodatage = time.strftime("%Y%m%d_%H%M%S")
        secours = destination.with_name(
            f"{destination.stem}_{horodatage}{destination.suffix}"
        )
        _tenter_ecriture(secours)
        return secours


@router.post("/upload", dependencies=[Depends(verifier_cle_api)])
def upload(file: UploadFile = File(...), auto_train: bool = False) -> dict[str, Any]:
    """Dépose un dataset dans data/ et renvoie un aperçu du schéma détecté.

    L'entraînement **n'est pas** lancé automatiquement : il est déclenché
    ensuite par l'utilisateur via ``POST /train/start`` (bouton du frontend).

    Args:
        file: Le dataset (CSV/Excel/Parquet).
        auto_train: Optionnel. Si vrai, lance aussi l'entraînement dès l'upload
            (désactivé par défaut). Le suivi se fait via ``GET /train/status``.
    """
    nom = file.filename or "dataset.csv"
    ext = "." + nom.rsplit(".", 1)[-1].lower() if "." in nom else ""
    if ext not in EXTENSIONS_OK:
        raise HTTPException(
            status_code=422,
            detail=f"Format non supporté ({ext}). Attendu : {sorted(EXTENSIONS_OK)}.",
        )

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    destination = _ecrire_dataset(settings.data_dir / nom, file.file.read())
    nom = destination.name

    try:
        df = charger_dataset(destination)
        schema = construire_schema(df)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Fichier illisible : {exc}") from exc

    # Drift vs le dataset ayant servi à entraîner le modèle actif (s'il existe).
    # Purement informatif : un échec de calcul ne doit jamais bloquer l'upload.
    drift = None
    reference_drift = charger_drift_reference()
    if reference_drift:
        try:
            drift = detecter_drift(df, reference_drift)
        except Exception:  # noqa: BLE001
            drift = None

    reponse: dict[str, Any] = {
        "fichier": nom,
        "lignes": int(df.shape[0]),
        "colonnes": int(df.shape[1]),
        "cible_detectee": schema.cible,
        "type_probleme": schema.type_probleme,
        "features": [c.nom for c in schema.features()],
        "entrainement": "ignore",
        "drift": drift,
    }

    # Déclenche l'entraînement en arrière-plan : la requête répond tout de suite.
    if auto_train:
        from app.api.training_state import lancer_entrainement

        etat = lancer_entrainement(destination)
        reponse["entrainement"] = etat["statut"]

    return reponse


@router.get("/train/status")
def train_status() -> dict[str, Any]:
    """Retourne l'état de l'entraînement en cours ou du dernier entraînement.

    Le frontend interroge ce endpoint après avoir lancé l'entraînement pour
    suivre la progression (statut ``en_cours`` → ``termine`` / ``echec``) et
    récupérer les métriques.
    """
    from app.api.training_state import etat_courant

    return etat_courant()


@router.post("/train/start", dependencies=[Depends(verifier_cle_api)])
def train_start(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Lance l'entraînement **en arrière-plan** sur le dataset choisi.

    Déclenché par le bouton « Lancer l'entraînement » du frontend. Répond
    immédiatement (pas de blocage) ; le suivi se fait via ``GET /train/status``.

    Args:
        payload: ``{"fichier": "<nom>"}`` pour cibler un fichier précis de
            ``data/`` ; sinon le dataset le plus récent est utilisé.
    """
    from app.api.training_state import lancer_entrainement

    fichier = payload.get("fichier")
    if fichier:
        chemin = settings.data_dir / fichier
        if not chemin.exists():
            raise HTTPException(status_code=404, detail=f"Fichier introuvable : {fichier}")
    else:
        csvs = sorted(
            settings.data_dir.glob("*.csv"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        if not csvs:
            raise HTTPException(
                status_code=400,
                detail="Aucun dataset dans data/. Uploade un fichier d'abord.",
            )
        chemin = csvs[0]

    return lancer_entrainement(chemin)


@router.post("/train", dependencies=[Depends(verifier_cle_api)])
def train(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """(Ré)entraîne le pipeline sur le dataset le plus récent de data/.

    Entraînement synchrone : peut prendre plusieurs minutes selon la taille.
    """
    from app.modeling.train import entrainer_et_selectionner, formater_resultat_entrainement

    fichier = payload.get("fichier")
    if fichier:
        chemin = settings.data_dir / fichier
        if not chemin.exists():
            raise HTTPException(status_code=404, detail=f"Fichier introuvable : {fichier}")
    else:
        csvs = sorted(
            settings.data_dir.glob("*.csv"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        if not csvs:
            raise HTTPException(status_code=400, detail="Aucun dataset dans data/. Uploade un fichier d'abord.")
        chemin = csvs[0]

    try:
        df = charger_dataset(chemin)
        res = entrainer_et_selectionner(df)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Échec de l'entraînement : {exc}") from exc

    charger_modele.cache_clear()
    charger_meta.cache_clear()
    recommandations_cache.vider()

    return formater_resultat_entrainement(res, fichier=chemin.name)
# Fin des routes ChurnGuard.
