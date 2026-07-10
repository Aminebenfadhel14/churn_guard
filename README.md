# ChurnGuard
this pltform 
**Plateforme universelle de prédiction et d'explication de l'attrition client (churn).**

ChurnGuard ingère un dataset client de n'importe quel secteur, entraîne
automatiquement plusieurs modèles de Machine Learning, sélectionne le meilleur,
explique chaque prédiction avec SHAP, recommande des actions de rétention
priorisées, et expose le tout via une API REST FastAPI. Une couche MCP permet
d'interroger la plateforme en langage naturel depuis Claude Desktop.

---

## Objectif

Rendre la prédiction du churn accessible et exploitable pour tout métier :
1. **Ingérer** un dataset (CSV / Excel / Parquet) et détecter automatiquement son schéma.
2. **Nettoyer** et enrichir les données (feature engineering, gestion du déséquilibre).
3. **Entraîner** et comparer plusieurs modèles, puis sélectionner le meilleur.
4. **Expliquer** chaque prédiction individuelle (SHAP).
5. **Recommander** des actions de rétention selon le niveau de risque.
6. **Exposer** le tout via une API REST documentée et une couche MCP.

---

## Stack technique

| Domaine            | Technologies                                                        |
|--------------------|---------------------------------------------------------------------|
| Backend / API      | Python 3.11+, FastAPI, Uvicorn                                       |
| Machine Learning   | scikit-learn, XGBoost, LightGBM, imbalanced-learn (SMOTE)           |
| IA explicable      | SHAP                                                                 |
| Données            | pandas, NumPy                                                        |
| MLOps              | MLflow, joblib, Docker                                               |
| Couche MCP         | FastMCP (SDK Python)                                                 |
| Frontend           | Généré via v0 (intégration ultérieure)                              |
| Outillage          | Git, pytest                                                          |

---

## Architecture (4 couches)

```
Dataset ─▶ [1] Ingestion ─▶ [2] Processing ─▶ [3] Modeling ─▶ [4] Serving
              détection        nettoyage &        entraînement    API REST
              de schéma        features           + sélection     + Explicabilité (SHAP)
                                                                   + Recommandations
                                                                          │
                                                                          ▼
                                                                   Couche MCP
                                                                   (Claude Desktop)
```

- **Couche 1 — Ingestion** : chargement multi-format et détection automatique du schéma (cible, IDs, fuites de données).
- **Couche 2 — Processing** : nettoyage adaptatif, encodage des variables catégorielles, SMOTE.
- **Couche 3 — Modeling** : entraînement multi-modèles, sélection par ROC-AUC / F1, suivi MLflow.
- **Couche 4 — Serving** : API FastAPI (`/predict`, `/explain`, `/recommend`, `/what-if`), explicabilité SHAP, moteur de recommandations.
- **MCP** : expose la plateforme à Claude Desktop en langage naturel.

---

## Statut

🚧 Projet en cours de construction (stage). Voir les étapes d'avancement dans les commits Git.

## Installation

_À compléter dans les étapes suivantes (environnement virtuel, dépendances, lancement)._

## Licence

Projet de stage — usage pédagogique.
