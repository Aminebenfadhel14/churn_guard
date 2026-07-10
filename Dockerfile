# ============================================================
# Dockerfile ChurnGuard — version de base.
# Sera complété (multi-stage, docker-compose) à l'étape 12.
# ============================================================
FROM python:3.12-slim

# Évite les fichiers .pyc et force les logs non bufferisés
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Installer les dépendances en premier (cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copier le code applicatif
COPY . .

EXPOSE 8000

# Lancer l'API FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
