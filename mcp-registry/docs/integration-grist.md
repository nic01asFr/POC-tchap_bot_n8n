# Intégration du MCP Registry avec Grist

Ce document explique comment intégrer le MCP Registry avec Grist, vous permettant d'utiliser les fonctionnalités de Grist dans des outils compatibles MCP comme Claude Desktop, VS Code, et Cursor.

## Prérequis

- Un compte Grist avec une clé API
- Le MCP Registry en cours d'exécution
- Un serveur MCP Grist configuré

## Configuration du serveur MCP Grist

### 1. Configurer les variables d'environnement

Créez un fichier `.env` dans le répertoire `mcp-registry` avec les informations suivantes :

```
GRIST_API_KEY=votre_cle_api_grist
GRIST_SERVER_URL=https://docs.grist.exemple.fr
```

### 2. Démarrer le serveur MCP Grist

Vous pouvez démarrer le serveur MCP Grist de deux façons :

#### Option 1 : Utiliser Docker Compose

```bash
docker-compose -f docker-compose.mcp-standard.yml up -d
```

#### Option 2 : Démarrer manuellement

```bash
cd mcp-registry
python scripts/start_grist_mcp.py
```

### 3. Vérifier que le serveur est détecté par le MCP Registry

Accédez à l'URL de votre MCP Registry (par défaut : http://localhost:8001) et vérifiez que le serveur Grist apparaît dans la liste des serveurs.

## Utilisation des outils Grist dans les clients MCP

### Exemples d'utilisation dans Claude Desktop

Une fois le MCP Registry configuré et le serveur Grist MCP en cours d'exécution, vous pouvez utiliser les fonctionnalités de Grist dans Claude Desktop comme suit :

#### 1. Configuration de Claude Desktop

Exécutez le script de configuration :

```bash
python scripts/setup_mcp_clients.py --client claude
```

#### 2. Requêtes à Grist via Claude

Voici quelques exemples de requêtes que vous pouvez adresser à Claude Desktop pour utiliser les outils Grist :

- "Liste toutes les tables du document Grist XYZ"
- "Montre-moi les 10 premières lignes de la table 'Clients'"
- "Crée une nouvelle entrée dans la table 'Tâches' avec le titre 'Révision du projet'"
- "Filtre la table 'Ventes' pour ne montrer que les ventes supérieures à 1000€"

### Intégration avec VS Code et Cursor

Pour VS Code ou Cursor, la configuration est similaire mais utilisez l'option correspondante dans le script :

```bash
# Pour VS Code
python scripts/setup_mcp_clients.py --client vscode

# Pour Cursor
python scripts/setup_mcp_clients.py --client cursor
```

## Outils Grist disponibles

Le serveur MCP Grist fournit les outils suivants :

| Nom de l'outil | Description | Paramètres |
|----------------|-------------|------------|
| `list_orgs` | Liste les organisations Grist | Aucun |
| `list_workspaces` | Liste les espaces de travail | `org_id` |
| `list_docs` | Liste les documents | `org_id`, `workspace_id` |
| `list_tables` | Liste les tables d'un document | `doc_id` |
| `list_records` | Liste les enregistrements d'une table | `doc_id`, `table_id`, `limit` |
| `add_record` | Ajoute un enregistrement à une table | `doc_id`, `table_id`, `fields` |
| `update_record` | Met à jour un enregistrement | `doc_id`, `table_id`, `record_id`, `fields` |
| `delete_record` | Supprime un enregistrement | `doc_id`, `table_id`, `record_id` |
| `execute_query` | Exécute une requête SQL sur un document | `doc_id`, `query` |

## Dépannage

### Le serveur Grist MCP n'est pas détecté

Vérifiez que :
- Le serveur Grist MCP est en cours d'exécution
- L'URL du serveur Grist MCP est correcte dans la configuration
- Votre clé API Grist est valide
- Les ports ne sont pas bloqués par un pare-feu

### Les outils Grist ne sont pas accessibles

Vérifiez que :
- Le MCP Registry est correctement configuré
- Le client MCP (Claude, VS Code, etc.) est correctement configuré pour utiliser le MCP Registry
- Les autorisations de votre compte Grist sont suffisantes pour les opérations demandées

## Ressources additionnelles

- [Documentation officielle de Grist](https://support.getgrist.com/)
- [Documentation de l'API Grist](https://support.getgrist.com/api/) 