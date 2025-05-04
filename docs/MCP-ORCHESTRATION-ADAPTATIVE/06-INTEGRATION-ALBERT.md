# Intégration avec Albert Tchapbot

Ce document décrit comment le système d'orchestration adaptative MCP s'intègre à l'architecture d'Albert Tchapbot et détaille les modifications nécessaires pour activer cette fonctionnalité.

## Architecture d'intégration

L'intégration du système d'orchestration adaptative avec Albert Tchapbot se fait selon le schéma suivant :

```
┌───────────────────┐      ┌─────────────────────┐
│                   │      │                     │
│  Albert Tchapbot  │◄────►│  MCP Registry       │
│                   │      │                     │
└─────────┬─────────┘      └───────────┬─────────┘
          │                            │
          │                            │
          ▼                            ▼
┌─────────────────────┐      ┌─────────────────────┐
│                     │      │                     │
│  Orchestrateur      │◄────►│  MCP Servers        │
│  Adaptatif          │      │                     │
└─────────┬─────────┬─┘      └─────────────────────┘
          │         │
          │         │
          ▼         ▼
┌─────────────┐ ┌───────────────┐
│             │ │               │
│ Registre de │ │ Module        │
│ Compositions│ │ d'Apprentissage│
└─────────────┘ └───────────────┘
```

### Points d'intégration

1. **Interface d'Albert avec l'orchestrateur** : Point de connexion principal où Albert transmet les requêtes à l'orchestrateur adaptatif.
2. **Accès au MCP Registry** : L'orchestrateur communique avec le registry MCP standard pour accéder aux outils disponibles.
3. **Gestion du contexte de conversation** : Albert fournit le contexte de conversation à l'orchestrateur pour un traitement adapté au fil des échanges.
4. **Retour des résultats** : L'orchestrateur renvoie les résultats des compositions exécutées à Albert pour présentation à l'utilisateur.

## Modifications dans Albert Tchapbot

### 1. Configuration de l'orchestrateur

Ajoutez la configuration de l'orchestrateur adaptatif dans le fichier `config.yaml` d'Albert :

```yaml
mcp:
  registry:
    url: "http://localhost:5000/api"
    api_key: "votre_clé_api"
  
  adaptive_orchestrator:
    enabled: true
    composition_registry_path: "./data/compositions"
    knowledge_base_path: "./data/knowledge_base"
    max_composition_steps: 10
    execution_timeout: 30  # secondes
    learning:
      enabled: true
      min_executions_for_pattern: 5
```

### 2. Initialisation de l'orchestrateur

Modifiez le fichier principal d'Albert pour initialiser l'orchestrateur adaptatif lors du démarrage :

```python
# Dans albert/app.py ou équivalent

from albert_mcp_adaptive_orchestrator import AdaptiveOrchestrator

class AlbertTchapBot:
    def __init__(self, config):
        self.config = config
        
        # Initialiser le client MCP Registry standard
        self.mcp_registry = MCPRegistryClient(
            config['mcp']['registry']['url'],
            config['mcp']['registry']['api_key']
        )
        
        # Initialiser l'orchestrateur adaptatif
        if config['mcp'].get('adaptive_orchestrator', {}).get('enabled', False):
            self.orchestrator = AdaptiveOrchestrator(
                config['mcp']['adaptive_orchestrator'],
                self.mcp_registry
            )
        else:
            self.orchestrator = None
            
        # Autres initialisations...
```

### 3. Modification du traitement des messages

Modifiez la fonction de traitement des messages pour utiliser l'orchestrateur adaptatif :

```python
# Dans albert/handlers/message_handler.py ou équivalent

async def handle_message(message, user_id, conversation_id):
    # Analyser le message pour détecter l'intention
    intent = analyze_intent(message)
    
    # Si l'orchestrateur adaptatif est disponible et que l'intention nécessite des outils MCP
    if app.orchestrator and requires_mcp_tools(intent):
        # Préparer le contexte de conversation
        context = await get_conversation_context(conversation_id)
        
        # Traiter la requête via l'orchestrateur adaptatif
        result = await app.orchestrator.process_request(
            message, 
            user_id, 
            conversation_id,
            context=context
        )
        
        # Si l'orchestrateur a traité la requête avec succès
        if result and result.get('status') == 'success':
            # Préparer et envoyer la réponse
            response = format_orchestrator_response(result)
            return response
    
    # Si l'orchestrateur n'est pas disponible ou n'a pas pu traiter la requête,
    # utiliser le traitement standard d'Albert
    return await standard_message_processing(message, user_id, conversation_id)
```

### 4. Accès au contexte de conversation

Implémentez une fonction pour récupérer le contexte de conversation :

```python
# Dans albert/services/context_service.py ou équivalent

async def get_conversation_context(conversation_id):
    """Récupère le contexte d'une conversation pour l'orchestrateur adaptatif"""
    
    # Récupérer l'historique récent de la conversation
    history = await conversation_store.get_conversation_history(
        conversation_id,
        limit=10  # Limiter aux 10 derniers échanges
    )
    
    # Récupérer les variables de contexte associées à cette conversation
    variables = await context_store.get_conversation_variables(conversation_id)
    
    # Récupérer les fichiers associés à cette conversation
    files = await file_store.get_conversation_files(conversation_id)
    
    # Construire le contexte pour l'orchestrateur
    context = {
        "conversation_id": conversation_id,
        "history": history,
        "variables": variables,
        "files": files
    }
    
    return context
```

### 5. Formatage des réponses

Implémentez une fonction pour formater les réponses de l'orchestrateur :

```python
# Dans albert/services/response_formatter.py ou équivalent

def format_orchestrator_response(result):
    """Formate la réponse de l'orchestrateur pour l'utilisateur"""
    
    # Extraire les données principales
    data = result.get('data', {})
    execution_info = result.get('execution_info', {})
    
    # Formater la réponse principale
    if 'message' in data:
        response = data['message']
    else:
        # Construire une réponse basée sur le résultat
        response = construct_response_from_data(data)
    
    # Si des fichiers ont été générés, ajouter les références
    if 'files' in data and data['files']:
        file_references = format_file_references(data['files'])
        response += "\n\n" + file_references
    
    # Si demandé en mode debug, ajouter des informations d'exécution
    if app.config.get('debug_mode', False):
        debug_info = format_debug_info(execution_info)
        response += "\n\n" + debug_info
    
    return response
```

## Hooks et points d'extension

L'intégration offre plusieurs points d'extension pour personnaliser le comportement :

### 1. Pré-traitement des requêtes

```python
@app.before_orchestrator_request
async def preprocess_request(request, context):
    """Pré-traitement des requêtes avant l'orchestrateur"""
    # Enrichir le contexte avec des données spécifiques à Albert
    context['user_preferences'] = await get_user_preferences(context['user_id'])
    
    # Modifier la requête si nécessaire
    if "fichiers récents" in request.lower():
        request = f"Liste des fichiers récents pour l'utilisateur {context['user_id']}"
    
    return request, context
```

### 2. Post-traitement des résultats

```python
@app.after_orchestrator_execution
async def postprocess_result(result, context):
    """Post-traitement des résultats de l'orchestrateur"""
    # Enregistrer l'activité pour analyse
    await activity_logger.log_orchestrator_activity(
        user_id=context['user_id'],
        composition_id=result.get('composition_id'),
        success=result.get('status') == 'success'
    )
    
    # Enrichir le résultat avec des informations supplémentaires
    if result.get('status') == 'success' and 'data' in result:
        result['data']['processed_by'] = 'adaptive_orchestrator'
    
    return result
```

### 3. Gestion des erreurs

```python
@app.orchestrator_error_handler
async def handle_orchestrator_error(error, request, context):
    """Gestion personnalisée des erreurs de l'orchestrateur"""
    # Journaliser l'erreur
    logger.error(f"Erreur d'orchestration: {error}", 
                 extra={"request": request, "user_id": context.get('user_id')})
    
    # Déterminer si une réponse spécifique est nécessaire
    if "timeout" in str(error).lower():
        return "L'opération a pris trop de temps. Pourriez-vous simplifier votre demande ?"
    
    if "permission" in str(error).lower():
        return "Vous n'avez pas les autorisations nécessaires pour effectuer cette action."
    
    # Réponse par défaut
    return "Je n'ai pas pu traiter votre demande. Pourriez-vous la reformuler différemment ?"
```

## Personnalisation avancée

### 1. Mapping d'intentions personnalisées

Vous pouvez définir des mappings d'intentions spécifiques à votre cas d'usage dans un fichier JSON :

```json
{
  "intent_patterns": [
    {
      "name": "recherche_documents",
      "patterns": [
        "trouve des documents sur {sujet}",
        "recherche {sujet} dans les documents",
        "documents concernant {sujet}"
      ],
      "parameters": [
        {
          "name": "sujet",
          "type": "string",
          "required": true
        }
      ]
    },
    {
      "name": "creation_rapport",
      "patterns": [
        "génère un rapport sur {projet}",
        "crée un rapport pour {projet}",
        "rapport {projet} {periode}"
      ],
      "parameters": [
        {
          "name": "projet",
          "type": "string",
          "required": true
        },
        {
          "name": "periode",
          "type": "string",
          "required": false,
          "default": "ce mois-ci"
        }
      ]
    }
  ]
}
```

Ce fichier doit être spécifié dans la configuration :

```yaml
mcp:
  adaptive_orchestrator:
    intent_patterns_path: "./config/intent_patterns.json"
```

### 2. Personnalisation des transformateurs de données

Vous pouvez créer des transformateurs de données personnalisés pour des cas d'usage spécifiques :

```python
# Dans albert/orchestrator/transformers.py

from albert_mcp_adaptive_orchestrator import DataTransformer, register_transformer

@register_transformer("document_to_presentation")
class DocumentToPresentationTransformer(DataTransformer):
    """Transforme les données d'un document en présentation"""
    
    def transform(self, input_data, config=None):
        """
        Transforme un document en structure de présentation
        
        Args:
            input_data: Données du document (dict)
            config: Configuration optionnelle
            
        Returns:
            Structure de présentation (dict)
        """
        if not input_data or 'content' not in input_data:
            return None
            
        content = input_data['content']
        title = input_data.get('title', 'Présentation')
        
        # Extraire les sections principales
        sections = self._extract_sections(content)
        
        # Créer la structure de la présentation
        presentation = {
            'title': title,
            'slides': []
        }
        
        # Créer la diapositive de titre
        presentation['slides'].append({
            'type': 'title',
            'content': {
                'title': title,
                'subtitle': input_data.get('subtitle', '')
            }
        })
        
        # Créer une diapositive pour chaque section
        for section in sections:
            presentation['slides'].append({
                'type': 'content',
                'content': {
                    'title': section['title'],
                    'bullets': section['key_points']
                }
            })
            
        return presentation
        
    def _extract_sections(self, content):
        # Logique pour extraire les sections et points clés
        # ...
        return sections
```

## Tests et validation

### 1. Tests unitaires

Ajoutez des tests pour vérifier l'intégration :

```python
# Dans tests/test_orchestrator_integration.py

import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_orchestrator():
    # Créer un mock de l'orchestrateur
    orchestrator = MagicMock()
    orchestrator.process_request.return_value = {
        'status': 'success',
        'data': {'message': 'Résultat de test'},
        'composition_id': 'test-composition-123'
    }
    return orchestrator

@pytest.mark.asyncio
async def test_message_handler_with_orchestrator(mock_orchestrator):
    # Remplacer l'orchestrateur de l'application par le mock
    with patch('albert.app.orchestrator', mock_orchestrator):
        # Tester le gestionnaire de messages
        response = await handle_message(
            "Recherche des documents sur l'IA",
            user_id="user123",
            conversation_id="conv456"
        )
        
        # Vérifier que l'orchestrateur a été appelé
        mock_orchestrator.process_request.assert_called_once()
        
        # Vérifier que la réponse est correcte
        assert "Résultat de test" in response

@pytest.mark.asyncio
async def test_orchestrator_error_handling(mock_orchestrator):
    # Configurer le mock pour simuler une erreur
    mock_orchestrator.process_request.side_effect = Exception("Timeout error")
    
    # Remplacer l'orchestrateur de l'application par le mock
    with patch('albert.app.orchestrator', mock_orchestrator):
        # Tester le gestionnaire de messages avec une erreur
        response = await handle_message(
            "Recherche des documents sur l'IA",
            user_id="user123",
            conversation_id="conv456"
        )
        
        # Vérifier que le traitement standard a été utilisé comme fallback
        assert response != "Résultat de test"
```

### 2. Tests d'intégration

Créez des scénarios de test pour valider l'intégration complète :

```python
# Dans tests/integration/test_end_to_end.py

import pytest
from albert.app import initialize_app

@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_orchestration():
    # Initialiser l'application avec la configuration de test
    app = initialize_app('./config/test_config.yaml')
    
    # Créer une session de test
    async with app.test_session() as session:
        # Envoyer une requête qui devrait être traitée par l'orchestrateur
        response = await session.process_message(
            "Génère un rapport sur le projet Alpha pour le dernier trimestre",
            user_id="test_user",
            conversation_id="test_conversation"
        )
        
        # Vérifier que la réponse contient un rapport
        assert "rapport" in response.lower()
        assert "projet Alpha" in response
        assert "trimestre" in response
        
        # Vérifier que l'orchestrateur a bien été utilisé
        assert app.orchestrator.last_processed_request is not None
```

## Déploiement et configuration en production

### 1. Configuration recommandée

Pour un environnement de production, utilisez la configuration suivante :

```yaml
mcp:
  registry:
    url: "https://mcp-registry.votredomaine.com/api"
    api_key: "${MCP_REGISTRY_API_KEY}"  # Variable d'environnement
  
  adaptive_orchestrator:
    enabled: true
    composition_registry_path: "/data/albert/compositions"
    knowledge_base_path: "/data/albert/knowledge_base"
    max_composition_steps: 15
    execution_timeout: 60  # secondes
    intent_patterns_path: "/etc/albert/intent_patterns.json"
    
    learning:
      enabled: true
      min_executions_for_pattern: 10
      optimization_interval: 86400  # Une fois par jour
      max_executions_stored: 5000
```

### 2. Surveillance et maintenance

Mettez en place des métriques et alertes pour surveiller le système :

- **Taux de succès des compositions** : Surveillez le pourcentage de requêtes traitées avec succès
- **Temps d'exécution** : Alertes si les temps d'exécution dépassent un seuil
- **Utilisation de l'espace disque** : Surveillez la croissance de la base de connaissances
- **Santé de l'orchestrateur** : Vérifiez périodiquement que l'orchestrateur répond

### 3. Rotation des données

Configurez une politique de rotation pour les données d'apprentissage :

```bash
#!/bin/bash
# /etc/cron.weekly/albert-data-cleanup

# Archiver les anciennes données d'exécution (plus de 90 jours)
find /data/albert/knowledge_base/executions -type f -name "*.json" -mtime +90 \
  -exec tar -rf /data/albert/archives/executions_$(date +%Y%m%d).tar {} \; \
  -exec rm {} \;

# Compresser les archives
gzip /data/albert/archives/executions_$(date +%Y%m%d).tar

# Nettoyer les compositions inutilisées depuis longtemps
python3 /opt/albert/scripts/cleanup_unused_compositions.py
```

## Exemples d'utilisation

### Exemple 1 : Récupération et traitement de données

```python
# Exemple d'utilisation de l'orchestrateur pour récupérer et traiter des données

# Message utilisateur
message = "Peux-tu analyser les ventes du dernier trimestre et me faire un résumé ?"

# Traitement par Albert avec orchestrateur
response = await handle_message(message, user_id="user123", conversation_id="conv456")

# Exemple de réponse générée après orchestration
"""
Voici l'analyse des ventes du dernier trimestre (Q2 2023) :

Tendances principales :
- Augmentation globale de 12% par rapport au trimestre précédent
- Les produits de la gamme Premium ont connu la plus forte croissance (+23%)
- La région Sud-Ouest est en baisse de 5% et nécessite une attention particulière

Top 3 des produits :
1. Solution Enterprise X1 - 1,2M€ (↑18%)
2. Module Analytics Pro - 820K€ (↑15%)
3. Service Cloud Basic - 750K€ (↓3%)

J'ai généré un rapport détaillé que vous pouvez consulter ici : [Rapport Q2 2023](/files/rapport_ventes_q2_2023.pdf)
"""
```

### Exemple 2 : Automatisation de processus

```python
# Exemple d'automatisation d'un processus via l'orchestrateur

# Message utilisateur
message = """Peux-tu m'aider avec le processus d'onboarding pour le nouveau client Acme Corp ? 
Les informations sont dans leur email d'hier et le contrat est sur le drive partagé."""

# Traitement par Albert avec orchestrateur
response = await handle_message(message, user_id="user123", conversation_id="conv456")

# Exemple de réponse générée après orchestration
"""
J'ai préparé l'onboarding pour Acme Corp :

1. J'ai créé un espace client dans Grist avec les informations du contrat
2. J'ai extrait les contacts principaux de l'email : Jean Martin (CTO) et Sophie Dubois (PM)
3. J'ai généré un document d'accueil personnalisé
4. J'ai programmé la réunion de kickoff pour lundi à 10h00 avec l'équipe
5. J'ai préparé le projet dans Trello avec les tâches initiales

Tous les documents sont disponibles dans le dossier client : [Dossier Acme Corp](/clients/acme-corp/)
"""
```

## Dépannage

### Problèmes courants et solutions

| Problème | Cause possible | Solution |
|----------|----------------|----------|
| L'orchestrateur n'est pas utilisé | Configuration désactivée | Vérifiez `enabled: true` dans le fichier config.yaml |
| Erreurs d'initialisation | Chemins incorrects | Vérifiez que les chemins des répertoires existent et sont accessibles |
| Timeout fréquents | Compositions trop complexes | Augmentez `execution_timeout` ou réduisez `max_composition_steps` |
| Erreurs de mémoire | Trop de données stockées | Nettoyez les anciennes données ou augmentez les ressources serveur |
| Compositions non créées | Erreur d'analyse d'intention | Vérifiez les modèles d'intention dans le fichier de configuration |

### Journalisation et diagnostic

Configurez une journalisation détaillée pour résoudre les problèmes :

```yaml
logging:
  orchestrator:
    level: "INFO"  # Utiliser "DEBUG" pour résoudre les problèmes
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: "/var/log/albert/orchestrator.log"
    max_size: 10485760  # 10 Mo
    backup_count: 5
```

Pour diagnostiquer un problème avec l'orchestrateur :

```bash
# Activer temporairement le mode debug
sed -i 's/level: "INFO"/level: "DEBUG"/' /etc/albert/config.yaml

# Redémarrer le service
systemctl restart albert-tchapbot

# Observer les logs en temps réel
tail -f /var/log/albert/orchestrator.log

# Effectuer une requête de test
curl -X POST http://localhost:8000/api/message \
     -H "Content-Type: application/json" \
     -d '{"message": "Analyse les données du projet X", "user_id": "debug", "conversation_id": "test"}'

# Après diagnostic, revenir au niveau INFO
sed -i 's/level: "DEBUG"/level: "INFO"/' /etc/albert/config.yaml
systemctl restart albert-tchapbot
``` 