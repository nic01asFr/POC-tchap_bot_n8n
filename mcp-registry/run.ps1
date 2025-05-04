# Script de démarrage du service MCP Registry (Windows)
Write-Host "Démarrage du service MCP Registry..."

# Vérifier si l'environnement virtuel existe
if (-not (Test-Path -Path "venv")) {
    Write-Host "L'environnement virtuel n'existe pas. Exécutez d'abord install.ps1."
    exit 1
}

# Activer l'environnement virtuel
Write-Host "Activation de l'environnement virtuel..."
& .\venv\Scripts\Activate.ps1

# Vérifier si le répertoire de configuration existe
if (-not (Test-Path -Path "conf")) {
    Write-Host "Le répertoire de configuration n'existe pas. Exécutez d'abord install.ps1."
    exit 1
}

# Créer le répertoire de cache pour les embeddings s'il n'existe pas
if (-not (Test-Path -Path ".cache\embeddings")) {
    Write-Host "Création du répertoire de cache pour les embeddings..."
    New-Item -ItemType Directory -Path ".cache\embeddings" -Force | Out-Null
}

# Démarrer le service
Write-Host "Démarrage du service..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload 