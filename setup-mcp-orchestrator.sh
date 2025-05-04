#!/bin/bash

# Script pour configurer automatiquement le MCP Registry et l'orchestrateur

echo "Configuration du MCP Registry et de l'orchestrateur..."

# S'assurer que les répertoires nécessaires existent
mkdir -p mcp-registry/data/embeddings_cache
mkdir -p mcp-registry/conf

# Vérifier si le fichier .env existe, sinon en créer un
if [ ! -f .env ]; then
    echo "Création du fichier .env..."
    cat > .env << EOF
# Configuration Albert-Tchap
ALBERT_API_TOKEN=votre_token_api
ALBERT_API_URL=https://api.albert.exemple.fr
ALBERT_MODEL=mixtral-8x7b-instruct-v0.1

# Configuration Grist
GRIST_API_KEY=votre_cle_api_grist
GRIST_SERVER_URL=https://docs.grist.exemple.fr

# Configuration MCP Registry
MCP_AUTH_TOKEN=votre_token_mcp_registry
EOF
    echo "Fichier .env créé. Veuillez le modifier avec vos informations d'authentification."
    echo "IMPORTANT: Vous devez éditer ce fichier avant de continuer."
    exit 1
fi

# Vérifier si le réseau existe déjà, sinon le créer
if ! docker network inspect albert-tchap-network >/dev/null 2>&1; then
    echo "Création du réseau Docker albert-tchap-network..."
    docker network create albert-tchap-network
fi

# Construire et démarrer les services
echo "Démarrage des services avec Docker Compose..."
docker-compose up -d

echo ""
echo "Configuration terminée!"
echo ""
echo "Le MCP Registry est accessible à l'adresse: http://localhost:8001"
echo "Le serveur Grist MCP est accessible à l'adresse: http://localhost:8083"
echo "L'orchestrateur MCP est accessible à l'adresse: http://localhost:8002"
echo ""
echo "Pour vérifier que les outils MCP sont disponibles pour l'orchestrateur:"
echo "curl http://localhost:8001/tools"
echo "" 