# Intégration du Model Context Protocol (MCP) dans Albert

Ce document explique comment utiliser les fonctionnalités du Model Context Protocol (MCP) dans Albert.

## Qu'est-ce que le Model Context Protocol (MCP) ?

Le Model Context Protocol (MCP) est un protocole développé par Anthropic qui standardise la manière dont les grands modèles de langage (LLMs) interagissent avec des outils externes. Il permet à un LLM d'accéder à des données et des services externes de façon structurée et sécurisée.

Albert intègre le support du MCP via le service MCP Registry, qui permet de découvrir et d'utiliser les outils disponibles sur différents serveurs MCP.

## Architecture

L'intégration MCP dans Albert se compose de deux parties principales :

1. **MCP Registry Service** : Un microservice indépendant qui :
   - Découvre et gère les serveurs MCP
   - Indexe les outils disponibles avec FAISS pour une recherche sémantique efficace
   - Expose une API pour rechercher et exécuter les outils

2. **Commandes Albert MCP** : Module dans Albert qui communique avec le MCP Registry pour :
   - Lister les serveurs et outils disponibles
   - Exécuter des outils
   - Suggérer automatiquement des outils pertinents

## Configuration de l'intégration MCP

### Configuration du MCP Registry Service

Le service MCP Registry utilise un fichier de configuration YAML. Exemple :

```yaml
# conf/config.yaml
app:
  name: "MCP Registry Service"
  version: "1.0.0"
  host: "0.0.0.0"
  port: 8000

registry:
  discovery_interval: 3600  # Intervalle de mise à jour en secondes
  discovery_enabled: true   # Activer la découverte automatique

# Configuration des serveurs MCP
servers:
  - id: "demo_weather"
    name: "Service Météo"
    description: "Fournit des informations météorologiques"
    url: "http://weather-server:8080"
    
  - id: "demo_docs"
    name: "Documentation"
    description: "Recherche dans la documentation"
    url: "http://docs-server:8080"
```

### Configuration d'Albert

Pour utiliser les fonctionnalités MCP dans Albert, ajoutez les paramètres suivants dans votre fichier `.env` :

```
# Configuration MCP Registry
mcp_registry_url=http://mcp-registry:8000
mcp_auth_token=votre-token-d-authentification
mcp_suggest_enabled=true
```

- `mcp_registry_url` : URL complète du service MCP Registry
- `mcp_auth_token` : Token d'authentification (si nécessaire)
- `mcp_suggest_enabled` : Active les suggestions automatiques d'outils

## Déploiement du MCP Registry Service

### Avec Docker

```bash
cd mcp-registry
docker build -t mcp-registry .
docker run -p 8000:8000 -v $(pwd)/conf:/app/conf mcp-registry
```

### Sans Docker

```bash
cd mcp-registry
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Commandes MCP disponibles dans Albert

Albert propose trois commandes principales pour interagir avec les outils MCP :

### `!mcp-servers`

Liste tous les serveurs MCP configurés dans le Registry.

Exemple :
```
!mcp-servers
```

### `!mcp-tools [search terme] [server_id] [refresh]`

Liste tous les outils disponibles ou effectue une recherche.

Options :
- `search terme` : Recherche sémantique des outils contenant le terme spécifié
- `server_id` : Liste uniquement les outils d'un serveur spécifique
- `refresh` : Force le rafraîchissement du cache des outils

Exemples :
```
!mcp-tools
!mcp-tools search météo
!mcp-tools demo_weather
!mcp-tools refresh
```

### `!mcp-run <server_id> <nom_outil> [paramètres]`

Exécute un outil MCP spécifique avec les paramètres fournis.

Format des paramètres : `nom=valeur` ou `nom="valeur avec espaces"`

Exemples :
```
!mcp-run demo_weather get_weather ville="Paris"
!mcp-run demo_docs search query="intelligence artificielle"
```

## Suggestions automatiques d'outils

Si activé (`mcp_suggest_enabled=true`), Albert peut suggérer automatiquement des outils MCP pertinents en fonction des messages de l'utilisateur en conversation privée.

## Développement d'un serveur MCP

Pour développer votre propre serveur MCP compatible avec le Registry, consultez la documentation officielle du protocole MCP sur [GitHub](https://github.com/modelcontextprotocol/docs).

Un serveur MCP standard doit exposer au minimum les endpoints suivants :
- `/schema` : Retourne le schéma des outils disponibles
- `/run` : Permet d'exécuter un outil avec des paramètres

Le schéma doit respecter le format défini par le protocole MCP. 