FROM python:3.10-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Installation de Poetry
RUN pip install --no-cache-dir poetry

# Configuration de Poetry pour ne pas créer d'environnement virtuel dans Docker
RUN poetry config virtualenvs.create false

# Copie des fichiers de dépendances
COPY pyproject.toml poetry.lock* ./

# Installation des dépendances
RUN poetry install --without dev --no-interaction --no-ansi --no-root

# Copie du code source
COPY . .

# Exposer le port pour l'API
EXPOSE 8000

# Commande de démarrage
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"] 