# Colaig : projet d'interopérabilité sur Tchap via n8n

*Un assistant intelligent pour vous faire gagner du temps, intégré à votre environnement de travail*

## 📋 Présentation du projet

Ce projet est une concrétisation de la vision **Colaig** - assistant IA intégré à l'espace numérique des agents publics. Il s'agit d'un POC (Proof of Concept) qui démontre comment un assistant IA interopérable, modulaire et évolutif peut s'intégrer aux outils existants de l'administration via une architecture moderne et ouverte.

### De la vision Colaig à la réalité opérationnelle

Colaig a été conçu comme une solution d'intelligence artificielle conversationnelle pensée spécifiquement pour le Bnum, capable de s'intégrer organiquement dans l'écosystème administratif. Ce POC transforme cette vision en une implémentation concrète en utilisant des technologies existantes et ouvertes.

![Capture d’écran 2025-04-27 023440.png](https://docs.numerique.gouv.fr/media/4df125ad-ea7c-4bbf-9b8e-e9e3b67d3097/attachments/bcf16eea-b5a0-42db-83e0-a4d0dd98ecb6.png)

> Flow de connexion au tchapbot via webhook 

![Capture d’écran 2025-04-24 044136.png](https://docs.numerique.gouv.fr/media/4df125ad-ea7c-4bbf-9b8e-e9e3b67d3097/attachments/72507361-4f1b-40e5-ad2e-2b870d8a2dc2.png)

> Ici un MCP Server construit sur n8n. Mon agent dispose de 6 Tools, permettant ici d'interagir avec les espaces documentaires du Bnum

## 🌟 Caractéristiques principales

*   **📚 Assistant conversationnel sur Tchap** - Accessible directement dans la messagerie de l'État
*   **🔄 Orchestration des workflows via n8n** - Automatisation puissante et flexible
*   **🛠️ Intégration avec Albert** - Utilise le modèle de langage de l'administration française
*   **🌐 Architecture modulaire** - Basée sur des protocoles ouverts (MCP, A2A)
*   **👥 Extensible et évolutif** - S'enrichit avec de nouvelles capacités sans repartir de zéro

## ⚙️ Architecture du système

L'architecture du POC s'articule autour de trois composants principaux, alignés avec la vision progressive de Colaig :

### 💬 Bot Tchap & API Albert

Le bot déployé sur Tchap (protocole Matrix) sert d'interface utilisateur et utilise l'Albert API pour comprendre les messages et formuler des réponses pertinentes.

### ♾️ n8n Workflows

Le bot délègue l'exécution des tâches à n8n, une plateforme d'automatisation open-source. Chaque demande déclenche un workflow qui orchestre les différentes étapes nécessaires (appels d'API, requêtes à des bases de données, traitement des réponses...).

### 🔌 Outils via MCP (Model Context Protocol)

Les fonctionnalités externes sont exposées via le protocole MCP, qui définit un standard pour qu'un modèle IA accède à des ressources ou appelle des fonctions externes. Chaque workflow n8n publié équivaut à un "outil" accessible à l'agent IA.

### 🤝 Futur: Dialogue multi-agents via A2A

Le protocole Agent-to-Agent (A2A) est considéré pour préparer l'évolution future. L'architecture est conçue pour accueillir plusieurs agents communiquant entre eux.

## 📊 Niveaux d'évolution Colaig

Ce POC correspond au **Niveau 2: Actions Automatisées** dans le parcours d'évolution de Colaig :

|              |                                                                              |                       |
| ------------ | ---------------------------------------------------------------------------- | --------------------- |
| Niveau       | Description                                                                  | État                  |
| **Niveau 1** | **Documentation Intelligente** - Assistant qui connaît votre documentation   | ✅ Intégré             |
| **Niveau 2** | **Actions Automatisées** - Assistant qui agit sur vos systèmes               | ✅ Ce POC              |
| **Niveau 3** | **Expertise Configurable** - Assistant personnalisable par experts métier    | 🔄 Préparé            |
| **Niveau 4** | **Réseau Collaboratif** - Écosystème d'assistants interconnectés             | 🔄 Architecture prête |
| **Niveau 5** | **Intelligence Collective** - Assistant qui apprend de tous les utilisateurs | 🔜 Futur              |

## 💻 Composants techniques utilisés

|                                   |                                                                            |
| --------------------------------- | -------------------------------------------------------------------------- |
| Composant                         | Rôle / Description                                                         |
| **Bot Tchap + Albert API**        | Chatbot IA intégré à Tchap utilisant l'API Albert pour le NLP              |
| **n8n (workflow engine)**         | Plateforme d'automatisation low-code orchestrant les actions               |
| **MCP (Model Context Protocol)**  | Protocole pour exposer des outils et données à un agent IA                 |
| **A2A (Agent-to-Agent Protocol)** | Protocole pour la communication entre agents IA hétérogènes                |
| **Nextcloud (exemple d'outil)**   | Suite de collaboration illustrant l'intégration avec des services externes |

## 🚀 Guide de démarrage rapide

### Prérequis

*   Accès Tchap: un compte sur la messagerie (idéalement un compte dédié)
*   Accès à l'API Albert: URL d'API et clé/token pour le service
*   Docker pour lancer n8n rapidement via Docker Compose
*   Paramètres des services externes (optionnels): données de connexion Nextcloud, etc.

### Installation

1.  Cloner le dépôt:

```shellscript
git clone https://github.com/nic01asFr/POC-tchap_bot_n8n.git
cd POC-tchap_bot_n8n
```

1.  Configurer les variables d'environnement dans le fichier `.env`:

```javascript
TCHAP_HOMESERVER=https://matrix.tchap.gouv.fr
TCHAP_BOT_USER=votre_bot@domaine.fr
TCHAP_BOT_PASSWORD=votre_mot_de_passe
ALBERT_API_URL=url_api_albert
ALBERT_API_KEY=votre_clé_api
```

1.  Lancer les services avec Docker Compose:

```shellscript
docker-compose up -d
```

1.  Vérifier l'accès à n8n sur <http://localhost:5678>

### Test rapide

1.  Ouvrir un chat sur Tchap avec le compte du bot
2.  Envoyer une question comme: "Peux-tu trouver le dernier compte-rendu de réunion sur Colaig?"
3.  Observer la réponse fournie par le bot
4.  Explorer les workflows dans l'interface n8n pour comprendre et modifier le comportement

## 📈 Cas d'usage

### 📚 Assistant documentaire

Un agent conversationnel capable de rechercher des documents et fournir des informations pertinentes.

### 👥 Agent métier spécialisé

Un assistant dédié à un domaine fonctionnel précis (RH, finances, juridique, etc.).

### 🔍 Agent de recherche transversal

Un agent capable d'agréger des informations de multiples sources pour la décision ou l'analyse.

## 🔒 Sécurité et Conformité

Aligné avec les principes de Colaig, ce POC est conçu selon le principe de "sécurité par défaut":

*   **☁️ Hébergement souverain** sur cloud de confiance ou sur site
*   **🔐 Intégration native** avec Tchap pour la communication sécurisée
*   **📝 Traçabilité complète** des sources d'information et décisions
*   **🛡️ Compatibilité** avec le RGPD et les référentiels du secteur public

## 🔍 Extensions et Contributions

L'architecture modulaire favorise une extension progressive des capacités, avec un effet cumulatif à chaque ajout de fonctionnalité. Chaque nouveau workflow ou outil enrichit l'assistant sans remise en cause de l'existant.

Pour contribuer:

1.  Forkez le dépôt
2.  Créez une nouvelle branche pour vos modifications
3.  Soumettez une pull request

## 📞 Contact

Pour toute information complémentaire, démonstration ou projet pilote, contactez nous à <colaig.assistant@developpement-durable.gouv.fr>.

Construit avec ❤️ pour un avenir numérique intelligent et autonome.
