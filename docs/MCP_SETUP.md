# Connexion de ChurnGuard MCP à Claude Desktop

Ce guide explique comment lancer le serveur MCP (`mcp/mcp_server.py`) et le
connecter à Claude Desktop.

> ⚠️ Le serveur MCP appelle l'API FastAPI de ChurnGuard. **L'API doit tourner**
> avant d'utiliser les outils MCP.

---

## 1. Démarrer l'API FastAPI (obligatoire)

Depuis la racine du projet, venv activé :

```powershell
# Windows
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

```bash
# macOS / Linux
source venv/bin/activate
python -m uvicorn app.main:app --reload
```

L'API écoute par défaut sur `http://127.0.0.1:8000`
(valeur `CHURNGUARD_API_BASE_URL`). Swagger : http://127.0.0.1:8000/docs

---

## 2. Tester le serveur MCP manuellement (optionnel)

```powershell
# Windows – depuis la racine du projet
.\venv\Scripts\python.exe mcp\mcp_server.py
```

```bash
# macOS / Linux
./venv/bin/python mcp/mcp_server.py
```

Le serveur communique via stdio (`mcp.run()`) : c'est normal qu'il « attende »
sans afficher grand-chose. C'est Claude Desktop qui le pilotera.

---

## 3. Config à ajouter dans `claude_desktop_config.json`

Emplacement du fichier :
- **Windows** : `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS** : `~/Library/Application Support/Claude/claude_desktop_config.json`

Ajoute (ou fusionne) le bloc `mcpServers` suivant. **Adapte les chemins absolus**
à ton installation.

### Windows

```json
{
  "mcpServers": {
    "churnguard": {
      "command": "C:\\Users\\MSI\\Desktop\\churn_guard\\venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\MSI\\Desktop\\churn_guard\\mcp\\mcp_server.py"
      ],
      "cwd": "C:\\Users\\MSI\\Desktop\\churn_guard",
      "env": {
        "PYTHONPATH": "C:\\Users\\MSI\\Desktop\\churn_guard",
        "CHURNGUARD_API_BASE_URL": "http://127.0.0.1:8000",
        "CHURNGUARD_API_KEY": "change-me-please"
      }
    }
  }
}
```

### macOS / Linux

```json
{
  "mcpServers": {
    "churnguard": {
      "command": "/chemin/vers/churn_guard/venv/bin/python",
      "args": [
        "/chemin/vers/churn_guard/mcp/mcp_server.py"
      ],
      "cwd": "/chemin/vers/churn_guard",
      "env": {
        "PYTHONPATH": "/chemin/vers/churn_guard",
        "CHURNGUARD_API_BASE_URL": "http://127.0.0.1:8000",
        "CHURNGUARD_API_KEY": "change-me-please"
      }
    }
  }
}
```

> 🔐 `CHURNGUARD_API_KEY` doit être **identique** à celle utilisée par l'API
> (définie dans ton fichier `.env`). Ne mets jamais la vraie clé dans un dépôt Git.
> `PYTHONPATH` pointe vers la racine pour que `from app.config import settings`
> fonctionne.

---

## 4. Redémarrer Claude Desktop

Ferme complètement puis rouvre Claude Desktop. Le serveur `churnguard`
apparaît dans les outils (icône 🔌 / marteau). Tu peux alors demander en
langage naturel, par exemple :

- « Prédis le churn de ce client : … »
- « Explique la prédiction pour ce client. »
- « Quelles actions de rétention recommandes-tu ? » (plan + email via `/recommend/enriched`)
- « Simule un what-if si on augmente son ancienneté. »
- « Liste les 10 clients les plus à risque. »
- « Donne-moi le résumé du dashboard ChurnGuard. »

Ces requêtes déclenchent respectivement les outils `predict_churn`,
`explain_prediction`, `recommend_actions`, `simulate_what_if`,
`list_high_risk_clients` et `get_dashboard_summary`.

---

## Dépannage

| Symptôme | Cause probable | Solution |
|----------|----------------|----------|
| « Impossible de se connecter à l'API » | API FastAPI non démarrée | Lancer `uvicorn app.main:app` |
| `ModuleNotFoundError: app` | `PYTHONPATH` / `cwd` incorrects | Vérifier les chemins absolus du bloc JSON |
| Serveur MCP absent dans Claude | JSON invalide ou app non redémarrée | Valider le JSON, redémarrer Claude Desktop |
| 401 / clé refusée | Clés API différentes | Aligner `CHURNGUARD_API_KEY` avec le `.env` de l'API |
