# MCP Registry pour Albert-Tchap

Ce dépôt contient l'infrastructure nécessaire pour intégrer le Model Context Protocol (MCP) dans Albert-Tchap, permettant l'utilisation d'outils variés comme Grist via une interface standardisée.

## Architecture

![Architecture MCP](docs/mcp-architecture.png)

L'architecture se compose de trois composants principaux :
1. **MCP Registry** - Service central qui découvre et indexe les outils MCP
2. **Serveurs MCP** - Fournisseurs d'outils (Grist, etc.)
3. **MCP Orchestrator** - Consommateur qui utilise les outils via le Registry

## Installation rapide

### Prérequis
- Docker et Docker Compose
- PowerShell (Windows) ou Bash (Linux/Mac)

### Installation automatique

Windows:
```powershell
.\setup-mcp-orchestrator.ps1
```

Linux/Mac:
```bash
./setup-mcp-orchestrator.sh
```

Le script effectue automatiquement les actions suivantes :
1. Crée les répertoires nécessaires
2. Génère un fichier `.env` si non existant
3. Crée le réseau Docker `albert-tchap-network`
4. Démarre tous les services avec `docker-compose`

### Installation manuelle

1. Créez un fichier `.env` contenant vos informations d'authentification
   ```
   ALBERT_API_TOKEN=votre_token_api
   ALBERT_API_URL=https://api.albert.exemple.fr
   ALBERT_MODEL=mixtral-8x7b-instruct-v0.1
   GRIST_API_KEY=votre_cle_api_grist
   GRIST_SERVER_URL=https://docs.grist.exemple.fr
   ```

2. Créez le réseau Docker
   ```
   docker network create albert-tchap-network
   ```

3. Démarrez l'infrastructure
   ```
   docker-compose up -d
   ```

## Services disponibles

| Service | URL | Description |
|---------|-----|-------------|
| MCP Registry | http://localhost:8001 | Registre central pour tous les outils MCP |
| Grist MCP | http://localhost:8083 | Serveur MCP pour Grist |
| MCP Orchestrator | http://localhost:8002 | Orchestrateur qui utilise les outils MCP |

## Vérification

Pour vérifier que les outils MCP sont disponibles:

Windows:
```powershell
Invoke-RestMethod -Uri "http://localhost:8001/tools"
```

Linux/Mac:
```bash
curl http://localhost:8001/tools
```

## Utilisation avec l'orchestrateur

L'orchestrateur est configuré pour utiliser automatiquement le MCP Registry. Les outils Grist sont accessibles via les endpoints suivants :

- **API orchestrateur**: `http://localhost:8002/api/tools/grist`
- **Interface utilisateur**: `http://localhost:8002/ui`

## Dépannage

1. **Les services ne démarrent pas**
   - Vérifiez que Docker est en cours d'exécution
   - Vérifiez que les ports 8001, 8002 et 8083 ne sont pas déjà utilisés

2. **Les outils Grist ne sont pas disponibles**
   - Vérifiez votre `GRIST_API_KEY` et `GRIST_SERVER_URL` dans `.env`
   - Vérifiez les logs du conteneur Grist MCP: `docker logs albert-tchap-grist-mcp`

3. **L'orchestrateur ne trouve pas les outils**
   - Vérifiez que le MCP Registry est accessible: `curl http://localhost:8001/health`
   - Vérifiez les logs du registry: `docker logs albert-tchap-mcp-registry` 