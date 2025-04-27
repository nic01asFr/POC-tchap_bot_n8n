# Intégration n8n dans Albert-Tchap

Ce document explique comment Albert-Tchap peut découvrir et utiliser dynamiquement les capacités exposées par n8n.

## Architecture

L'intégration repose sur une architecture client-serveur :

- **Albert-Tchap** agit comme client, découvrant et invoquant les capacités de n8n
- **n8n** expose les capacités via des endpoints RESTful (webhooks et MCP)

```
[Utilisateurs Tchap] 
      ↓ conversation
[Albert-Tchap Bot] ←→ HTTP(S) →→ [n8n API Gateway]
                                    ↓
          ┌───────────────────────┬─────────────────────┐
          ↓                       ↓                     ↓
[Catalogue MCP]            [Catalogue Webhooks]   [Exécution Tools]
```

## Fonctionnalités

### 1. Découverte des outils

Albert-Tchap peut découvrir dynamiquement les outils disponibles dans n8n :

- **Commande `!tools`** : Liste toutes les catégories d'outils
- **Commande `!tools <catégorie>`** : Liste les outils d'une catégorie spécifique
- **Commande `!tools search <terme>`** : Recherche des outils par mot-clé

### 2. Exécution des outils

Albert-Tchap peut exécuter les outils n8n avec des paramètres :

- **Commande `!run <nom_outil> [paramètres]`** : Exécute un outil spécifique
- Format des paramètres : `nom=valeur` ou `nom="valeur avec espaces"`

### 3. Détection contextuelle

Albert-Tchap peut détecter des intentions d'utilisation d'outils dans les conversations :

- Analyse les messages pour détecter des mots-clés liés à des catégories d'outils
- Suggère des outils appropriés lorsqu'une intention est détectée

## Composants techniques

### Côté Albert-Tchap

1. **Module `n8n`** : Module Python pour interagir avec l'API n8n
   - `client.py` : Client HTTP pour communiquer avec n8n
   - `command.py` : Gestionnaire de commandes n8n
   - `models.py` : Modèles de données pour les outils n8n

2. **Commandes** : Intégration dans le système de commandes existant
   - `n8n_commands.py` : Enregistre les commandes `!tools` et `!run`

### Côté n8n

1. **Workflow "Catalogue"** : Expose la liste des outils disponibles
   - Endpoint `/catalog/all` qui renvoie tous les outils exposés
   - Extraction des informations des webhooks et du serveur MCP

2. **Workflow "MCP Hub"** : Expose les outils via le protocole MCP
   - Nœud "MCP Server Trigger" pour exposer les outils
   - Custom Workflow Tools pour envelopper des workflows complexes

## Configuration

### Variables d'environnement

```
# Dans le fichier .env d'Albert-Tchap
N8N_ENABLED=True
N8N_BASE_URL=https://votre-instance-n8n.fr
N8N_AUTH_TOKEN=votre-token-bearer
N8N_MCP_URL=https://votre-instance-n8n.fr/webhook/mcp
N8N_TOOLS_CACHE_TTL=300
```

## Sécurité

- **Authentification** : Token Bearer pour sécuriser les communications
- **Autorisations** : Seuls les utilisateurs autorisés peuvent utiliser les commandes n8n
- **Filtrage** : Seuls les workflows taggés "expose" sont visibles dans le catalogue

## Exemples d'utilisation

### Lister les catégories d'outils

```
Utilisateur : !tools
Albert : 
📋 **Catégories d'outils disponibles:**

**EMAIL** (2 outils)
**DATABASE** (3 outils)
**DOCUMENTS** (1 outil)

Utilisez `!tools <catégorie>` pour voir les outils d'une catégorie
Utilisez `!tools search <terme>` pour rechercher des outils
```

### Exécuter un outil

```
Utilisateur : !run send_email destinataire="jean@example.fr" sujet="Réunion" contenu="Bonjour Jean"
Albert : ✅ Email envoyé avec succès à jean@example.fr
```

### Détection contextuelle

```
Utilisateur : J'aimerais envoyer un email à l'équipe
Albert : 
Il semble que vous vouliez utiliser un outil de la catégorie **email**.

Voici quelques outils disponibles:
- **send_email**: Envoie un email aux destinataires spécifiés
- **read_emails**: Lit les emails récents

Pour utiliser un outil, tapez `!run <nom_outil> [paramètres]`
```

## Pour aller plus loin

Voir le guide détaillé d'installation dans `n8n_setup_guide.md` pour configurer les workflows nécessaires dans n8n. 