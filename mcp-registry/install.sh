#!/bin/bash

# Script d'installation pour le service MCP Registry
echo "Installation du service MCP Registry..."

# Vérifier si Python 3.10+ est installé
python_version=$(python3 --version 2>&1 | awk '{print $2}')
python_major=$(echo $python_version | cut -d. -f1)
python_minor=$(echo $python_version | cut -d. -f2)

if [ "$python_major" -lt 3 ] || ([ "$python_major" -eq 3 ] && [ "$python_minor" -lt 10 ]); then
    echo "Erreur: Python 3.10 ou supérieur est requis."
    echo "Version actuelle: $python_version"
    exit 1
fi

# Créer un environnement virtuel si nécessaire
if [ ! -d "venv" ]; then
    echo "Création de l'environnement virtuel..."
    python3 -m venv venv
fi

# Activer l'environnement virtuel
source venv/bin/activate

# Installer les dépendances
echo "Installation des dépendances..."
pip install -r requirements.txt

# Créer le répertoire de configuration
if [ ! -d "conf" ]; then
    echo "Création du répertoire de configuration..."
    mkdir -p conf
fi

# Créer le fichier de configuration par défaut s'il n'existe pas
if [ ! -f "conf/config.yaml" ]; then
    echo "Création du fichier de configuration par défaut..."
    cat > conf/config.yaml << EOL
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
EOL
fi

# Créer le répertoire de cache pour les embeddings
mkdir -p .cache/embeddings

echo "Installation terminée."
echo ""
echo "Pour démarrer le service:"
echo "------------------------"
echo "source venv/bin/activate"
echo "uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "Ou avec Docker:"
echo "------------------------"
echo "docker build -t mcp-registry ."
echo "docker run -p 8000:8000 -v \$(pwd)/conf:/app/conf mcp-registry" 