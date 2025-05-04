# Registre de Compositions

Le registre de compositions est un composant essentiel du système d'orchestration adaptative MCP. Il gère le stockage, l'indexation et la recherche des compositions créées par le système.

## Fonctionnalités principales

Le registre de compositions offre les fonctionnalités suivantes :

1. **Stockage persistant** des compositions validées et en cours d'apprentissage
2. **Indexation vectorielle** pour la recherche sémantique de compositions
3. **Gestion du cycle de vie** des compositions (création, validation, mise à jour, suppression)
4. **Exposition des compositions** comme outils MCP de haut niveau
5. **Versionnement** des compositions pour suivre leur évolution

## Structure d'une composition

Une composition est définie par la structure suivante :

```json
{
  "id": "composition_123456",
  "name": "Recherche et résumé d'emails",
  "description": "Recherche des emails par sujet et génère un résumé de chacun",
  "intent_type": "email_search_summarize",
  "version": 2,
  "created_at": "2025-03-15T14:30:00Z",
  "updated_at": "2025-03-18T09:45:00Z",
  "status": "validated",
  "stats": {
    "usage_count": 15,
    "success_rate": 0.93,
    "avg_execution_time": 2.4
  },
  "steps": [
    {
      "id": "search_emails",
      "server_id": "gmail",
      "tool_id": "search_emails",
      "description": "Recherche des emails par sujet",
      "input_mapping": {
        "query": "subject"
      },
      "output_mapping": {
        "emails": "email_list"
      },
      "required": true
    },
    {
      "id": "summarize_emails",
      "server_id": "memory",
      "tool_id": "process_text",
      "description": "Génère un résumé pour chaque email",
      "input_mapping": {
        "text": "email_list[i].body",
        "operation": "'summarize'"
      },
      "iterations": "email_list",
      "output_mapping": {
        "result": "email_list[i].summary"
      },
      "required": true
    }
  ],
  "input_schema": {
    "type": "object",
    "properties": {
      "subject": {
        "type": "string",
        "description": "Sujet de l'email à rechercher"
      }
    },
    "required": ["subject"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "email_list": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "id": { "type": "string" },
            "subject": { "type": "string" },
            "from": { "type": "string" },
            "date": { "type": "string" },
            "body": { "type": "string" },
            "summary": { "type": "string" }
          }
        }
      }
    }
  },
  "examples": [
    {
      "input": { "subject": "réunion" },
      "output": {
        "email_list": [
          {
            "id": "msg123",
            "subject": "Réunion de projet",
            "from": "jean.dupont@example.com",
            "date": "2025-03-14T10:00:00Z",
            "body": "Bonjour, nous avons une réunion de projet demain...",
            "summary": "Rappel de la réunion de projet prévue demain."
          }
        ]
      }
    }
  ]
}
```

### Explication des champs

- **id**: Identifiant unique de la composition
- **name**: Nom lisible par un humain
- **description**: Description détaillée de la fonctionnalité de la composition
- **intent_type**: Type d'intention associée à cette composition
- **version**: Numéro de version de la composition
- **created_at/updated_at**: Horodatages de création et dernière modification
- **status**: État de la composition (learning, validated, deprecated)
- **stats**: Statistiques d'utilisation de la composition
- **steps**: Liste ordonnée des étapes de la composition
  - **id**: Identifiant unique de l'étape
  - **server_id**: Identifiant du serveur MCP
  - **tool_id**: Identifiant de l'outil MCP
  - **description**: Description de l'étape
  - **input_mapping**: Mappage des paramètres d'entrée
  - **output_mapping**: Mappage des résultats
  - **iterations**: Champ pour itérer sur une liste (optionnel)
  - **required**: Indique si l'étape est obligatoire
- **input_schema**: Schéma JSON des paramètres d'entrée attendus
- **output_schema**: Schéma JSON des résultats retournés
- **examples**: Exemples d'utilisation de la composition

## Implémentation du registre

### Classe principale

```python
class CompositionRegistry:
    def __init__(self, config, mcp_registry):
        self.config = config
        self.mcp_registry = mcp_registry
        self.base_path = config.get("compositions_path", "./compositions")
        self.vector_index = self._init_vector_index()
        self.compositions = {}
        self._load_compositions()
        
    def _init_vector_index(self):
        """Initialise l'index vectoriel pour la recherche sémantique"""
        try:
            import faiss
            from sentence_transformers import SentenceTransformer
            
            # Charger le modèle d'embedding
            model = SentenceTransformer(self.config.get("embedding_model", "all-MiniLM-L6-v2"))
            
            # Créer l'index FAISS
            embedding_size = model.get_sentence_embedding_dimension()
            index = faiss.IndexFlatL2(embedding_size)
            
            return {
                "model": model,
                "index": index,
                "ids": [],
                "texts": []
            }
        except ImportError:
            logger.warning("FAISS ou SentenceTransformer non disponible. La recherche sémantique sera désactivée.")
            return None
            
    def _load_compositions(self):
        """Charge les compositions depuis le stockage"""
        # Charger les compositions validées
        validated_path = os.path.join(self.base_path, "validated")
        if os.path.exists(validated_path):
            for filename in os.listdir(validated_path):
                if filename.endswith(".json"):
                    try:
                        with open(os.path.join(validated_path, filename), "r") as f:
                            composition = json.load(f)
                            self.register_composition(composition, index=True)
                    except Exception as e:
                        logger.error(f"Erreur lors du chargement de la composition {filename}: {e}")
                        
        # Charger les compositions en apprentissage
        learning_path = os.path.join(self.base_path, "learning")
        if os.path.exists(learning_path):
            for filename in os.listdir(learning_path):
                if filename.endswith(".json"):
                    try:
                        with open(os.path.join(learning_path, filename), "r") as f:
                            composition = json.load(f)
                            self.register_composition(composition, index=False)
                    except Exception as e:
                        logger.error(f"Erreur lors du chargement de la composition {filename}: {e}")
```

### Méthodes de gestion des compositions

```python
def register_composition(self, composition, index=True):
    """
    Enregistre une nouvelle composition dans le registre.
    
    Args:
        composition (dict): La composition à enregistrer
        index (bool): Si True, indexe la composition pour la recherche sémantique
    """
    # Vérifier que la composition a un ID
    if "id" not in composition:
        composition["id"] = f"composition_{uuid.uuid4().hex[:8]}"
        
    # Vérifier que la composition a un type d'intention
    if "intent_type" not in composition:
        composition["intent_type"] = "generic"
        
    # Ajouter les timestamps
    if "created_at" not in composition:
        composition["created_at"] = datetime.utcnow().isoformat()
    composition["updated_at"] = datetime.utcnow().isoformat()
    
    # Enregistrer la composition
    self.compositions[composition["id"]] = composition
    
    # Indexer la composition pour la recherche sémantique
    if index and self.vector_index:
        self._index_composition(composition)
        
    # Si la composition est validée, l'exposer comme outil MCP
    if composition.get("status") == "validated":
        self._expose_as_mcp_tool(composition)
        
    # Sauvegarder la composition sur disque
    self._save_composition(composition)
    
    return composition["id"]

def _index_composition(self, composition):
    """Indexe une composition pour la recherche sémantique"""
    if not self.vector_index:
        return
        
    # Créer un texte représentatif de la composition
    text = f"{composition['name']}. {composition['description']}. {composition['intent_type']}"
    
    # Générer l'embedding
    embedding = self.vector_index["model"].encode([text])[0]
    
    # Ajouter à l'index
    self.vector_index["index"].add(np.array([embedding], dtype=np.float32))
    self.vector_index["ids"].append(composition["id"])
    self.vector_index["texts"].append(text)
    
def _expose_as_mcp_tool(self, composition):
    """Expose une composition comme un outil MCP de haut niveau"""
    tool_id = f"composition_{composition['id']}"
    
    # Créer une description de l'outil
    description = f"{composition['name']} - {composition['description']}"
    
    # Enregistrer la composition comme un outil MCP
    self.mcp_registry.register_custom_tool(
        server_id="compositions",
        tool_id=tool_id,
        name=composition["name"],
        description=description,
        input_schema=composition["input_schema"],
        output_schema=composition["output_schema"],
        handler=lambda params: self.execute_composition(composition["id"], params)
    )
    
def _save_composition(self, composition):
    """Sauvegarde une composition sur disque"""
    # Déterminer le répertoire de destination
    if composition.get("status") == "validated":
        directory = os.path.join(self.base_path, "validated")
    else:
        directory = os.path.join(self.base_path, "learning")
        
    # Créer le répertoire s'il n'existe pas
    os.makedirs(directory, exist_ok=True)
    
    # Sauvegarder la composition
    filename = f"{composition['id']}.json"
    with open(os.path.join(directory, filename), "w") as f:
        json.dump(composition, f, indent=2)
```

### Méthodes de recherche de compositions

```python
def find_composition_by_id(self, composition_id):
    """
    Recherche une composition par son ID.
    
    Args:
        composition_id (str): L'ID de la composition à rechercher
        
    Returns:
        dict or None: La composition trouvée, ou None
    """
    return self.compositions.get(composition_id)
    
def find_compositions_by_intent(self, intent_type, validated_only=True):
    """
    Recherche des compositions par type d'intention.
    
    Args:
        intent_type (str): Le type d'intention à rechercher
        validated_only (bool): Si True, ne retourne que les compositions validées
        
    Returns:
        list: Liste des compositions correspondantes
    """
    result = []
    for comp in self.compositions.values():
        if comp.get("intent_type") == intent_type:
            if not validated_only or comp.get("status") == "validated":
                result.append(comp)
    return result
    
def search_compositions(self, query, top_k=5, validated_only=True):
    """
    Recherche des compositions par similarité sémantique.
    
    Args:
        query (str): La requête de recherche
        top_k (int): Nombre maximum de résultats
        validated_only (bool): Si True, ne retourne que les compositions validées
        
    Returns:
        list: Liste des compositions correspondantes
    """
    if not self.vector_index:
        # Fallback sur une recherche par mots-clés si l'index vectoriel n'est pas disponible
        return self._keyword_search(query, top_k, validated_only)
        
    # Générer l'embedding de la requête
    query_embedding = self.vector_index["model"].encode([query])[0]
    
    # Rechercher les compositions les plus similaires
    distances, indices = self.vector_index["index"].search(np.array([query_embedding], dtype=np.float32), top_k * 2)
    
    # Filtrer les résultats
    results = []
    for idx in indices[0]:
        comp_id = self.vector_index["ids"][idx]
        comp = self.compositions.get(comp_id)
        if comp and (not validated_only or comp.get("status") == "validated"):
            results.append(comp)
            if len(results) >= top_k:
                break
                
    return results
    
def _keyword_search(self, query, top_k=5, validated_only=True):
    """Recherche par mots-clés (fallback)"""
    # Tokenisation simple de la requête
    query_tokens = set(query.lower().split())
    
    # Calculer un score pour chaque composition
    scored_compositions = []
    for comp in self.compositions.values():
        if validated_only and comp.get("status") != "validated":
            continue
            
        # Texte à comparer
        comp_text = f"{comp.get('name', '')} {comp.get('description', '')} {comp.get('intent_type', '')}"
        comp_tokens = set(comp_text.lower().split())
        
        # Score = nombre de tokens en commun
        score = len(query_tokens.intersection(comp_tokens))
        if score > 0:
            scored_compositions.append((score, comp))
            
    # Trier par score décroissant et retourner les top_k
    scored_compositions.sort(reverse=True)
    return [comp for _, comp in scored_compositions[:top_k]]
```

### Méthodes d'exécution et de mise à jour

```python
async def execute_composition(self, composition_id, params):
    """
    Exécute une composition avec les paramètres donnés.
    
    Args:
        composition_id (str): L'ID de la composition à exécuter
        params (dict): Les paramètres d'entrée
        
    Returns:
        dict: Les résultats de l'exécution
    """
    # Récupérer la composition
    composition = self.find_composition_by_id(composition_id)
    if not composition:
        raise ValueError(f"Composition non trouvée: {composition_id}")
        
    # Valider les paramètres d'entrée
    self._validate_input(params, composition.get("input_schema", {}))
    
    # Créer un contexte d'exécution
    execution_context = {
        "params": params,
        "results": {},
        "start_time": time.time()
    }
    
    # Exécuter les étapes
    try:
        for step in composition.get("steps", []):
            result = await self._execute_step(step, execution_context)
            execution_context["results"][step["id"]] = result
    except Exception as e:
        # Mettre à jour les statistiques
        self._update_stats(composition, False, time.time() - execution_context["start_time"])
        raise ExecutionError(f"Erreur lors de l'exécution de la composition: {e}")
        
    # Préparer le résultat final
    final_result = self._prepare_output(execution_context, composition.get("output_schema", {}))
    
    # Mettre à jour les statistiques
    self._update_stats(composition, True, time.time() - execution_context["start_time"])
    
    return final_result
    
def _update_stats(self, composition, success, execution_time):
    """Met à jour les statistiques d'une composition"""
    if "stats" not in composition:
        composition["stats"] = {"usage_count": 0, "success_count": 0, "total_time": 0}
        
    composition["stats"]["usage_count"] = composition["stats"].get("usage_count", 0) + 1
    if success:
        composition["stats"]["success_count"] = composition["stats"].get("success_count", 0) + 1
    composition["stats"]["total_time"] = composition["stats"].get("total_time", 0) + execution_time
    
    # Calculer le taux de succès
    composition["stats"]["success_rate"] = composition["stats"]["success_count"] / composition["stats"]["usage_count"]
    
    # Calculer le temps d'exécution moyen
    composition["stats"]["avg_execution_time"] = composition["stats"]["total_time"] / composition["stats"]["usage_count"]
    
    # Sauvegarder les changements
    composition["updated_at"] = datetime.utcnow().isoformat()
    self._save_composition(composition)
    
    # Vérifier si la composition doit être validée
    if (composition.get("status") != "validated" and
        composition["stats"]["usage_count"] >= self.config.get("min_executions", 5) and
        composition["stats"]["success_rate"] >= self.config.get("min_success_rate", 0.7)):
        self._validate_composition(composition)
        
def _validate_composition(self, composition):
    """Valide une composition"""
    # Changer le statut
    composition["status"] = "validated"
    
    # Réindexer la composition
    self._index_composition(composition)
    
    # Exposer comme outil MCP
    self._expose_as_mcp_tool(composition)
    
    # Sauvegarder
    self._save_composition(composition)
    
    logger.info(f"Composition validée: {composition['id']} ({composition['name']})")
```

## Types de compositions

Le registre gère différents types de compositions :

### 1. Templates de compositions

Les templates sont des modèles de compositions définis manuellement. Ils servent de base pour créer de nouvelles compositions et définissent les structures communes pour certains types de tâches.

**Exemples de templates** :
- Recherche et traitement de données
- Séquence d'actions sur des fichiers
- Séquence d'opérations de manipulation de texte

### 2. Compositions en apprentissage

Les compositions en apprentissage sont créées automatiquement par l'orchestrateur adaptatif lorsqu'il décompose une tâche. Elles sont stockées temporairement pour analyse et peuvent être promues au statut "validé" si elles sont utilisées avec succès plusieurs fois.

### 3. Compositions validées

Les compositions validées ont prouvé leur efficacité (taux de succès élevé sur plusieurs exécutions) et sont exposées comme des outils MCP de haut niveau. Elles peuvent être directement utilisées par l'orchestrateur pour traiter des requêtes similaires à l'avenir.

## Cycle de vie d'une composition

```
┌────────────┐     ┌─────────────────┐     ┌────────────┐     ┌─────────────┐
│ Création   │────▶│ Apprentissage   │────▶│ Validation │────▶│ Utilisation │
└────────────┘     └─────────────────┘     └────────────┘     └─────────────┘
                          │                                          │
                          │                                          │
                          ▼                                          ▼
                    ┌──────────┐                             ┌─────────────┐
                    │ Abandon  │                             │ Dépréciation│
                    └──────────┘                             └─────────────┘
```

1. **Création** : Une composition est créée soit manuellement (template), soit automatiquement par l'orchestrateur.
2. **Apprentissage** : La composition est utilisée et ses performances sont mesurées.
3. **Validation** : Si la composition atteint un taux de succès suffisant, elle est validée.
4. **Utilisation** : La composition validée est exposée comme outil MCP et utilisée par l'orchestrateur.
5. **Dépréciation** : Si la composition devient obsolète ou si ses performances se dégradent, elle peut être dépréciée.

## Considérations de sécurité

Le registre de compositions implémente plusieurs mécanismes de sécurité :

1. **Validation des entrées** : Les paramètres d'entrée sont validés selon le schéma défini
2. **Isolation des exécutions** : Chaque exécution est isolée dans son propre contexte
3. **Limitations des ressources** : Des timeouts et des limites sont appliqués aux exécutions
4. **Traçabilité** : Toutes les exécutions sont journalisées pour audit

## Évolutivité et maintenance

Le registre est conçu pour être évolutif et facile à maintenir :

1. **Stockage modulaire** : Les compositions sont stockées dans des fichiers JSON individuels
2. **Indexation flexible** : L'index vectoriel peut être remplacé par d'autres méthodes d'indexation
3. **Versionnement** : Les compositions sont versionnées pour suivre leur évolution
4. **Nettoyage automatique** : Les compositions peu utilisées ou avec un faible taux de succès sont périodiquement nettoyées 