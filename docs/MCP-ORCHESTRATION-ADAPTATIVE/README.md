# Documentation du Système d'Orchestration Adaptative MCP pour Albert Tchapbot

Bienvenue dans la documentation du système d'orchestration adaptative MCP pour Albert Tchapbot. Ce système permet d'améliorer considérablement les capacités de votre Tchapbot en automatisant la composition et l'exécution d'outils MCP complexes.

## Présentation

Le système d'orchestration adaptative MCP est une extension avancée du MCP Registry qui permet à Albert Tchapbot de :

1. **Composer automatiquement** des séquences d'outils MCP pour réaliser des tâches complexes
2. **Apprendre de ses exécutions** pour améliorer ses performances au fil du temps
3. **Créer de nouveaux outils composites** à partir des compositions réussies
4. **Réduire la charge cognitive** sur le modèle LLM en lui offrant des outils de plus haut niveau

Cette architecture est particulièrement adaptée aux cas où le modèle LLM d'Albert n'est pas assez puissant pour orchestrer lui-même des workflows complexes impliquant plusieurs outils MCP.

## Contenu de la documentation

- [Architecture générale](./01-ARCHITECTURE.md) - Vue d'ensemble du système
- [Installation et prérequis](./02-INSTALLATION.md) - Comment installer et configurer le système
- [Orchestrateur adaptatif](./03-ORCHESTRATEUR.md) - Fonctionnement détaillé de l'orchestrateur
- [Registre de compositions](./04-REGISTRE-COMPOSITIONS.md) - Comment les compositions sont stockées et gérées
- [Module d'apprentissage](./05-APPRENTISSAGE.md) - Mécanismes d'apprentissage du système
- [Intégration avec Albert](./06-INTEGRATION-ALBERT.md) - Comment intégrer le système avec Albert Tchapbot
- [Exemples d'utilisation](./07-EXEMPLES.md) - Exemples concrets d'utilisation
- [Guide de dépannage](./08-DEPANNAGE.md) - Résolution des problèmes courants

## Démarrage rapide

Pour une mise en place rapide du système, suivez ces étapes :

1. Assurez-vous d'avoir une installation fonctionnelle du MCP Registry
2. Installez le module d'orchestration adaptative :
   ```bash
   pip install albert-mcp-adaptive-orchestrator
   ```
3. Configurez le module dans votre configuration Albert :
   ```yaml
   # config.yaml
   mcp:
     enable_adaptive_orchestrator: true
     compositions_path: "./compositions"
   ```
4. Démarrez votre Tchapbot Albert avec le module activé
5. Commencez à utiliser des compositions automatiques avec la commande `@albert_bot compose`

## Principe de fonctionnement

Le système d'orchestration adaptative fonctionne selon ce workflow :

1. L'utilisateur envoie une requête à Albert qui nécessite plusieurs outils MCP
2. L'orchestrateur vérifie si une composition existante correspond à cette requête
3. Si une composition existe, elle est exécutée directement
4. Sinon, l'orchestrateur décompose la tâche en étapes simples et les exécute séquentiellement
5. La nouvelle séquence d'exécution est enregistrée comme une composition potentielle
6. Si la composition est utilisée avec succès plusieurs fois, elle devient un nouvel outil MCP

Ce système permet à Albert de s'améliorer continuellement, même avec un modèle LLM de capacité modeste.

## Serveurs MCP recommandés

Le système est compatible avec tous les serveurs MCP, mais certains sont particulièrement utiles pour la création de compositions :

- **Memory** - Pour stocker et récupérer des données entre les étapes
- **Filesystem** - Pour les opérations sur les fichiers
- **Git/GitHub** - Pour l'interaction avec les dépôts
- **Grist** - Pour la manipulation de données tabulaires
- **Calendar/Gmail** - Pour les intégrations avec Google Workspace

Consultez la [liste complète des serveurs MCP recommandés](./02-INSTALLATION.md#serveurs-mcp-recommandés) pour plus d'informations.

## Support et contribution

Si vous rencontrez des problèmes ou souhaitez contribuer à ce projet :

1. Consultez le [guide de dépannage](./08-DEPANNAGE.md)
2. Ouvrez une issue sur le dépôt GitHub
3. Proposez des améliorations via des pull requests

---

Cette documentation est maintenue par l'équipe Albert Tchapbot. Pour toute question, contactez support@albert-tchapbot.com. 