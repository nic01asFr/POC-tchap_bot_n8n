# Guide d'installation du MCP Registry pour Tchapbot Albert

Ce guide vous explique comment installer et configurer le MCP Registry pour l'intégration avec un Tchapbot Albert.

## Prérequis

- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)
- Git

## 1. Cloner le dépôt

```powershell
git clone https://github.com/votre-organisation/albert-tchap-mcp.git
cd albert-tchap-mcp
```

## 2. Installer les dépendances

```powershell
pip install -r requirements.txt
```

## 3. Configuration du MCP Registry

### Créer le répertoire de configuration

```powershell
mkdir -p mcp-registry/conf
```

### Créer le fichier de configuration des serveurs MCP

Créez un fichier `mcp-registry/conf/mcp_servers.json` avec le contenu suivant:

```json
{
  "grist-mcp": {
    "command": "python",
    "args": [
      "scripts/grist_mcp_server.py"
    ],
    "url": "http://localhost:5000/",
    "env": {
      "GRIST_API_KEY": "votre_clé_api_grist",
      "GRIST_SERVER_URL": "https://docs.getgrist.com"
    }
  },
  "filesystem-mcp": {
    "command": "python",
    "args": [
      "scripts/filesystem_mcp_server.py"
    ],
    "url": "http://localhost:5001/"
  }
}
```

Remplacez `votre_clé_api_grist` par votre véritable clé API Grist.

### Créer le fichier de configuration générale

Créez un fichier `mcp-registry/conf/config.yaml` avec le contenu suivant:

```yaml
app:
  name: "MCP Registry"
  version: "1.0.0"
  port: 8000
  log_level: "INFO"

registry:
  discovery_interval: 300  # en secondes
  manage_servers: true
  server_urls:
    - "http://localhost:5000/"
    - "http://localhost:5001/"
```

## 4. Créer le script de démarrage

Créez un fichier `start_mcp_registry.py` à la racine du projet:

```python
#!/usr/bin/env python
import asyncio
import os
import sys
import logging
from pathlib import Path

# Ajouter le répertoire courant au path pour l'importation des modules
sys.path.insert(0, str(Path(__file__).parent))

from mcp_registry.app.core.registry import MCPRegistry
from mcp_registry.app.config.settings import load_settings

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mcp_registry.log")
    ]
)

logger = logging.getLogger("mcp_registry")

async def main():
    logger.info("Démarrage du MCP Registry...")
    
    # Charger les paramètres
    settings = load_settings()
    logger.info(f"Configuration chargée: {settings}")
    
    # Initialiser le registry
    registry = MCPRegistry(settings=settings)
    
    try:
        # Démarrer le registry
        await registry.start()
        logger.info("MCP Registry démarré avec succès")
        
        # Maintenir le processus actif
        while True:
            await asyncio.sleep(60)
            logger.debug("MCP Registry en cours d'exécution...")
            
    except KeyboardInterrupt:
        logger.info("Arrêt du MCP Registry demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du MCP Registry: {e}", exc_info=True)
    finally:
        # Arrêter proprement le registry
        logger.info("Arrêt du MCP Registry...")
        await registry.stop()
        logger.info("MCP Registry arrêté")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nArrêt du MCP Registry")
```

## 5. Obtenir une clé API Grist

1. Connectez-vous à votre compte Grist à l'adresse https://docs.getgrist.com
2. Allez dans les paramètres de votre profil
3. Accédez à la section "API Keys"
4. Créez une nouvelle clé API
5. Copiez la clé générée et utilisez-la dans la configuration

## 6. Démarrer le MCP Registry

```powershell
python start_mcp_registry.py
```

Vous devriez voir des logs indiquant que le MCP Registry démarre et découvre les serveurs MCP configurés.

## 7. Vérifier l'installation

Pour vérifier que le MCP Registry fonctionne correctement:

1. Le fichier de log `mcp_registry.log` doit montrer des messages de démarrage réussi
2. Les serveurs MCP configurés doivent être démarrés automatiquement
3. Les outils disponibles doivent être découverts et indexés

## 8. Intégration avec le Tchapbot Albert

Pour intégrer le MCP Registry avec votre Tchapbot Albert:

1. Assurez-vous que le MCP Registry est en cours d'exécution
2. Configurez votre Tchapbot pour utiliser le MCPCommandHandler comme décrit dans la documentation
3. Démarrez votre Tchapbot

## Résolution des problèmes courants

### Le MCP Registry ne démarre pas

- Vérifiez que toutes les dépendances sont installées
- Vérifiez les permissions sur les fichiers de configuration
- Consultez les logs pour identifier les erreurs spécifiques

### Les serveurs MCP ne sont pas découverts

- Vérifiez que les URLs dans `config.yaml` sont correctes
- Assurez-vous que les serveurs MCP sont accessibles aux URLs spécifiées
- Vérifiez que le pare-feu n'empêche pas les connexions

### Erreurs d'authentification avec Grist

- Vérifiez que la clé API Grist est valide
- Assurez-vous que la clé API a les permissions nécessaires
- Vérifiez que l'URL du serveur Grist est correcte

## Serveurs MCP additionnels

Pour ajouter d'autres serveurs MCP (GitHub, n8n, etc.):

1. Obtenez les scripts serveur MCP correspondants
2. Ajoutez-les au répertoire `scripts/`
3. Configurez-les dans `mcp_servers.json`
4. Ajoutez leurs URLs dans `config.yaml`
5. Redémarrez le MCP Registry

## Mode développement

Pour exécuter le MCP Registry en mode développement avec plus de logs:

```powershell
$env:LOG_LEVEL="DEBUG"; python start_mcp_registry.py
```

Cela affichera des logs plus détaillés pour faciliter le débogage. 