# Script PowerShell pour configurer automatiquement le MCP Registry et l'orchestrateur

Write-Host "Configuration du MCP Registry et de l'orchestrateur..."

# S'assurer que les répertoires nécessaires existent
New-Item -Path "mcp-registry/data/embeddings_cache" -ItemType Directory -Force | Out-Null
New-Item -Path "mcp-registry/conf" -ItemType Directory -Force | Out-Null

# Vérifier si le fichier .env existe, sinon en créer un
if (-not (Test-Path ".env")) {
    Write-Host "Création du fichier .env..."
    @"
# Configuration Albert-Tchap
ALBERT_API_TOKEN=votre_token_api
ALBERT_API_URL=https://api.albert.exemple.fr
ALBERT_MODEL=mixtral-8x7b-instruct-v0.1

# Configuration Grist
GRIST_API_KEY=votre_cle_api_grist
GRIST_SERVER_URL=https://docs.grist.exemple.fr

# Configuration MCP Registry
MCP_AUTH_TOKEN=votre_token_mcp_registry
"@ | Out-File -FilePath ".env" -Encoding utf8

    Write-Host "Fichier .env créé. Veuillez le modifier avec vos informations d'authentification."
    Write-Host "IMPORTANT: Vous devez éditer ce fichier avant de continuer."
    exit 1
}

# Vérifier si le réseau existe déjà, sinon le créer
$networkExists = docker network ls | Select-String -Pattern "albert-tchap-network"
if (-not $networkExists) {
    Write-Host "Création du réseau Docker albert-tchap-network..."
    docker network create albert-tchap-network
}

# Construire et démarrer les services
Write-Host "Démarrage des services avec Docker Compose..."
docker-compose up -d

Write-Host ""
Write-Host "Configuration terminée!"
Write-Host ""
Write-Host "Le MCP Registry est accessible à l'adresse: http://localhost:8001"
Write-Host "Le serveur Grist MCP est accessible à l'adresse: http://localhost:8083"
Write-Host "L'orchestrateur MCP est accessible à l'adresse: http://localhost:8002"
Write-Host ""
Write-Host "Pour vérifier que les outils MCP sont disponibles pour l'orchestrateur:"
Write-Host "Invoke-RestMethod -Uri 'http://localhost:8001/tools'"
Write-Host "" 