#!/bin/bash

# Script de démarrage du service MCP Registry
echo "Démarrage du service MCP Registry..."

# Vérifier si l'environnement virtuel existe
if [ ! -d "venv" ]; then
    echo "L'environnement virtuel n'existe pas. Exécutez d'abord install.sh."
    exit 1
fi

# Activer l'environnement virtuel
source venv/bin/activate

# Vérifier si le répertoire de configuration existe
if [ ! -d "conf" ]; then
    echo "Le répertoire de configuration n'existe pas. Exécutez d'abord install.sh."
    exit 1
fi

# Créer le répertoire de cache pour les embeddings s'il n'existe pas
mkdir -p .cache/embeddings

# Démarrer le service
echo "Démarrage du service..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload 