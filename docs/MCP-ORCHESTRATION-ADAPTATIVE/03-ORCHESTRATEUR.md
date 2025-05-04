# Orchestrateur Adaptatif MCP

L'orchestrateur adaptatif est le composant central du système d'orchestration adaptative MCP. Ce document décrit son fonctionnement interne, ses interfaces et comment l'étendre.

## Fonctionnement général

L'orchestrateur adaptatif est responsable de :

1. Analyser les requêtes des utilisateurs pour en extraire l'intention
2. Rechercher des compositions existantes correspondant à cette intention
3. Exécuter les compositions existantes ou décomposer la tâche en étapes plus simples
4. Gérer le flux de données entre les différentes étapes d'une composition
5. Collecter des données pour améliorer les compositions futures

## Architecture interne

L'orchestrateur est composé de plusieurs sous-modules spécialisés :

```
┌─────────────────────────────────────────────────────┐
│                 Orchestrateur Adaptatif             │
│                                                     │
│  ┌─────────────┐    ┌────────────┐    ┌──────────┐  │
│  │ Analyseur   │    │ Moteur     │    │ Moniteur │  │
│  │ d'intention │───▶│ d'exécution│───▶│          │  │
│  └─────────────┘    └────────────┘    └──────────┘  │
│          │                 ▲               │        │
│          ▼                 │               ▼        │
│  ┌─────────────┐    ┌────────────┐    ┌──────────┐  │
│  │ Gestionnaire│    │Transformeur│    │ Logger   │  │
│  │ de contexte │◀──▶│ de données │    │          │  │
│  └─────────────┘    └────────────┘    └──────────┘  │
└─────────────────────────────────────────────────────┘
```

### 1. Analyseur d'intention

L'analyseur d'intention est responsable d'extraire le type d'intention et les paramètres à partir de la requête de l'utilisateur.

#### Fonctionnement

1. Analyse lexicale et syntaxique de la requête
2. Identification des entités et des actions
3. Classification de l'intention principale
4. Extraction des paramètres explicites et implicites

#### Exemple d'implémentation

```python
class IntentionAnalyzer:
    def __init__(self, patterns=None):
        self.patterns = patterns or self._load_default_patterns()
        
    def analyze(self, request):
        """Analyse une requête et retourne l'intention identifiée"""
        # Extraction basée sur des règles ou des patterns
        for pattern_name, pattern in self.patterns.items():
            if pattern.match(request.content):
                params = pattern.extract_params(request.content)
                return Intention(type=pattern_name, params=params)
        
        # Si aucun pattern ne correspond, utiliser une approche heuristique
        tokens = self._tokenize(request.content)
        action = self._identify_action(tokens)
        entities = self._identify_entities(tokens)
        
        # Mapper vers un type d'intention connu
        intent_type = self._map_to_intent_type(action, entities)
        params = self._extract_params(tokens, intent_type)
        
        return Intention(type=intent_type, params=params)
```

### 2. Gestionnaire de contexte

Le gestionnaire de contexte maintient l'état de la conversation et les informations contextuelles nécessaires à l'exécution des compositions.

#### Fonctionnement

1. Stockage des variables de session
2. Gestion des références aux entités mentionnées précédemment
3. Mémorisation du contexte entre les différentes requêtes
4. Résolution des références ambiguës

#### Exemple d'implémentation

```python
class ContextManager:
    def __init__(self, memory_tool):
        self.memory_tool = memory_tool  # Outil MCP Memory pour le stockage persistant
        
    async def load_context(self, user_id, conversation_id):
        """Charge le contexte pour une conversation donnée"""
        context_key = f"context:{user_id}:{conversation_id}"
        result = await self.memory_tool.execute({"action": "get", "key": context_key})
        
        if result.get("value"):
            return json.loads(result["value"])
        return {"entities": {}, "variables": {}, "history": []}
        
    async def save_context(self, user_id, conversation_id, context):
        """Sauvegarde le contexte de la conversation"""
        context_key = f"context:{user_id}:{conversation_id}"
        await self.memory_tool.execute({
            "action": "set", 
            "key": context_key, 
            "value": json.dumps(context)
        })
        
    def update_context(self, context, intention, results):
        """Met à jour le contexte avec les résultats d'une exécution"""
        # Mettre à jour l'historique
        context["history"].append({
            "intention": intention.to_dict(),
            "timestamp": time.time()
        })
        
        # Extraire et stocker les entités des résultats
        new_entities = self._extract_entities(results)
        context["entities"].update(new_entities)
        
        # Mettre à jour les variables
        for key, value in results.items():
            if isinstance(value, (str, int, float, bool, list, dict)):
                context["variables"][key] = value
                
        return context
```

### 3. Moteur d'exécution

Le moteur d'exécution est responsable de l'exécution des compositions et des séquences d'outils MCP.

#### Fonctionnement

1. Sélection des outils MCP à exécuter
2. Préparation des paramètres pour chaque outil
3. Exécution séquentielle ou parallèle des outils
4. Gestion des dépendances entre les outils
5. Traitement des résultats

#### Exemple d'implémentation

```python
class ExecutionEngine:
    def __init__(self, mcp_registry):
        self.registry = mcp_registry
        
    async def execute_composition(self, composition, params, context):
        """Exécute une composition avec les paramètres donnés"""
        results = {}
        current_params = params.copy()
        
        for step in composition.steps:
            # Préparer les paramètres pour cette étape
            step_params = self._prepare_params(step, current_params, results, context)
            
            # Exécuter l'outil
            tool = await self.registry.get_tool(step.server_id, step.tool_id)
            if not tool:
                raise ExecutionError(f"Outil non trouvé: {step.server_id}/{step.tool_id}")
                
            result = await self.registry.execute_tool(step.server_id, step.tool_id, step_params)
            
            # Traiter le résultat
            processed_result = self._process_result(step, result)
            results[step.id] = processed_result
            
            # Mettre à jour les paramètres courants avec le résultat
            if step.output_mapping:
                for output_key, param_key in step.output_mapping.items():
                    if output_key in processed_result:
                        current_params[param_key] = processed_result[output_key]
            else:
                # Par défaut, ajouter tous les résultats aux paramètres
                current_params.update(processed_result)
                
        return results
        
    async def execute_steps(self, steps, params, context):
        """Exécute une séquence d'étapes ad-hoc"""
        # Implémentation similaire à execute_composition, mais pour des étapes
        # qui ne font pas partie d'une composition formelle
        # ...
```

### 4. Transformeur de données

Le transformeur de données est responsable de la transformation et du mappage des données entre les différentes étapes d'une composition.

#### Fonctionnement

1. Extraction des données pertinentes des résultats
2. Mappage des clés de données selon les besoins des outils
3. Conversion des formats de données
4. Agrégation des résultats partiels

#### Exemple d'implémentation

```python
class DataTransformer:
    def __init__(self):
        self.converters = {
            "str_to_list": lambda x: x.split(",") if isinstance(x, str) else x,
            "list_to_str": lambda x: ",".join(x) if isinstance(x, list) else str(x),
            "json_parse": lambda x: json.loads(x) if isinstance(x, str) else x,
            "json_stringify": lambda x: json.dumps(x) if not isinstance(x, str) else x,
            # Autres convertisseurs...
        }
        
    def transform(self, data, mapping, transformations=None):
        """Transforme les données selon le mapping et les transformations spécifiés"""
        result = {}
        
        # Appliquer le mapping de clés
        for source_key, target_key in mapping.items():
            if source_key in data:
                result[target_key] = data[source_key]
                
        # Appliquer les transformations
        if transformations:
            for key, transformer in transformations.items():
                if key in result:
                    if isinstance(transformer, str) and transformer in self.converters:
                        result[key] = self.converters[transformer](result[key])
                    elif callable(transformer):
                        result[key] = transformer(result[key])
                        
        return result
```

### 5. Moniteur

Le moniteur observe l'exécution des compositions et collecte des données pour le module d'apprentissage.

#### Fonctionnement

1. Mesure du temps d'exécution des étapes
2. Détection des erreurs et des exceptions
3. Enregistrement des résultats intermédiaires
4. Collecte de statistiques d'utilisation

#### Exemple d'implémentation

```python
class Monitor:
    def __init__(self, learning_module):
        self.learning_module = learning_module
        self.current_executions = {}
        
    def start_monitoring(self, execution_id, composition=None):
        """Commence à surveiller une exécution"""
        self.current_executions[execution_id] = {
            "start_time": time.time(),
            "steps": {},
            "composition": composition,
            "status": "running"
        }
        
    def record_step(self, execution_id, step_id, status, result=None, error=None):
        """Enregistre les informations sur une étape d'exécution"""
        if execution_id not in self.current_executions:
            return
            
        execution = self.current_executions[execution_id]
        execution["steps"][step_id] = {
            "status": status,
            "timestamp": time.time(),
            "result": result,
            "error": error
        }
        
    def end_monitoring(self, execution_id, status, final_result=None):
        """Termine la surveillance d'une exécution et envoie les données au module d'apprentissage"""
        if execution_id not in self.current_executions:
            return
            
        execution = self.current_executions[execution_id]
        execution["end_time"] = time.time()
        execution["status"] = status
        execution["final_result"] = final_result
        
        # Envoyer les données au module d'apprentissage
        if self.learning_module:
            self.learning_module.learn_from_execution(execution)
            
        # Nettoyer
        del self.current_executions[execution_id]
```

## Interface de l'orchestrateur

L'orchestrateur expose une API simple pour faciliter son intégration avec Albert Tchapbot.

### Méthodes principales

#### 1. process_request

```python
async def process_request(self, request, user_id, conversation_id):
    """
    Traite une requête utilisateur.
    
    Args:
        request (str): La requête de l'utilisateur
        user_id (str): L'identifiant de l'utilisateur
        conversation_id (str): L'identifiant de la conversation
        
    Returns:
        dict: Le résultat du traitement
    """
```

Cette méthode est le point d'entrée principal de l'orchestrateur. Elle analyse la requête, trouve ou crée une composition appropriée, l'exécute et retourne le résultat.

#### 2. get_compositions

```python
def get_compositions(self, intent_type=None, limit=10):
    """
    Récupère les compositions disponibles.
    
    Args:
        intent_type (str, optional): Type d'intention pour filtrer les compositions
        limit (int, optional): Nombre maximum de compositions à retourner
        
    Returns:
        list: Liste des compositions correspondantes
    """
```

Cette méthode permet de récupérer les compositions existantes, éventuellement filtrées par type d'intention.

#### 3. execute_composition

```python
async def execute_composition(self, composition_id, params, user_id, conversation_id):
    """
    Exécute une composition spécifique.
    
    Args:
        composition_id (str): L'identifiant de la composition à exécuter
        params (dict): Les paramètres à passer à la composition
        user_id (str): L'identifiant de l'utilisateur
        conversation_id (str): L'identifiant de la conversation
        
    Returns:
        dict: Le résultat de l'exécution
    """
```

Cette méthode permet d'exécuter directement une composition spécifique, sans passer par l'analyse de la requête.

## Configuration de l'orchestrateur

L'orchestrateur peut être configuré via plusieurs paramètres :

```yaml
orchestrator:
  # Général
  max_steps_per_composition: 10  # Nombre max d'étapes par composition
  execution_timeout: 30  # Timeout en secondes
  
  # Analyse d'intention
  intent_patterns_path: "./patterns"  # Chemin vers les patterns d'intention
  default_intent_type: "generic"  # Type d'intention par défaut
  
  # Exécution
  parallel_execution: false  # Exécution parallèle des étapes indépendantes
  retry_failed_steps: true  # Réessayer les étapes échouées
  max_retries: 3  # Nombre max de tentatives
  
  # Apprentissage
  learning_enabled: true  # Activer l'apprentissage
  min_success_rate: 0.7  # Taux de succès minimum pour valider une composition
  min_executions: 5  # Nombre min d'exécutions avant validation
```

## Extension de l'orchestrateur

L'orchestrateur est conçu pour être extensible. Voici comment étendre ses principales fonctionnalités :

### Ajout de nouveaux patterns d'intention

Les patterns d'intention sont définis dans des fichiers JSON dans le répertoire `patterns`. Pour ajouter un nouveau pattern :

1. Créez un fichier JSON (par exemple, `email_patterns.json`) :

```json
{
  "patterns": [
    {
      "name": "send_email",
      "regex": "envo(ie|yer) (un )?mail|courrier|email à (.+?) avec (?:le sujet|comme sujet) ['\"]*(.+?)['\"]*",
      "params": {
        "recipient": "$3",
        "subject": "$4"
      }
    },
    {
      "name": "read_emails",
      "regex": "(lis|affiche|montre) mes (derniers|récents|nouveaux)? (mails|emails|courriers)",
      "params": {
        "count": "10"
      }
    }
  ]
}
```

2. L'orchestrateur chargera automatiquement ces patterns au démarrage.

### Ajout de nouveaux transformateurs de données

Pour ajouter un nouveau transformateur de données :

1. Créez une fonction de transformation :

```python
def extract_first_item(data):
    """Extrait le premier élément d'une liste ou retourne la valeur telle quelle"""
    if isinstance(data, list) and len(data) > 0:
        return data[0]
    return data
```

2. Enregistrez-la auprès du transformeur de données :

```python
orchestrator.data_transformer.converters["extract_first"] = extract_first_item
```

### Création de templates de composition

Vous pouvez créer des templates de composition pour les tâches courantes :

1. Créez un fichier JSON dans le répertoire `compositions/templates` :

```json
{
  "id": "template_list_and_summarize",
  "name": "Lister et résumer des fichiers",
  "description": "Liste les fichiers dans un répertoire et génère un résumé pour chacun",
  "intent_type": "list_and_summarize",
  "steps": [
    {
      "id": "list_files",
      "server_id": "filesystem",
      "tool_id": "list_directory",
      "input_mapping": {
        "directory": "path"
      }
    },
    {
      "id": "read_and_summarize",
      "server_id": "filesystem",
      "tool_id": "read_file",
      "input_mapping": {
        "file_path": "list_files.files[i]"
      },
      "iterations": "list_files.files"
    }
  ]
}
```

2. Ce template pourra être utilisé comme base pour créer de nouvelles compositions.

## Considérations de performances

L'orchestrateur a été conçu en tenant compte des performances :

1. **Mise en cache** : Les résultats des outils fréquemment utilisés sont mis en cache
2. **Exécution optimisée** : Les étapes indépendantes peuvent être exécutées en parallèle
3. **Timeouts** : Des timeouts sont appliqués à chaque étape pour éviter les blocages
4. **Limitations** : Le nombre d'étapes et la profondeur de récursion sont limités

Pour les cas d'utilisation intensifs, considérez les ajustements suivants :

- Augmentez la limite de mémoire pour l'orchestrateur
- Activez l'exécution parallèle des étapes indépendantes
- Utilisez des serveurs MCP plus performants
- Mettez en place un système de mise en cache externe 