# Documentation Technique: Intégration Grist via MCP pour Tchapbot Albert

## Introduction à Grist MCP

L'intégration de Grist via MCP permet à un Tchapbot Albert d'interagir avec des bases de données Grist, offrant ainsi une interface conversationnelle pour manipuler des données structurées.

## Fonctionnalités principales

Le serveur MCP Grist expose les fonctionnalités suivantes:

- **Lister les organisations** (`mcp_list_organizations`)
- **Lister les espaces de travail** (`mcp_list_workspaces`)
- **Lister les documents** (`mcp_list_documents`)
- **Lister les tables** (`mcp_list_tables`)
- **Lister les colonnes** (`mcp_list_columns`)
- **Lister les enregistrements** (`mcp_list_records`)
- **Ajouter des enregistrements** (`mcp_add_grist_records`)
- **Mettre à jour des enregistrements** (`mcp_update_grist_records`)
- **Supprimer des enregistrements** (`mcp_delete_grist_records`)
- **Exécuter des requêtes SQL filtrées** (`mcp_filter_sql_query`)
- **Exécuter des requêtes SQL personnalisées** (`mcp_execute_sql_query`)

## Configuration du serveur MCP Grist

### Prérequis

1. Un compte Grist (gratuit ou payant)
2. Une clé API Grist
3. Python 3.8+ avec les dépendances requises

### Installation du serveur MCP Grist

1. Cloner le dépôt contenant le serveur MCP Grist
2. Installer les dépendances:
   ```
   pip install -r requirements.txt
   ```
3. Configurer les variables d'environnement:
   ```
   GRIST_API_KEY=votre_clé_api
   GRIST_SERVER_URL=https://docs.getgrist.com
   ```

### Configuration dans le MCP Registry

Dans le fichier `mcp_servers.json`, ajouter:

```json
{
  "grist-mcp": {
    "command": "python",
    "args": [
      "C:\\chemin\\vers\\grist_mcp_server.py"
    ],
    "url": "http://localhost:5000/",
    "env": {
      "GRIST_API_KEY": "votre_clé_api",
      "GRIST_SERVER_URL": "https://docs.getgrist.com"
    }
  }
}
```

## Exemples d'utilisation

### 1. Lister les organisations

```
Utilisateur: @tchapbot liste mes organisations grist
```

Flux d'exécution:
1. Le Tchapbot analyse la commande
2. Il utilise le MCPRegistry pour trouver l'outil `mcp_list_organizations`
3. Il exécute l'outil sans paramètres
4. Il retourne la liste des organisations formatée

### 2. Lister les documents d'un espace de travail

```
Utilisateur: @tchapbot liste les documents dans l'espace de travail 123
```

Flux d'exécution:
1. Le Tchapbot analyse la commande et extrait l'ID de l'espace de travail (123)
2. Il trouve l'outil `mcp_list_documents`
3. Il exécute l'outil avec le paramètre `workspace_id=123`
4. Il retourne la liste des documents

### 3. Manipuler des enregistrements

```
Utilisateur: @tchapbot ajoute un contact avec nom=Dupont, prénom=Jean, email=jean.dupont@example.com
```

Flux d'exécution:
1. Le Tchapbot analyse la commande et extrait les informations du contact
2. Il cherche l'outil `mcp_add_grist_records`
3. Il exécute l'outil avec les paramètres:
   ```json
   {
     "doc_id": "document_id",
     "table_id": "Contacts",
     "records": [
       {
         "nom": "Dupont",
         "prénom": "Jean",
         "email": "jean.dupont@example.com"
       }
     ]
   }
   ```
4. Il retourne une confirmation de l'ajout

## Intégration dans le Tchapbot

### Commandes spécifiques à Grist

```python
@tchapbot.command("grist", "Interagit avec Grist")
async def grist_command(bot, message):
    # Parse la commande pour extraire l'action et les paramètres
    action, params = parse_grist_command(message.content)
    
    # Map des actions vers les outils MCP
    tool_map = {
        "lister_orgs": "mcp_list_organizations",
        "lister_espaces": "mcp_list_workspaces",
        "lister_docs": "mcp_list_documents",
        "lister_tables": "mcp_list_tables",
        "lister_colonnes": "mcp_list_columns",
        "lister_enregistrements": "mcp_list_records",
        "ajouter": "mcp_add_grist_records",
        "modifier": "mcp_update_grist_records",
        "supprimer": "mcp_delete_grist_records",
        "rechercher": "mcp_filter_sql_query",
        "requete": "mcp_execute_sql_query"
    }
    
    # Trouver l'outil correspondant
    mcp_handler = bot.get_handler('MCPCommandHandler')
    tools = await mcp_handler.registry.search_tools_by_name(tool_map.get(action))
    
    if not tools:
        return f"Commande Grist non reconnue: {action}"
    
    # Préparer et exécuter l'outil
    tool = tools[0]
    result = await mcp_handler.execute_tool(
        f"{tool['server_id']}/{tool['id']}", 
        params
    )
    
    # Formater et retourner le résultat
    return format_grist_result(action, result)
```

### Fonctions utilitaires

```python
def parse_grist_command(content):
    """
    Parse une commande Grist.
    Format: @tchapbot grist [action] [paramètres]
    
    Exemple: @tchapbot grist lister_docs espace=123
    """
    # Extrait l'action (lister_orgs, lister_docs, etc.)
    parts = content.split(maxsplit=2)
    if len(parts) < 3:
        return "lister_orgs", {}
        
    action = parts[2].split()[0]
    
    # Extrait les paramètres (au format clé=valeur)
    params = {}
    if len(parts) > 3:
        param_str = parts[3]
        for param in param_str.split():
            if "=" in param:
                key, value = param.split("=", 1)
                params[key] = value
                
    return action, params

def format_grist_result(action, result):
    """
    Formate les résultats d'une commande Grist pour l'affichage.
    """
    if action == "lister_orgs":
        if not result:
            return "Vous n'avez accès à aucune organisation Grist."
            
        return "Organisations Grist:\n" + "\n".join([
            f"- {org['name']} (ID: {org['id']})" for org in result
        ])
        
    elif action == "lister_espaces":
        if not result:
            return "Aucun espace de travail trouvé dans cette organisation."
            
        return "Espaces de travail:\n" + "\n".join([
            f"- {workspace['name']} (ID: {workspace['id']})" for workspace in result
        ])
        
    # Formatage pour d'autres actions...
    
    return str(result)
```

## Exemple d'utilisation complète

Voici un exemple complet d'interaction avec Grist via le Tchapbot:

```
Utilisateur: @tchapbot grist lister_orgs

Tchapbot: Organisations Grist:
- Mon Organisation (ID: 123)
- Organisation Test (ID: 456)

Utilisateur: @tchapbot grist lister_espaces org=123

Tchapbot: Espaces de travail:
- Projets (ID: 789)
- Finances (ID: 101)

Utilisateur: @tchapbot grist lister_docs espace=789

Tchapbot: Documents:
- Projets 2023 (ID: doc1)
- Clients (ID: doc2)

Utilisateur: @tchapbot grist lister_tables doc=doc2

Tchapbot: Tables:
- Clients
- Contacts
- Factures

Utilisateur: @tchapbot grist ajouter doc=doc2 table=Clients nom="Entreprise XYZ" secteur="Technologie" contact="Alice Smith"

Tchapbot: Client ajouté avec succès (ID: 42)
```

## Gestion des erreurs

Le serveur MCP Grist inclut une gestion des erreurs pour les cas courants:

- **Authentification**: Erreurs liées à la clé API invalide
- **Permissions**: Tentatives d'accès à des ressources sans autorisation
- **Ressources introuvables**: Documents, tables ou enregistrements non trouvés
- **Validation**: Données non conformes au schéma de la table

Ces erreurs sont transmises au Tchapbot qui les reformate en messages compréhensibles.

## Extensions possibles

L'intégration Grist via MCP peut être étendue pour:

1. **Création automatique de vues**: Permettre de créer des vues personnalisées sur les données
2. **Export de données**: Ajouter des fonctionnalités d'exportation (CSV, Excel)
3. **Gestion des widgets**: Manipuler les widgets des tableaux de bord Grist
4. **Intégration avec traitement en langage naturel**: Permettre des requêtes en langage naturel converties en SQL

Cette architecture modulaire facilite l'ajout de nouvelles fonctionnalités sans modifier le cœur du Tchapbot. 