# Base de connaissances - Playbooks de rétention (RAG)

Ce dossier alimente l'Assistant IA de ChurnGuard (RAG). Chaque fichier Markdown
est un *playbook* : un guide d'actions de rétention. L'Assistant y récupère les
extraits pertinents pour appuyer ses recommandations sur des bonnes pratiques,
et non seulement sur les facteurs bruts du modèle.

## Organisation

- `facteurs/`  : playbooks par **facteur de risque** (universel, valable pour
  n'importe quel dataset : banque, RH, télécom, assurance, e-commerce...).
- `secteurs/`  : exemples d'application par secteur.
- `general/`   : principes transverses de rétention.

## Ajouter de la connaissance

Dépose un fichier `.md`, `.txt` (ou `.pdf`) dans un de ces sous-dossiers, puis
relance l'indexation (endpoint `POST /rag/reindex` ou redémarrage de l'API).
Aucune modification de code n'est nécessaire : le RAG prend les nouveaux
documents automatiquement. Le corpus est donc extensible pour tout nouveau
dataset importé.
