FROM python:3.9-slim

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Installer numpy en premier pour s'assurer de la compatibilité
RUN pip install --no-cache-dir numpy==1.26.3

# Copier les fichiers de dépendances Python
COPY requirements.txt /app/

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY . /app/

# Créer les répertoires nécessaires
RUN mkdir -p /app/data /app/logs /app/embeddings_cache /app/conf

# Exposer le port de l'API
EXPOSE 8001

# Variables d'environnement par défaut
ENV MCP_APP_PORT=8001 \
    MCP_DISCOVERY_ENABLED=true \
    MCP_MANAGE_SERVERS=true \
    LOG_LEVEL=INFO \
    ALBERT_API_URL=https://albert.api.etalab.gouv.fr

# Commande pour démarrer l'application
# On passera la clé API Albert en variable d'environnement ou via docker-compose
ENTRYPOINT ["python", "start_mcp_registry.py"] 