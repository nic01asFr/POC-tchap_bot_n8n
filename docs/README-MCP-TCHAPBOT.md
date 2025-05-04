# Documentation MCP pour Tchapbot Albert

Bienvenue dans la documentation du MCP (Model Control Protocol) pour le Tchapbot Albert. Cette documentation couvre l'installation, la configuration et l'utilisation du MCP Registry pour intégrer divers services externes à votre Tchapbot.

## Contenu de la documentation

### Documentation générale

- [Architecture et composants MCP](MCP-REGISTRY-POUR-TCHAPBOT.md) - Vue d'ensemble de l'architecture MCP Registry
- [Guide d'installation](INSTALLATION-MCP-REGISTRY.md) - Guide étape par étape pour installer le MCP Registry

### Documentation spécifique aux serveurs MCP

- [Intégration Grist](MCP-GRIST-POUR-TCHAPBOT.md) - Utilisation de Grist via MCP

## Qu'est-ce que le MCP?

Le MCP (Model Control Protocol) est un protocole qui permet à un assistant IA comme Albert d'interagir avec des services externes via des outils standardisés. Le MCP Registry est un composant central qui:

1. Découvre et gère les serveurs MCP
2. Indexe les outils disponibles sur chaque serveur
3. Permet la recherche sémantique d'outils
4. Facilite l'exécution des outils par le Tchapbot

## Architecture simplifiée

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Tchapbot    │────▶│ MCP Registry │────▶│ Serveurs MCP    │
│ Albert      │     │              │     │ (Grist, GitHub, │
└─────────────┘     └──────────────┘     │  Filesystem,    │
                                         │  n8n, etc.)     │
                                         └─────────────────┘
```

## Démarrage rapide

1. [Installez le MCP Registry](INSTALLATION-MCP-REGISTRY.md)
2. Configurez au moins un serveur MCP (par exemple, [Grist MCP](MCP-GRIST-POUR-TCHAPBOT.md))
3. Démarrez le MCP Registry avec `python start_mcp_registry.py`
4. Intégrez le MCPCommandHandler dans votre Tchapbot Albert

## Exemples d'utilisation

Voici quelques exemples d'utilisation du MCP avec votre Tchapbot:

### Interaction avec Grist

```
Utilisateur: @tchapbot grist lister_orgs

Tchapbot: Organisations Grist:
- Mon Organisation (ID: 123)
- Organisation Test (ID: 456)
```

### Manipulation de fichiers

```
Utilisateur: @tchapbot fichier liste /Documents

Tchapbot: Fichiers dans /Documents:
- Projet1.docx
- Rapport.pdf
- budget.xlsx
```

## Serveurs MCP disponibles

Le MCP Registry peut être étendu avec différents serveurs MCP:

| Serveur MCP | Description | Documentation |
|-------------|-------------|---------------|
| Grist MCP | Interaction avec bases de données Grist | [Documentation](MCP-GRIST-POUR-TCHAPBOT.md) |
| Filesystem MCP | Manipulation de fichiers locaux | À venir |
| GitHub MCP | Interaction avec GitHub | À venir |
| n8n MCP | Exécution de workflows n8n | À venir |

## Contribution

Vous souhaitez contribuer à ce projet? Vous pouvez:

1. Améliorer la documentation existante
2. Développer de nouveaux serveurs MCP
3. Signaler des bugs ou proposer des améliorations

## Support

Si vous rencontrez des problèmes ou avez des questions:

1. Consultez la section [Résolution des problèmes courants](INSTALLATION-MCP-REGISTRY.md#résolution-des-problèmes-courants)
2. Ouvrez une issue sur le dépôt GitHub
3. Contactez l'équipe de support 