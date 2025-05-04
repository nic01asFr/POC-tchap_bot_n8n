# Script d'installation pour le service MCP Registry (Windows)
Write-Host "Installation du service MCP Registry..."

# Vérifier si Python 3.10+ est installé
try {
    $pythonVersion = (python --version 2>&1) -replace "Python "
    $pythonMajor = [int]($pythonVersion -split '\.')[0]
    $pythonMinor = [int]($pythonVersion -split '\.')[1]

    if ($pythonMajor -lt 3 -or ($pythonMajor -eq 3 -and $pythonMinor -lt 10)) {
        Write-Host "Erreur: Python 3.10 ou supérieur est requis."
        Write-Host "Version actuelle: $pythonVersion"
        exit 1
    }
} catch {
    Write-Host "Erreur: Python n'est pas installé ou n'est pas accessible."
    exit 1
}

# Créer un environnement virtuel si nécessaire
if (-not (Test-Path -Path "venv")) {
    Write-Host "Création de l'environnement virtuel..."
    python -m venv venv
}

# Activer l'environnement virtuel
Write-Host "Activation de l'environnement virtuel..."
& .\venv\Scripts\Activate.ps1

# Installer les dépendances
Write-Host "Installation des dépendances..."
pip install -r requirements.txt

# Créer le répertoire de configuration
if (-not (Test-Path -Path "conf")) {
    Write-Host "Création du répertoire de configuration..."
    New-Item -ItemType Directory -Path "conf" | Out-Null
}

# Créer le fichier de configuration par défaut s'il n'existe pas
if (-not (Test-Path -Path "conf\config.yaml")) {
    Write-Host "Création du fichier de configuration par défaut..."
    @"
app:
  name: "MCP Registry Service"
  version: "1.0.0"
  host: "0.0.0.0"
  port: 8000

embedding:
  cache_dir: ".cache/embeddings"
  model: "all-MiniLM-L6-v2"
  model_source: "sentence-transformers"

registry:
  discovery_interval: 3600
  discovery_enabled: true
  cache_ttl: 86400

servers:
  - id: "demo_weather"
    name: "Service Météo"
    description: "Fournit des informations météorologiques"
    url: "http://localhost:8001"
"@ | Out-File -FilePath "conf\config.yaml" -Encoding utf8
}

# Créer le répertoire de cache pour les embeddings
if (-not (Test-Path -Path ".cache\embeddings")) {
    New-Item -ItemType Directory -Path ".cache\embeddings" -Force | Out-Null
}

Write-Host "Installation terminée."
Write-Host ""
Write-Host "Pour démarrer le service:"
Write-Host "------------------------"
Write-Host ".\venv\Scripts\Activate.ps1"
Write-Host "uvicorn app.main:app --host 0.0.0.0 --port 8000"
Write-Host ""
Write-Host "Ou avec Docker:"
Write-Host "------------------------"
Write-Host "docker build -t mcp-registry ."
Write-Host "docker run -p 8000:8000 -v ${PWD}/conf:/app/conf mcp-registry" 