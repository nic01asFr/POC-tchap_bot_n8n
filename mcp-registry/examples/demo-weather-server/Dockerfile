FROM python:3.10-slim

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de requirements
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY app.py .

# Exposer le port
EXPOSE 8001

# Variables d'environnement
ENV MCP_SERVER_ID=demo_weather
ENV MCP_SERVER_NAME="Service Météo (Demo)"
ENV MCP_SERVER_DESCRIPTION="Service de démonstration pour obtenir la météo"

# Commande de démarrage
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"] 