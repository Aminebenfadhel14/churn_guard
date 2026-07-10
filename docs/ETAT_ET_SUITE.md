# ChurnGuard — État du projet & étapes restantes (passation)

Document de passation pour continuer le développement. Il décrit l'état actuel,
ce qui a été fait récemment, les points d'attention, et ce qu'il reste à faire.

---

## 1. Vue d'ensemble

**ChurnGuard** : plateforme universelle de prédiction et d'explication de
l'attrition client (churn), applicable à tout dataset tabulaire de
**classification binaire** (cible oui/non).

**Stack :**
- Backend : Python 3.11, **FastAPI**, scikit-learn, XGBoost, LightGBM, SHAP,
  imbalanced-learn (SMOTE), pandas, MLflow, joblib.
- Frontend : **Next.js 16** (Turbopack, React, TypeScript, Tailwind, base-ui),
  généré via v0 puis branché au backend.
- Couche **MCP** (FastMCP) connectée à Claude Desktop.

**Lancement (2 serveurs en même temps) :**
- API : `.\venv\Scripts\python.exe -m uvicorn app.main:app --reload` (port 8000)
- Frontend : `cd frontend && npm run dev` (port 3000)
- Ou double-clic sur **`start.bat`** (lance les deux).

**Arborescence principale :**
```
app/           # backend FastAPI
  ingestion/   # chargement + détection de schéma (cible, IDs, fuites)
  processing/  # nettoyage, features, SMOTE, preprocessing
  modeling/    # entraînement multi-modèles, sélection, registry versionné
  explainability/  # SHAP
  recommendations/ # IA experte (Groq) + repli minimal si LLM indisponible
  api/         # routes FastAPI (routes.py, schema_service.py, training_state.py)
mcp/           # serveur MCP (mcp_server.py)
frontend/      # app Next.js
data/          # datasets (ignoré par git)
models/        # modèle actif + registry (ignoré par git)
tests/         # pytest
```

---

## 2. Ce qui FONCTIONNE aujourd'hui (branché au vrai backend)

- **Upload** (`/upload`) : dépose un dataset, détecte le schéma. **N'entraîne
  plus automatiquement** — l'entraînement est déclenché par un bouton.
- **Entraînement manuel** : bouton « Lancer l'entraînement » → `POST /train/start`
  (entraînement en **arrière-plan**, non bloquant) + suivi via `GET /train/status`.
- **Prédire** (`/schema` + `/predict`) : formulaire auto-généré selon le dataset,
  score en temps réel. + **alerte email en brouillon** (voir §3).
- **Clients** (`GET /clients`) : liste **dynamique** de toutes les lignes du
  dataset actif scorées, avec pagination, filtre par risque, recherche, export CSV.
- **Dashboard** (`GET /dashboard`) : **dynamique** — KPI, répartition par niveau
  de risque, histogramme des scores, top-10 clients réels.
- **MCP** : 5 outils (`predict_churn`, `explain_prediction`, `recommend_actions`,
  `simulate_what_if`, `list_high_risk_clients`) connectés à Claude Desktop.

---

## 3. Travaux réalisés récemment (contexte pour comprendre le code)

- **Entraînement plus rapide et robuste** (`app/modeling/train.py`,
  `app/modeling/models.py`) : parallélisme borné (évite un crash mémoire),
  jeu de modèles « rapide » par défaut (LogReg, RandomForest, HistGB, XGBoost,
  LightGBM), validation croisée à **3 folds**. Passer `rapide=False` à
  `modeles_disponibles()` pour le catalogue complet.
- **Upload robuste** (`app/api/routes.py`, fonction `_ecrire_dataset`) : gère le
  cas Windows où le fichier est verrouillé/lecture seule (Excel) — retire
  l'attribut lecture seule, sinon écrit sous un nom horodaté.
- **CORS** ouvert à toutes les origines en dev (`app/main.py`,
  `allow_origins=["*"]`, `allow_credentials=False`).
- **Écriture atomique du modèle** (`app/modeling/registry.py`,
  `_remplacer_atomique`) : écrit dans un `.tmp` puis `os.replace` → plus de
  `schema.json` tronqué même si l'entraînement est interrompu.
- **Sélection du bon dataset** (`app/api/routes.py`, `_dataset_du_modele_actif`) :
  `/clients` et `/dashboard` scorent le dataset **compatible avec le modèle actif**
  (colonnes attendues), pas simplement « le dernier fichier uploadé ».
- **Frontend** : page Clients et Dashboard réécrites en mode générique (fetch du
  backend). Bug d'hydratation du header corrigé (base-ui ne gère pas `asChild` :
  ne jamais mettre `asChild` sur `Button`/`DropdownMenuTrigger` — styler
  directement ou utiliser `buttonVariants`). Nom du profil = **Medamine Ben Fadhel**.
- **Alerte email — brouillon uniquement** (`frontend/app/predict/page.tsx`) :
  si risque **élevé**, bouton « Préparer l'alerte » → génère objet + corps
  (score + caractéristiques + actions de `/recommend`), avec « Copier » et
  « Ouvrir dans ma messagerie » (mailto). **Aucun envoi automatique, pas de BDD.**
  L'envoi réel (Nodemailer) a été volontairement laissé de côté.

---

## 4. Points d'attention / pièges connus

1. **Deux serveurs doivent tourner en même temps** (API + frontend), sinon le
   navigateur affiche « API injoignable ». Utiliser `start.bat`.
2. **Ne pas laisser le CSV ouvert dans Excel** pendant l'upload (verrou Windows).
3. **Après avoir changé de dataset**, il faut **ré-entraîner** (bouton) pour que
   le modèle actif et les pages Clients/Dashboard correspondent.
4. **Le fichier `WA_Fn-UseC_-Telco-...-selected-columns.csv` est incomplet**
   (colonne cible `Churn` absente) → utiliser la version complète 21 colonnes.
5. **La cible doit être binaire** (2 classes). Multi-classes / régression non
   supportés en l'état.

---

## 5. ÉTAPES RESTANTES (à faire)

### A. Réparer l'état du modèle (prioritaire)
Le `models/schema.json` a été corrompu par un entraînement interrompu. La cause
est corrigée (écriture atomique), mais il faut **régénérer** un modèle propre :
→ Upload de `Churn_Modelling.csv` → **« Lancer l'entraînement »**. Vérifier
ensuite que `/predict`, `/clients`, `/dashboard` répondent sans erreur.

### B. Vérifier la compilation backend côté Windows
```powershell
.\venv\Scripts\python.exe -m py_compile app\api\routes.py app\modeling\registry.py
```
(rien affiché = OK)

### C. Rendre dynamiques les pages encore en données factices
Fichier `frontend/lib/api.ts` = **couche mock**. Restent en mock :
- **Détail client** (`frontend/app/clients/[id]/...`) + onglets **Explain /
  Recommend / What-if** de cette page.
- Brancher au vrai backend : `/explain`, `/recommend`, `/what-if` existent déjà
  côté API. Idée : sur la page Clients, rendre les lignes cliquables vers un
  détail qui appelle ces endpoints (mais un dataset générique n'a pas forcément
  d'« ID client » stable — prévoir un mode générique).

### D. (Optionnel) Envoi réel de l'alerte email
Ajouter Nodemailer via une route API Next.js (`app/api/notify/route.ts`),
credentials Gmail (mot de passe d'application) dans `.env.local`. Décidé « pas
maintenant ». Aucune base de données nécessaire.

### E. Finaliser l'ÉTAPE 12 du plan initial
- **Tests pytest** (viser ≥ 60 % de couverture). Fichiers existants :
  `tests/test_api.py`, `tests/test_explainability.py`, `tests/test_recommendations.py`.
  Ajouter des tests pour `/clients`, `/dashboard`, `/train/start`, `_ecrire_dataset`,
  `_dataset_du_modele_actif`, écriture atomique du registry.
- **docker-compose.yml** (n'existe pas encore ; `Dockerfile` existe).
- **README** : compléter installation, lancement (start.bat), usage, datasets de
  démo, connexion MCP (voir `MCP_SETUP.md`).

### F. Commit Git (important)
Beaucoup de changements ne sont **pas encore commités**. Committer par lots avec
des messages clairs, ex. :
- `feat: entrainement manuel + endpoint /train/start asynchrone`
- `fix: upload robuste (fichier verrouille) + ecriture atomique du modele`
- `feat: page Clients dynamique (GET /clients)`
- `feat: dashboard dynamique (GET /dashboard) + histogramme`
- `feat: alerte email en brouillon sur la page Predire`
- `fix: CORS + bug hydratation header (asChild base-ui)`

---

## 6. Endpoints backend disponibles (référence)

- `GET  /health` — sonde de vivacité
- `GET  /schema` — schéma du modèle actif (pour le formulaire Prédire)
- `POST /predict` — prédiction sur un client saisi
- `POST /explain` — explication SHAP
- `POST /recommend` — actions de rétention
- `POST /what-if` — simulation de variables
- `GET  /clients` — liste paginée scorée (limit, offset, risk, q)
- `GET  /clients/high-risk` — top-N clients à risque
- `GET  /dashboard` — agrégats du tableau de bord
- `POST /upload` — dépose un dataset (auto_train=false par défaut)
- `GET  /train/status` — état de l'entraînement en cours/dernier
- `POST /train/start` — lance l'entraînement en arrière-plan
- `POST /train` — entraînement synchrone (ancien, gardé)

Sécurité : clé API optionnelle via en-tête `x-api-key` (désactivée si la clé
`.env` vaut la valeur par défaut `change-me-please`).
