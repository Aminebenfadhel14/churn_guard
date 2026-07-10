# ChurnGuard — Prompts par étape (à copier-coller dans Claude)

Ce fichier contient un prompt autonome pour chacune des 12 étapes du projet.
Copie-colle le bloc de l'étape voulue. Le **contexte commun** ci-dessous peut être
collé une seule fois en début de conversation, ou rappelé dans chaque prompt.

---

## 🎯 Contexte commun (à coller en tête de conversation)

```
Tu es un ingénieur logiciel senior spécialisé en data science et MLOps.
Projet : ChurnGuard — plateforme universelle de prédiction et d'explication
de l'attrition client (churn), applicable à tout secteur. Elle ingère un dataset,
entraîne plusieurs modèles ML, sélectionne le meilleur, explique chaque prédiction
(SHAP), recommande des actions de rétention, expose le tout via une API REST FastAPI,
et ajoute une couche MCP pour interroger la plateforme en langage naturel depuis
Claude Desktop.

Stack : Python 3.11+, FastAPI, scikit-learn, XGBoost, LightGBM, SHAP,
imbalanced-learn (SMOTE), pandas, NumPy, MLflow, joblib, Docker, FastMCP, pytest.

Règles de travail :
- Code propre, commenté en français, avec type hints et docstrings.
- Config via variables d'environnement (.env), jamais de secrets en dur.
- Commits Git réguliers (convention feat:, fix:, chore:…).
- Avance étape par étape : montre le résultat, explique, attends mon "OK".
- Si une info manque, pose la question avant de coder.
```

---

## Étape 1 — Initialisation du projet et de Git

```
ÉTAPE 1 — Initialisation du projet et de Git.
- Crée le dossier racine "churnguard".
- Initialise un dépôt Git (git init).
- Crée un .gitignore adapté à Python (venv, __pycache__, .env, *.pkl,
  mlruns/, data/, models/, etc.).
- Crée un README.md initial décrivant le projet, la stack et l'architecture.
- Fais un premier commit "chore: initialisation du projet".
Montre les commandes et fichiers, explique, puis attends ma validation.
```

---

## Étape 2 — Environnement virtuel (venv)

```
ÉTAPE 2 — Environnement virtuel.
- Crée un venv (python -m venv venv).
- Donne la commande exacte d'activation selon l'OS (Windows / macOS / Linux).
- Crée requirements.txt avec : fastapi, uvicorn, scikit-learn, xgboost,
  lightgbm, shap, imbalanced-learn, pandas, numpy, mlflow, joblib,
  python-dotenv, httpx, fastmcp, pytest.
- Donne la commande d'installation.
Explique, puis attends ma validation.
```

---

## Étape 3 — Structure des dossiers (architecture 4 couches)

```
ÉTAPE 3 — Structure des dossiers.
Crée cette arborescence :
  churnguard/
    app/
      __init__.py
      main.py            (point d'entrée FastAPI)
      config.py          (config via variables d'env)
      ingestion/         (couche 1 : chargement + détection schéma)
      processing/        (couche 2 : nettoyage + feature engineering)
      modeling/          (entraînement + sélection modèle)
      explainability/    (SHAP)
      recommendations/   (Next Best Actions + règles JSON)
      api/               (routes FastAPI : predict, explain, recommend, what-if)
    mcp/
      mcp_server.py
    data/                (ignoré par git)
    models/              (ignoré par git)
    tests/
    .env.example
    requirements.txt
    README.md
    Dockerfile
Ajoute les __init__.py nécessaires et explique le rôle de chaque dossier.
Attends ma validation.
```

---

## Étape 4 — Récupération et exploration du dataset

```
ÉTAPE 4 — Récupération et exploration du dataset.
Dataset bancaire (~10k lignes) :
https://www.kaggle.com/datasets/saurabhbadole/bank-customer-churn-prediction-dataset
- Explique comment le télécharger (API Kaggle ET téléchargement manuel).
- Place-le dans data/.
- Écris un script exploratoire qui charge le CSV et affiche : dimensions,
  types de colonnes, valeurs manquantes, distribution de la cible (churn),
  aperçu statistique.
- Résume le contenu (colonnes, cible, déséquilibre éventuel).
Attends ma validation.
```

---

## Étape 5 — Couche 1 : Ingestion + détection de schéma

```
ÉTAPE 5 — Couche ingestion.
- Implémente un module d'ingestion acceptant CSV, Excel et Parquet avec
  détection automatique de l'encodage.
- Ajoute une fonction qui identifie la variable cible, les colonnes d'ID et
  les fuites de données potentielles (heuristiques simples pour l'instant ;
  on branchera un LLM plus tard).
Code commenté en français, type hints, docstrings. Attends ma validation.
```

---

## Étape 6 — Couche 2 : Nettoyage + feature engineering

```
ÉTAPE 6 — Couche processing.
- Nettoyage adaptatif (valeurs manquantes, outliers) avec pandas.
- Encodage des variables catégorielles avec scikit-learn.
- Application de SMOTE si les classes sont déséquilibrées.
Code commenté en français, type hints, docstrings. Attends ma validation.
```

---

## Étape 7 — Modélisation et sélection automatique

```
ÉTAPE 7 — Modélisation.
- Entraîne et compare plusieurs modèles : régression logistique, Random Forest,
  Gradient Boosting, XGBoost, LightGBM.
- Sélectionne le meilleur selon ROC-AUC / F1-score.
- Sauvegarde le meilleur modèle avec joblib et logue l'expérience dans MLflow.
Attends ma validation.
```

---

## Étape 8 — Explicabilité (SHAP)

```
ÉTAPE 8 — Explicabilité.
- Implémente la couche SHAP (TreeExplainer) pour expliquer chaque prédiction.
- Ajoute un fallback simple si SHAP échoue.
Code commenté en français, type hints, docstrings. Attends ma validation.
```

---

## Étape 9 — Moteur de recommandations (Next Best Actions)

```
ÉTAPE 9 — Recommandations.
- Crée un moteur de règles métier éditables dans un fichier JSON externalisé.
- Génère des actions de rétention priorisées selon le niveau de risque.
Attends ma validation.
```

---

## Étape 10 — API REST FastAPI

```
ÉTAPE 10 — API REST.
- Crée les endpoints : /predict, /explain, /recommend, /what-if.
- Documentation Swagger automatique.
- Gestion propre des erreurs + clé API simple via .env.
Attends ma validation.
```

---

## Étape 11 — Couche MCP

```
ÉTAPE 11 — Couche MCP.
- Crée mcp/mcp_server.py avec FastMCP exposant ces outils, chacun appelant
  l'API FastAPI existante :
  predict_churn, explain_prediction, recommend_actions,
  simulate_what_if, list_high_risk_clients.
- Donne les instructions pour lancer le serveur MCP et l'extrait de
  claude_desktop_config.json à ajouter pour le connecter à Claude Desktop.
Attends ma validation.
```

---

## Étape 12 — Tests, Docker et documentation

```
ÉTAPE 12 — Tests, Docker, documentation.
- Écris des tests unitaires pytest (couverture visée ≥ 60%).
- Crée un Dockerfile et un docker-compose.yml.
- Complète le README avec les instructions d'installation, de lancement
  et d'utilisation.
Attends ma validation.
```

---

## État d'avancement (au 6 juillet 2026)

- ✅ **Étapes 1 → 11** : terminées et commitées.
- 🚧 **Étape 12** : partielle — tests présents (couverture à vérifier),
  Dockerfile présent, **docker-compose.yml manquant**, README à compléter.
