# MCP Registry pour Albert-Tchap

Un service de registre pour les serveurs MCP (Model Context Protocol) compatible avec le standard MCP, développé pour Albert-Tchap.

## Fonctionnalités

- ✅ **Compatible avec le standard MCP** - Fonctionne avec Claude Desktop, VS Code, Cursor et autres clients MCP
- 🔍 **Découverte automatique** - Découvre automatiquement les serveurs MCP disponibles
- 🧰 **Standardisation des outils** - Normalise les différents formats d'outils pour une meilleure compatibilité
- 🔎 **Recherche vectorielle** - Permet de rechercher des outils par similarité sémantique
- 🔄 **Exécution adaptative** - Supporte plusieurs formats d'exécution d'outils

## Installation

### Prérequis

- Docker et Docker Compose
- Python 3.8+ (pour le développement local)

### Utilisation avec Docker Compose

1. Cloner le dépôt :
   ```bash
   git clone https://github.com/votre-organisation/albert-tchap.git
   cd albert-tchap/mcp-registry
   ```

2. Créer un fichier `.env` avec les variables nécessaires :
   ```
   ALBERT_API_TOKEN=votre_token_api
   ALBERT_API_URL=https://api.albert.exemple.fr
   ALBERT_MODEL=mixtral-8x7b-instruct-v0.1
   GRIST_API_KEY=votre_cle_api_grist
   GRIST_SERVER_URL=https://docs.grist.exemple.fr
   ```

3. Lancer avec Docker Compose :
   ```bash
   docker-compose -f docker-compose.mcp-standard.yml up -d
   ```

### Configuration des clients MCP

Utilisez le script fourni pour configurer automatiquement vos clients MCP (Claude Desktop, VS Code, Cursor) :

```bash
python scripts/setup_mcp_clients.py --url http://localhost:8001 --clients all
```

## Architecture

Le MCP Registry sert d'intermédiaire entre les clients MCP et les serveurs MCP :

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Clients    │────▶│ MCP Registry │────▶│ Serveurs MCP    │
│  (Claude,   │     │              │     │ (Grist, GitHub, │
│   VSCode,   │◀────│              │◀────│  Filesystem,    │
│   Cursor)   │     └──────────────┘     │  etc.)          │
└─────────────┘                          └─────────────────┘
```

## Endpoints API

### Endpoints standards MCP

- **GET /info** - Informations sur le MCP Registry
- **GET /servers** - Liste des serveurs MCP disponibles
- **GET /tools** - Liste des outils MCP disponibles
- **POST /execute** - Exécute un outil MCP

### Endpoints API supplémentaires

- **GET /api/status** - État du service
- **GET /api/servers** - Liste détaillée des serveurs
- **GET /api/tools** - Liste détaillée des outils
- **POST /api/search** - Recherche sémantique d'outils
- **POST /api/analyze** - Analyse d'intention pour recommander des outils

## Développement

### Installation locale

```bash
cd mcp-registry
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sous Windows
pip install -r requirements.txt
```

### Lancement local

```bash
cd mcp-registry
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## Intégration avec d'autres services

Consultez la documentation sur l'intégration avec d'autres services :

- [Intégration avec Grist](docs/integration-grist.md)
- [Intégration avec n8n](docs/integration-n8n.md)
- [Intégration avec Albert](docs/integration-albert.md)

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request. 