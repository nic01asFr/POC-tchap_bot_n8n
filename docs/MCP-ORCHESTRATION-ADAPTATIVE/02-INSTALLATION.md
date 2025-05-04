# Installation et Prérequis

Ce document décrit la procédure d'installation et les prérequis nécessaires pour mettre en place le système d'orchestration adaptative MCP pour Albert Tchapbot.

## Prérequis

### 1. Environnement

- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)
- Accès administrateur sur la machine de déploiement
- Au moins 2 Go de RAM disponible pour le système complet

### 2. MCP Registry

Le système d'orchestration adaptative s'appuie sur un MCP Registry fonctionnel. Si vous n'avez pas encore installé le MCP Registry, suivez les instructions dans la [documentation du MCP Registry](../INSTALLATION-MCP-REGISTRY.md).

Assurez-vous que votre MCP Registry est correctement configuré et peut communiquer avec au moins quelques serveurs MCP de base.

### 3. Albert Tchapbot

Vous devez disposer d'une installation fonctionnelle d'Albert Tchapbot. Si ce n'est pas le cas, consultez la documentation principale d'Albert pour le configurer.

### 4. Serveurs MCP

Pour tirer pleinement parti du système d'orchestration, nous recommandons d'installer au moins les serveurs MCP suivants :

- **Memory** (obligatoire) - Pour le stockage de données entre les étapes des compositions
- **Filesystem** - Pour les opérations sur les fichiers
- **Grist** - Pour l'accès aux données tabulaires

## Installation

### Méthode 1 : Installation via pip

1. Installez le package `albert-mcp-adaptive-orchestrator` :

```bash
pip install albert-mcp-adaptive-orchestrator
```

2. Vérifiez l'installation :

```bash
python -c "import albert_mcp_orchestrator; print(albert_mcp_orchestrator.__version__)"
```

### Méthode 2 : Installation depuis les sources

1. Clonez le dépôt :

```bash
git clone https://github.com/albert-tchapbot/mcp-adaptive-orchestrator.git
cd mcp-adaptive-orchestrator
```

2. Installez les dépendances :

```bash
pip install -r requirements.txt
```

3. Installez le package en mode développement :

```bash
pip install -e .
```

## Configuration

### 1. Configuration du MCP Registry

Assurez-vous que votre fichier de configuration du MCP Registry (`mcp-registry/conf/config.yaml`) contient les paramètres suivants :

```yaml
app:
  name: "MCP Registry with Adaptive Orchestration"
  version: "1.0.0"
  port: 8000
  log_level: "INFO"

registry:
  discovery_interval: 300  # en secondes
  manage_servers: true
  enable_adaptive_orchestration: true  # Activer l'orchestration adaptative
  compositions_path: "./compositions"  # Chemin pour stocker les compositions
  
  # URLs des serveurs MCP (assurez-vous que le serveur Memory est inclus)
  server_urls:
    - "http://localhost:5000/"  # Memory
    - "http://localhost:5001/"  # Autre serveur
    - "http://localhost:5002/"  # Autre serveur
```

### 2. Configuration du serveur Memory

Le serveur Memory est essentiel pour l'orchestration adaptative. Assurez-vous qu'il est correctement configuré dans votre fichier `mcp_servers.json` :

```json
{
  "memory": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-memory"],
    "url": "http://localhost:5000/"
  }
}
```

### 3. Configuration d'Albert Tchapbot

Modifiez la configuration d'Albert pour activer le handler d'orchestration adaptative. Dans le fichier de configuration d'Albert, ajoutez :

```yaml
handlers:
  - name: "AdaptiveOrchestratorHandler"
    module: "albert_mcp_orchestrator.handlers"
    enabled: true
    config:
      registry_url: "http://localhost:8000"  # URL du MCP Registry
      compositions_path: "./compositions"     # Chemin des compositions
      learning_enabled: true                  # Activer l'apprentissage
      log_level: "INFO"                       # Niveau de log
```

## Structure des répertoires

Après l'installation, vous devriez avoir la structure de répertoires suivante :

```
albert-tchapbot/
├── mcp-registry/           # MCP Registry
│   ├── conf/
│   │   ├── config.yaml     # Configuration du Registry
│   │   └── mcp_servers.json # Configuration des serveurs MCP
│   └── ...
├── compositions/           # Répertoire des compositions
│   ├── validated/          # Compositions validées
│   ├── learning/           # Compositions en apprentissage
│   └── templates/          # Modèles de compositions
└── config.yaml             # Configuration d'Albert Tchapbot
```

## Vérification de l'installation

Pour vérifier que l'installation a réussi :

1. Démarrez le MCP Registry :

```bash
cd mcp-registry
python start_mcp_registry.py
```

2. Vérifiez les logs pour confirmer que l'orchestration adaptative est activée :

```
INFO - MCP Registry - Adaptive orchestration enabled, loading compositions from ./compositions
```

3. Démarrez Albert Tchapbot et vérifiez que le handler est chargé :

```bash
cd albert-tchapbot
python start_albert.py
```

4. Testez une commande d'orchestration simple :

```
@albert_bot compose liste mes fichiers importants et résume leur contenu
```

Si tout est correctement configuré, l'orchestrateur devrait traiter cette requête en décomposant la tâche en plusieurs étapes (listage de fichiers, puis lecture et résumé de chaque fichier).

## Serveurs MCP recommandés

Voici une liste plus détaillée des serveurs MCP recommandés pour l'orchestration adaptative :

### Serveurs de base

| Nom | Description | Installation | Utilité pour l'orchestration |
|-----|-------------|-------------|---------------------------|
| Memory | Stockage de données persistant | `npx -y @modelcontextprotocol/server-memory` | **Essentiel** - Utilisé pour stocker des données entre les étapes |
| Filesystem | Accès aux fichiers locaux | `npx -y @modelcontextprotocol/server-filesystem /path/to/allowed` | Très utile pour les compositions impliquant des fichiers |
| Git | Opérations sur les dépôts Git | `uvx mcp-server-git --repository /path/to/repo` | Utile pour les workflows de développement |

### Serveurs pour données structurées

| Nom | Description | Installation | Utilité pour l'orchestration |
|-----|-------------|-------------|---------------------------|
| Grist | Accès aux bases Grist | Configuration spécifique | Excellent pour les compositions impliquant des données tabulaires |
| Postgres | Accès aux bases PostgreSQL | `npx -y @modelcontextprotocol/server-postgres postgresql://localhost/mydb` | Pour les compositions nécessitant des données relationnelles |
| SQLite | Accès aux bases SQLite | `npx -y @modelcontextprotocol/server-sqlite /path/to/db.sqlite` | Alternative légère à Postgres |

### Serveurs pour la productivité

| Nom | Description | Installation | Utilité pour l'orchestration |
|-----|-------------|-------------|---------------------------|
| Gmail | Accès aux emails | Configuration spécifique | Pour les compositions impliquant des emails |
| Calendar | Gestion du calendrier | Configuration spécifique | Pour les compositions de planification |
| Notion | Accès à Notion | Configuration spécifique | Pour les compositions de gestion de connaissances |

### Serveurs pour le développement

| Nom | Description | Installation | Utilité pour l'orchestration |
|-----|-------------|-------------|---------------------------|
| GitHub | Interaction avec GitHub | `npx -y @modelcontextprotocol/server-github` avec token | Pour les compositions liées au développement |
| VS Code | Intégration avec VS Code | Configuration spécifique | Pour les compositions d'assistance au développement |

## Dépannage

### Le service d'orchestration ne démarre pas

- Vérifiez que le MCP Registry est en cours d'exécution
- Assurez-vous que le serveur Memory est correctement configuré
- Vérifiez les logs pour des erreurs spécifiques
- Assurez-vous que les chemins dans la configuration sont corrects et accessibles

### Les compositions ne sont pas créées

- Vérifiez que le répertoire `compositions` existe et est accessible en écriture
- Assurez-vous que l'apprentissage est activé dans la configuration
- Vérifiez que vous avez suffisamment d'espace disque

### Erreurs d'exécution des compositions

- Assurez-vous que tous les serveurs MCP nécessaires sont en cours d'exécution
- Vérifiez les permissions d'accès aux ressources requises
- Consultez les logs pour des erreurs spécifiques 