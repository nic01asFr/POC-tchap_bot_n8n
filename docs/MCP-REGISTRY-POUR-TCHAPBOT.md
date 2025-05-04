# Documentation Technique: MCP Registry pour Albert Bot

## Architecture générale

L'architecture MCP (Model Control Protocol) permet à un chatbot Albert d'interagir avec divers services externes via un système standardisé. Cette documentation décrit l'implémentation d'un registre MCP (MCP Registry) qui sert d'intermédiaire entre Albert et n'importe quel serveur MCP.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Albert Bot │────▶│ MCP Registry │────▶│ Serveurs MCP    │
└─────────────┘     └──────────────┘     │ (Grist, GitHub, │
                                         │  Filesystem,    │
                                         │  n8n, etc.)     │
                                         └─────────────────┘
```

## Composants essentiels

### 1. MCP Registry

Le MCP Registry est le composant central qui:
- Découvre et gère les serveurs MCP
- Indexe les outils disponibles sur chaque serveur
- Permet la recherche sémantique d'outils
- Facilite l'exécution des outils par Albert

**Localisation**: `/mcp-registry/`

### 2. MCP Client

Permet la communication entre le Registry et les serveurs MCP via HTTP.

**Localisation**: `/mcp-registry/app/core/mcp_client.py`

### 3. Gestionnaire de serveurs

Gère le cycle de vie des serveurs MCP (démarrage, arrêt, surveillance).

**Localisation**: `/mcp-registry/app/core/server_manager.py`

### 4. Indexation vectorielle

Permet la recherche sémantique des outils MCP basée sur leurs descriptions.

**Localisation**: `/mcp-registry/app/core/vector_store.py`

## Scripts indispensables

| Script | Localisation | Description |
|--------|--------------|-------------|
| `start_mcp_registry.py` | `/mcp-registry/` | Script principal pour démarrer le MCP Registry |
| `mcp_client.py` | `/mcp-registry/app/core/` | Client HTTP pour les serveurs MCP |
| `registry.py` | `/mcp-registry/app/core/` | Classe principale du registre MCP |
| `server_manager.py` | `/mcp-registry/app/core/` | Gestionnaire des serveurs MCP |
| `vector_store.py` | `/mcp-registry/app/core/` | Indexation vectorielle pour la recherche |
| `settings.py` | `/mcp-registry/app/config/` | Configuration du MCP Registry |
| `mcp_servers.json` | `/mcp-registry/conf/` | Configuration des serveurs MCP |
| `config.yaml` | `/mcp-registry/conf/` | Configuration générale du Registry |

## Flux d'interactions détaillé

### 1. Démarrage et découverte

```
┌─────────────────┐     ┌─────────────────┐     ┌───────────────────┐     ┌────────────────┐
│ start_mcp_      │────▶│ MCPRegistry     │────▶│ MCPServerManager  │────▶│ Serveurs MCP   │
│ registry.py     │     │ .start()        │     │ .start_servers()  │     │ démarrés       │
└─────────────────┘     └─────────────────┘     └───────────────────┘     └────────────────┘
                             │                          ▲
                             ▼                          │
                        ┌─────────────────┐      ┌─────────────────┐
                        │ MCPClient       │      │ mcp_servers.json│
                        │ .discover_      │◀─────│ (Configuration) │
                        │  servers()      │      └─────────────────┘
                        └─────────────────┘
                             │
                             ▼
                        ┌─────────────────┐
                        │ VectorStore     │
                        │ .build_index()  │
                        └─────────────────┘
```

### 2. Recherche et exécution d'outils

```
┌─────────────┐     ┌───────────────┐     ┌──────────────┐     ┌────────────────┐
│ Albert Bot  │────▶│ MCPRegistry   │────▶│ VectorStore  │────▶│ Outils indexés │
│ (commande)  │     │ .search_tools()│     │ .search()    │     │                │
└─────────────┘     └───────────────┘     └──────────────┘     └────────────────┘
                          │                                            ▲
                          ▼                                            │
                    ┌───────────────┐                           ┌─────────────┐
                    │ MCPRegistry   │                           │ MCPClient   │
                    │ .execute_tool()│                          │ .get_tools()│
                    └───────────────┘                           └─────────────┘
                          │                                            ▲
                          ▼                                            │
                    ┌───────────────┐                           ┌─────────────┐
                    │ MCPClient     │                           │ MCP Servers │
                    │ .execute_tool()│───────────────────────▶  │             │
                    └───────────────┘                           └─────────────┘
```

## Intégration avec Albert Bot

L'intégration avec Albert est réalisée via un module de commandes générique pour les outils MCP.

### Module de commandes MCP pour Albert

```python
# Exemple de structure du module Albert pour MCP
from albert_api import Command, CommandHandler
from mcp_registry.app.core.registry import MCPRegistry

class MCPCommandHandler(CommandHandler):
    def __init__(self):
        self.registry = MCPRegistry()

    async def setup(self):
        await self.registry.start()
        
    async def search_tools(self, query):
        tools = await self.registry.search_tools(query, limit=5)
        return tools
        
    async def execute_tool(self, tool_id, params):
        # Extraire server_id et tool_id
        server_id, tool_id = tool_id.split('/')
        result = await self.registry.execute_tool(server_id, tool_id, params)
        return result
        
    async def cleanup(self):
        await self.registry.stop()
```

### Commandes Albert génériques pour MCP

```python
# Exemple de commandes Albert génériques pour MCP
from albert_api import Command, Bot

@Bot.command("mcp-search", "Recherche et exécute un outil MCP")
async def search_and_execute(bot, message):
    # Extraire la requête et les paramètres du message
    query, params = parse_command(message.content)
    
    mcp_handler = bot.get_handler('MCPCommandHandler')
    tools = await mcp_handler.search_tools(query)
    
    if not tools:
        return f"Aucun outil MCP trouvé pour: {query}"
        
    # Utilise le premier outil trouvé
    tool = tools[0]
    tool_id = f"{tool['server_id']}/{tool['id']}"
    
    # Prépare les paramètres pour l'outil
    formatted_params = format_params_for_tool(tool, params)
    
    # Exécute l'outil
    result = await mcp_handler.execute_tool(tool_id, formatted_params)
    
    # Format et retourne le résultat
    return format_result_for_user(tool, result)
```

## Configuration

### 1. Configuration des serveurs MCP (`mcp_servers.json`)

```json
{
  "grist-mcp": {
    "command": "python",
    "args": [
      "C:\\chemin\\vers\\grist_mcp_server.py"
    ],
    "url": "http://localhost:5000/"
  },
  "github-mcp": {
    "command": "python",
    "args": [
      "C:\\chemin\\vers\\github_mcp_server.py"
    ],
    "url": "http://localhost:5001/"
  },
  "filesystem-mcp": {
    "command": "python",
    "args": [
      "C:\\chemin\\vers\\filesystem_mcp_server.py"
    ],
    "url": "http://localhost:5002/"
  },
  "n8n-mcp": {
    "command": "python",
    "args": [
      "C:\\chemin\\vers\\n8n_mcp_server.py"
    ],
    "url": "http://localhost:5003/"
  }
}
```

### 2. Configuration générale du Registry (`config.yaml`)

```yaml
app:
  name: "MCP Registry"
  version: "1.0.0"
  port: 8000

registry:
  discovery_interval: 300
  manage_servers: true
  server_urls:
    - "http://localhost:5000/"
    - "http://localhost:5001/"
    - "http://localhost:5002/"
    - "http://localhost:5003/"
```

## Enregistrement de nouveaux serveurs MCP

Pour ajouter un nouveau serveur MCP:

1. Ajoutez sa configuration dans `mcp_servers.json`
2. Ajoutez son URL dans `config.yaml` (section `server_urls`)
3. Redémarrez le MCP Registry, ou attendez le cycle de découverte suivant

Le Registry découvrira automatiquement les outils disponibles sur le nouveau serveur.

## Initialisation au démarrage d'Albert

```python
# Exemple d'initialisation d'Albert avec MCP
from albert_api import Bot
from mcp_handlers import MCPCommandHandler

async def startup():
    bot = Bot()
    
    # Enregistrer le gestionnaire MCP
    mcp_handler = MCPCommandHandler()
    bot.register_handler('MCPCommandHandler', mcp_handler)
    
    # Initialiser le gestionnaire
    await mcp_handler.setup()
    
    # Démarrer le bot
    await bot.start()
```

## Exemples d'utilisation

### 1. Utilisation de GitHub MCP

```
Utilisateur: @albert_bot liste mes repos github
```

Albert:
1. Parse la commande et identifie qu'il s'agit d'une requête GitHub
2. Utilise le MCPRegistry pour trouver l'outil approprié via recherche sémantique
3. Exécute l'outil "list_repositories" du serveur GitHub MCP
4. Retourne les résultats formatés à l'utilisateur

### 2. Utilisation du Filesystem MCP

```
Utilisateur: @albert_bot liste les fichiers dans /Documents/Projets
```

Albert:
1. Parse la commande et identifie qu'il s'agit d'une opération sur le système de fichiers
2. Utilise le Registry pour trouver l'outil "list_files" du serveur Filesystem MCP
3. Exécute l'outil avec le chemin spécifié
4. Retourne la liste des fichiers à l'utilisateur

### 3. Utilisation de n8n MCP

```
Utilisateur: @albert_bot exécute le workflow de traitement de factures
```

Albert:
1. Parse la commande et identifie qu'il s'agit d'une requête n8n
2. Trouve l'outil "execute_workflow" via le Registry
3. Exécute le workflow spécifié
4. Retourne les résultats de l'exécution à l'utilisateur

## Architecture d'extension pour un Tchapbot

Pour adapter cette architecture à un Tchapbot basé sur Albert API:

1. **Intégration du MCP Registry**:
   ```python
   from mcp_registry.app.core.registry import MCPRegistry
   
   class TchapbotMCPIntegration:
       def __init__(self):
           self.registry = MCPRegistry()
           
       async def initialize(self):
           await self.registry.start()
   ```

2. **Création de commandes spécifiques**:
   ```python
   @tchapbot.command("fichier", "Manipule des fichiers")
   async def fichier_command(bot, message):
       # Utilise le serveur Filesystem MCP
       # ...
   
   @tchapbot.command("git", "Interagit avec GitHub")
   async def git_command(bot, message):
       # Utilise le serveur GitHub MCP
       # ...
   ```

3. **Utilisation générique des outils MCP**:
   ```python
   @tchapbot.command("mcp", "Exécute n'importe quel outil MCP")
   async def generic_mcp_command(bot, message):
       # Structure: @tchapbot mcp [nom_outil] [paramètres]
       tool_name, params = parse_message(message.content)
       
       # Recherche de l'outil
       tools = await bot.mcp_integration.registry.search_tools(tool_name)
       
       if tools:
           # Exécution de l'outil
           result = await bot.mcp_integration.registry.execute_tool(
               tools[0]["server_id"], 
               tools[0]["id"], 
               params
           )
           return format_result(result)
       else:
           return f"Outil '{tool_name}' non trouvé"
   ```

Cette architecture est flexible et permet d'intégrer facilement tout serveur MCP respectant le protocole standard, qu'il s'agisse de serveurs existants ou de nouveaux serveurs développés pour des besoins spécifiques. 