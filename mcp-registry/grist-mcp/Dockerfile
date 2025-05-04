FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de dépendances
COPY requirements.txt /app/

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY grist_mcp_server.py /app/

# Créer un fichier .env vide - les variables seront fournies par Docker
RUN touch /app/.env

# Exposer le port pour le serveur MCP
EXPOSE 8083

# Point d'entrée
CMD ["python", "grist_mcp_server.py"] 