# Module d'Apprentissage

Le module d'apprentissage est un composant clé du système d'orchestration adaptative MCP qui permet d'améliorer continuellement les performances et la pertinence des compositions. Ce document décrit son fonctionnement et son intégration avec les autres composants du système.

## Objectifs du module d'apprentissage

Le module d'apprentissage poursuit plusieurs objectifs :

1. **Analyser les exécutions réussies** pour identifier les modèles efficaces
2. **Détecter les erreurs et problèmes** dans les compositions existantes
3. **Suggérer des alternatives** lorsqu'une étape échoue
4. **Améliorer les compositions existantes** en fonction des retours d'expérience
5. **Générer des descriptions et exemples** pour les nouvelles compositions
6. **Identifier les opportunités** de créer de nouvelles compositions

## Architecture du module

Le module d'apprentissage est structuré en plusieurs sous-composants spécialisés :

```
┌─────────────────────────────────────────────────────────┐
│                  Module d'Apprentissage                 │
│                                                         │
│  ┌─────────────┐    ┌────────────┐    ┌──────────────┐  │
│  │ Collecteur  │    │ Analyseur  │    │ Générateur   │  │
│  │ de données  │───▶│ de modèles │───▶│ d'alternatives│  │
│  └─────────────┘    └────────────┘    └──────────────┘  │
│          │                 ▲                 ▲          │
│          ▼                 │                 │          │
│  ┌─────────────┐    ┌────────────┐    ┌──────────────┐  │
│  │ Base de     │    │ Évaluateur │    │ Optimiseur   │  │
│  │ connaissances◀───│ de qualité │◀───│ de composition│  │
│  └─────────────┘    └────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 1. Collecteur de données

Le collecteur de données recueille des informations sur les exécutions des compositions et des outils MCP individuels.

#### Fonctionnement

1. Réception des données d'exécution depuis le moniteur
2. Structuration et normalisation des données
3. Filtrage des informations pertinentes
4. Stockage dans la base de connaissances

#### Exemple d'implémentation

```python
class DataCollector:
    def __init__(self, knowledge_base):
        self.knowledge_base = knowledge_base
        
    def collect_execution_data(self, execution_data):
        """Collecte les données d'une exécution"""
        # Extraire les informations principales
        execution_id = execution_data.get("id")
        composition_id = execution_data.get("composition", {}).get("id")
        status = execution_data.get("status")
        start_time = execution_data.get("start_time")
        end_time = execution_data.get("end_time")
        steps = execution_data.get("steps", {})
        
        # Structurer les données
        structured_data = {
            "execution_id": execution_id,
            "composition_id": composition_id,
            "status": status,
            "duration": end_time - start_time if end_time and start_time else None,
            "timestamp": datetime.utcnow().isoformat(),
            "steps": []
        }
        
        # Traiter chaque étape
        for step_id, step_data in steps.items():
            step_info = {
                "step_id": step_id,
                "status": step_data.get("status"),
                "duration": step_data.get("end_time", 0) - step_data.get("start_time", 0),
                "tool": {
                    "server_id": step_data.get("tool", {}).get("server_id"),
                    "tool_id": step_data.get("tool", {}).get("tool_id")
                },
                "error": step_data.get("error")
            }
            structured_data["steps"].append(step_info)
            
        # Stocker les données
        self.knowledge_base.store_execution(structured_data)
        
    def collect_tool_usage(self, tool_data):
        """Collecte les données d'utilisation d'un outil"""
        # Structurer les données
        structured_data = {
            "server_id": tool_data.get("server_id"),
            "tool_id": tool_data.get("tool_id"),
            "status": tool_data.get("status"),
            "duration": tool_data.get("duration"),
            "params": tool_data.get("params"),
            "result": tool_data.get("result"),
            "error": tool_data.get("error"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Stocker les données
        self.knowledge_base.store_tool_usage(structured_data)
```

### 2. Base de connaissances

La base de connaissances stocke toutes les informations collectées et permet leur interrogation efficace.

#### Fonctionnement

1. Stockage structuré des données d'exécution
2. Indexation pour des recherches rapides
3. Agrégation de données statistiques
4. Gestion de la durée de conservation des données

#### Exemple d'implémentation

```python
class KnowledgeBase:
    def __init__(self, config):
        self.config = config
        self.storage_path = config.get("knowledge_base_path", "./knowledge_base")
        self.executions_path = os.path.join(self.storage_path, "executions")
        self.tools_path = os.path.join(self.storage_path, "tools")
        self.patterns_path = os.path.join(self.storage_path, "patterns")
        
        # Créer les répertoires nécessaires
        os.makedirs(self.executions_path, exist_ok=True)
        os.makedirs(self.tools_path, exist_ok=True)
        os.makedirs(self.patterns_path, exist_ok=True)
        
        # Charger les modèles existants
        self.patterns = self._load_patterns()
        
    def store_execution(self, execution_data):
        """Stocke les données d'une exécution"""
        execution_id = execution_data.get("execution_id")
        if not execution_id:
            execution_id = f"execution_{uuid.uuid4().hex[:8]}"
            execution_data["execution_id"] = execution_id
            
        # Sauvegarder dans un fichier JSON
        filename = f"{execution_id}.json"
        with open(os.path.join(self.executions_path, filename), "w") as f:
            json.dump(execution_data, f, indent=2)
            
        # Mettre à jour les statistiques agrégées
        self._update_execution_stats(execution_data)
        
    def store_tool_usage(self, tool_data):
        """Stocke les données d'utilisation d'un outil"""
        server_id = tool_data.get("server_id")
        tool_id = tool_data.get("tool_id")
        
        if not server_id or not tool_id:
            return
            
        # Créer un ID pour cette utilisation
        usage_id = f"usage_{uuid.uuid4().hex[:8]}"
        tool_data["usage_id"] = usage_id
        
        # Sauvegarder dans un fichier JSON
        tool_dir = os.path.join(self.tools_path, f"{server_id}_{tool_id}")
        os.makedirs(tool_dir, exist_ok=True)
        
        filename = f"{usage_id}.json"
        with open(os.path.join(tool_dir, filename), "w") as f:
            json.dump(tool_data, f, indent=2)
            
        # Mettre à jour les statistiques agrégées
        self._update_tool_stats(tool_data)
        
    def store_pattern(self, pattern_data):
        """Stocke un modèle d'exécution"""
        pattern_id = pattern_data.get("pattern_id")
        if not pattern_id:
            pattern_id = f"pattern_{uuid.uuid4().hex[:8]}"
            pattern_data["pattern_id"] = pattern_id
            
        # Sauvegarder dans un fichier JSON
        filename = f"{pattern_id}.json"
        with open(os.path.join(self.patterns_path, filename), "w") as f:
            json.dump(pattern_data, f, indent=2)
            
        # Mettre à jour les modèles en mémoire
        self.patterns[pattern_id] = pattern_data
```

### 3. Analyseur de modèles

L'analyseur de modèles identifie des patterns récurrents dans les exécutions et détecte les causes d'échec.

#### Fonctionnement

1. Analyse des séquences d'exécution réussies
2. Identification des erreurs courantes et leurs causes
3. Détection de corrélations entre paramètres et résultats
4. Génération de modèles d'exécution

#### Exemple d'implémentation

```python
class PatternAnalyzer:
    def __init__(self, knowledge_base):
        self.knowledge_base = knowledge_base
        
    def analyze_successful_executions(self, composition_id, min_count=5):
        """Analyse les exécutions réussies d'une composition"""
        # Récupérer les exécutions réussies
        executions = self.knowledge_base.get_executions_by_composition(
            composition_id, 
            status="success", 
            limit=100
        )
        
        if len(executions) < min_count:
            return None  # Pas assez de données
            
        # Analyser les séquences d'étapes
        step_sequences = []
        for execution in executions:
            sequence = []
            for step in execution.get("steps", []):
                step_info = {
                    "step_id": step.get("step_id"),
                    "server_id": step.get("tool", {}).get("server_id"),
                    "tool_id": step.get("tool", {}).get("tool_id"),
                    "status": step.get("status")
                }
                sequence.append(step_info)
            step_sequences.append(sequence)
            
        # Identifier les séquences les plus fréquentes
        common_sequences = self._find_common_sequences(step_sequences)
        
        # Générer des modèles d'exécution
        patterns = []
        for seq in common_sequences:
            pattern = {
                "pattern_id": f"pattern_{uuid.uuid4().hex[:8]}",
                "composition_id": composition_id,
                "sequence": seq,
                "frequency": seq["count"] / len(executions),
                "created_at": datetime.utcnow().isoformat()
            }
            patterns.append(pattern)
            
        # Stocker les modèles
        for pattern in patterns:
            self.knowledge_base.store_pattern(pattern)
            
        return patterns
        
    def analyze_failures(self, composition_id, min_count=3):
        """Analyse les échecs d'une composition"""
        # Récupérer les exécutions échouées
        executions = self.knowledge_base.get_executions_by_composition(
            composition_id, 
            status="failure", 
            limit=50
        )
        
        if len(executions) < min_count:
            return None  # Pas assez de données
            
        # Analyser les erreurs par étape
        step_errors = {}
        for execution in executions:
            for step in execution.get("steps", []):
                if step.get("status") == "failure":
                    step_id = step.get("step_id")
                    error = step.get("error", {})
                    
                    if step_id not in step_errors:
                        step_errors[step_id] = {"errors": [], "count": 0}
                        
                    step_errors[step_id]["errors"].append(error)
                    step_errors[step_id]["count"] += 1
                    
        # Identifier les erreurs les plus fréquentes
        failure_patterns = []
        for step_id, data in step_errors.items():
            if data["count"] >= min_count:
                error_types = self._categorize_errors(data["errors"])
                
                for error_type, count in error_types.items():
                    if count >= min_count:
                        pattern = {
                            "pattern_id": f"failure_{uuid.uuid4().hex[:8]}",
                            "composition_id": composition_id,
                            "step_id": step_id,
                            "error_type": error_type,
                            "frequency": count / len(executions),
                            "created_at": datetime.utcnow().isoformat()
                        }
                        failure_patterns.append(pattern)
                        
        # Stocker les modèles d'échec
        for pattern in failure_patterns:
            self.knowledge_base.store_pattern(pattern)
            
        return failure_patterns
```

### 4. Générateur d'alternatives

Le générateur d'alternatives propose des solutions de remplacement lorsqu'une étape échoue.

#### Fonctionnement

1. Analyse de l'erreur rencontrée
2. Recherche de solutions alternatives dans la base de connaissances
3. Génération de suggestions adaptées au contexte
4. Évaluation de la pertinence des alternatives

#### Exemple d'implémentation

```python
class AlternativeGenerator:
    def __init__(self, knowledge_base, mcp_registry):
        self.knowledge_base = knowledge_base
        self.mcp_registry = mcp_registry
        
    async def generate_alternative(self, step, error, context):
        """Génère une alternative pour une étape échouée"""
        # Analyser l'erreur
        error_type = self._categorize_error(error)
        
        # Rechercher des modèles d'erreur similaires
        failure_patterns = self.knowledge_base.get_patterns_by_error(
            step.get("server_id"),
            step.get("tool_id"),
            error_type
        )
        
        if failure_patterns:
            # Utiliser les alternatives existantes
            for pattern in failure_patterns:
                if "alternative" in pattern:
                    return self._adapt_alternative(pattern["alternative"], context)
        
        # Si aucune alternative n'est trouvée, essayer de générer une nouvelle
        alternatives = await self._find_similar_tools(step, error, context)
        
        if alternatives:
            # Sélectionner la meilleure alternative
            best_alt = max(alternatives, key=lambda a: a["score"])
            
            # Enregistrer cette alternative pour une utilisation future
            self._store_alternative(step, error_type, best_alt)
            
            return best_alt
            
        return None
        
    async def _find_similar_tools(self, step, error, context):
        """Recherche des outils similaires qui pourraient remplacer l'étape échouée"""
        # Récupérer la description de l'outil échoué
        tool_desc = await self.mcp_registry.get_tool_description(
            step.get("server_id"), 
            step.get("tool_id")
        )
        
        if not tool_desc:
            return []
            
        # Rechercher des outils similaires par fonction
        similar_tools = await self.mcp_registry.search_tools(
            tool_desc.get("description", ""),
            limit=5
        )
        
        # Filtrer pour exclure l'outil d'origine
        similar_tools = [
            t for t in similar_tools 
            if not (t["server_id"] == step.get("server_id") and t["tool_id"] == step.get("tool_id"))
        ]
        
        # Évaluer chaque outil alternatif
        alternatives = []
        for tool in similar_tools:
            score = self._evaluate_alternative_tool(tool, step, error, context)
            if score > 0.5:  # Seuil minimal de pertinence
                alternatives.append({
                    "server_id": tool["server_id"],
                    "tool_id": tool["tool_id"],
                    "params": self._map_params(step.get("params", {}), tool),
                    "score": score
                })
                
        return alternatives
```

### 5. Évaluateur de qualité

L'évaluateur de qualité mesure la performance des compositions et des alternatives générées.

#### Fonctionnement

1. Définition de métriques d'évaluation
2. Calcul de scores de qualité pour les compositions
3. Évaluation des alternatives proposées
4. Identification des compositions à améliorer

#### Exemple d'implémentation

```python
class QualityEvaluator:
    def __init__(self, knowledge_base):
        self.knowledge_base = knowledge_base
        
    def evaluate_composition(self, composition_id):
        """Évalue la qualité d'une composition"""
        # Récupérer les données d'exécution
        executions = self.knowledge_base.get_executions_by_composition(
            composition_id, 
            limit=100
        )
        
        if not executions:
            return None
            
        # Calculer les métriques de base
        success_count = sum(1 for e in executions if e.get("status") == "success")
        total_count = len(executions)
        
        if total_count == 0:
            return None
            
        success_rate = success_count / total_count
        
        # Calculer le temps d'exécution moyen
        durations = [e.get("duration") for e in executions if e.get("duration") is not None]
        avg_duration = sum(durations) / len(durations) if durations else None
        
        # Calculer les métriques par étape
        step_metrics = {}
        for execution in executions:
            for step in execution.get("steps", []):
                step_id = step.get("step_id")
                if step_id not in step_metrics:
                    step_metrics[step_id] = {
                        "success_count": 0,
                        "total_count": 0,
                        "durations": []
                    }
                    
                step_metrics[step_id]["total_count"] += 1
                if step.get("status") == "success":
                    step_metrics[step_id]["success_count"] += 1
                    
                duration = step.get("duration")
                if duration is not None:
                    step_metrics[step_id]["durations"].append(duration)
        
        # Calculer les taux de succès et temps moyens par étape
        for step_id, metrics in step_metrics.items():
            total = metrics["total_count"]
            if total > 0:
                metrics["success_rate"] = metrics["success_count"] / total
                
            durations = metrics["durations"]
            if durations:
                metrics["avg_duration"] = sum(durations) / len(durations)
                
            # Supprimer les listes brutes pour plus de clarté
            del metrics["durations"]
            
        # Construire le résultat final
        quality_score = {
            "composition_id": composition_id,
            "overall": {
                "success_rate": success_rate,
                "avg_duration": avg_duration,
                "total_executions": total_count
            },
            "steps": step_metrics,
            "evaluated_at": datetime.utcnow().isoformat()
        }
        
        return quality_score
        
    def evaluate_alternative(self, alternative, original_step, executions=None):
        """Évalue la qualité d'une alternative proposée"""
        if not executions:
            # Récupérer les données d'exécution où cette alternative a été utilisée
            executions = self.knowledge_base.get_executions_with_alternative(
                alternative.get("server_id"),
                alternative.get("tool_id"),
                limit=20
            )
            
        if not executions:
            # Pas encore de données d'exécution, utiliser une estimation
            return self._estimate_alternative_quality(alternative, original_step)
            
        # Calculer le taux de succès
        success_count = sum(1 for e in executions if e.get("status") == "success")
        total_count = len(executions)
        
        success_rate = success_count / total_count if total_count > 0 else 0
        
        # Calculer le score final
        score = {
            "success_rate": success_rate,
            "sample_size": total_count,
            "confidence": min(0.5 + (total_count / 10) * 0.5, 1.0)  # Confiance croissante avec plus de données
        }
        
        return score
```

### 6. Optimiseur de composition

L'optimiseur de composition améliore les compositions existantes en fonction des données collectées.

#### Fonctionnement

1. Identification des étapes problématiques
2. Proposition de modifications pour améliorer les performances
3. Mise à jour des mappages de paramètres
4. Génération de nouvelles descriptions et exemples

#### Exemple d'implémentation

```python
class CompositionOptimizer:
    def __init__(self, knowledge_base, registry):
        self.knowledge_base = knowledge_base
        self.registry = registry
        
    def optimize_composition(self, composition_id):
        """Optimise une composition existante"""
        # Récupérer la composition
        composition = self.registry.find_composition_by_id(composition_id)
        if not composition:
            return None
            
        # Évaluer la qualité actuelle
        evaluator = QualityEvaluator(self.knowledge_base)
        quality = evaluator.evaluate_composition(composition_id)
        
        if not quality:
            return None
            
        # Copier la composition pour modification
        optimized = copy.deepcopy(composition)
        changes = []
        
        # Identifier les étapes problématiques
        problem_steps = []
        for step_id, metrics in quality.get("steps", {}).items():
            if metrics.get("success_rate", 1.0) < 0.8:  # Seuil de succès problématique
                problem_steps.append(step_id)
                
        # Optimiser chaque étape problématique
        for step_id in problem_steps:
            # Trouver l'étape dans la composition
            step_index = next(
                (i for i, s in enumerate(optimized.get("steps", [])) if s.get("id") == step_id),
                None
            )
            
            if step_index is None:
                continue
                
            step = optimized["steps"][step_index]
            
            # Vérifier les alternatives connues
            alternatives = self.knowledge_base.get_alternatives_for_step(step_id)
            
            if alternatives:
                best_alt = max(alternatives, key=lambda a: a.get("success_rate", 0))
                
                # Remplacer l'étape par la meilleure alternative
                new_step = {
                    "id": step_id,
                    "server_id": best_alt["server_id"],
                    "tool_id": best_alt["tool_id"],
                    "description": step.get("description", ""),
                    "input_mapping": best_alt.get("input_mapping", step.get("input_mapping", {})),
                    "output_mapping": best_alt.get("output_mapping", step.get("output_mapping", {})),
                    "required": step.get("required", True)
                }
                
                optimized["steps"][step_index] = new_step
                
                changes.append({
                    "type": "replace_step",
                    "step_id": step_id,
                    "original": {
                        "server_id": step.get("server_id"),
                        "tool_id": step.get("tool_id")
                    },
                    "new": {
                        "server_id": new_step["server_id"],
                        "tool_id": new_step["tool_id"]
                    }
                })
                
        # Si des changements ont été faits, mettre à jour la composition
        if changes:
            # Incrémenter la version
            optimized["version"] = composition.get("version", 1) + 1
            optimized["updated_at"] = datetime.utcnow().isoformat()
            
            # Enregistrer les modifications
            optimized["optimization_history"] = optimized.get("optimization_history", []) + [{
                "timestamp": datetime.utcnow().isoformat(),
                "changes": changes
            }]
            
            # Enregistrer la composition optimisée
            self.registry.update_composition(optimized)
            
            return {
                "composition_id": composition_id,
                "changes": changes,
                "new_version": optimized["version"]
            }
            
        return {
            "composition_id": composition_id,
            "changes": [],
            "message": "No optimizations needed"
        }
```

## Types d'apprentissage

Le module implémente plusieurs types d'apprentissage :

### 1. Apprentissage par l'expérience

Basé sur l'analyse des exécutions réussies et échouées pour identifier les motifs et les erreurs récurrentes.

### 2. Apprentissage par analogie

Recherche de similarités entre différentes compositions pour appliquer des solutions connues à de nouveaux problèmes.

### 3. Apprentissage par renforcement

Évaluation et adaptation continue des compositions en fonction de leur taux de succès et de leur efficacité.

## Intégration avec l'orchestrateur

Le module d'apprentissage s'intègre étroitement avec l'orchestrateur adaptatif :

```python
class AdaptiveOrchestrator:
    def __init__(self, config, registry):
        self.config = config
        self.registry = registry
        
        # Initialiser la base de connaissances
        self.knowledge_base = KnowledgeBase(config)
        
        # Initialiser le collecteur de données
        self.data_collector = DataCollector(self.knowledge_base)
        
        # Initialiser l'analyseur de modèles
        self.pattern_analyzer = PatternAnalyzer(self.knowledge_base)
        
        # Initialiser le générateur d'alternatives
        self.alternative_generator = AlternativeGenerator(
            self.knowledge_base, 
            registry
        )
        
        # Initialiser l'évaluateur de qualité
        self.quality_evaluator = QualityEvaluator(self.knowledge_base)
        
        # Initialiser l'optimiseur de composition
        self.composition_optimizer = CompositionOptimizer(
            self.knowledge_base,
            registry
        )
        
    async def process_request(self, request, user_id, conversation_id):
        # Traitement normal de la requête
        # ...
        
        # Collecter les données d'exécution
        self.data_collector.collect_execution_data(execution_data)
        
        # Analyse périodique des modèles (à basse fréquence)
        if random.random() < 0.1:  # 10% des requêtes
            asyncio.create_task(self._background_analysis())
            
        # Retourner le résultat
        return result
        
    async def _background_analysis(self):
        """Effectue une analyse en arrière-plan"""
        try:
            # Récupérer les compositions récemment utilisées
            recent_compositions = self.registry.get_recently_used_compositions(limit=5)
            
            for comp in recent_compositions:
                # Analyser les exécutions réussies
                self.pattern_analyzer.analyze_successful_executions(comp["id"])
                
                # Analyser les échecs
                self.pattern_analyzer.analyze_failures(comp["id"])
                
                # Évaluer la qualité
                quality = self.quality_evaluator.evaluate_composition(comp["id"])
                
                # Optimiser si nécessaire
                if quality and quality["overall"]["success_rate"] < 0.8:
                    self.composition_optimizer.optimize_composition(comp["id"])
                    
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse en arrière-plan: {e}")
```

## Configuration et personnalisation

Le module d'apprentissage peut être configuré via plusieurs paramètres :

```yaml
learning:
  # Général
  enabled: true  # Activer l'apprentissage
  knowledge_base_path: "./knowledge_base"  # Chemin pour la base de connaissances
  
  # Collecte de données
  max_executions_stored: 1000  # Nombre max d'exécutions à stocker
  max_tool_usages_stored: 5000  # Nombre max d'utilisations d'outils à stocker
  
  # Analyse de modèles
  min_executions_for_pattern: 5  # Nombre min d'exécutions pour identifier un modèle
  min_failures_for_pattern: 3  # Nombre min d'échecs pour identifier un modèle d'erreur
  
  # Génération d'alternatives
  alternative_similarity_threshold: 0.7  # Seuil de similarité pour les alternatives
  max_alternatives_per_step: 3  # Nombre max d'alternatives par étape
  
  # Optimisation
  min_success_rate_for_validation: 0.7  # Taux de succès min pour valider une composition
  optimization_interval: 86400  # Intervalle entre les optimisations (en secondes)
```

## Extension du module

Le module d'apprentissage peut être étendu de plusieurs façons :

### 1. Ajout de nouvelles sources de données

Le collecteur de données peut être étendu pour recueillir des informations supplémentaires, comme les retours des utilisateurs.

### 2. Nouveaux algorithmes d'analyse

L'analyseur de modèles peut être amélioré avec des algorithmes plus sophistiqués, comme l'apprentissage par renforcement ou les réseaux de neurones.

### 3. Stratégies d'optimisation avancées

L'optimiseur de composition peut être étendu avec des stratégies plus avancées, comme l'optimisation multi-objectif ou l'optimisation génétique.

## Considérations de performances

Le module d'apprentissage est conçu pour minimiser son impact sur les performances :

1. **Analyse en arrière-plan** : Les analyses intensives sont effectuées en arrière-plan
2. **Échantillonnage** : Seule une partie des exécutions est analysée en profondeur
3. **Mise en cache** : Les résultats d'analyse sont mis en cache pour éviter les calculs répétés

## Gestion des données

Le module gère efficacement les données d'apprentissage :

1. **Rotation des logs** : Les anciennes données sont périodiquement supprimées
2. **Agrégation** : Les données brutes sont agrégées pour réduire l'espace de stockage
3. **Compression** : Les données peuvent être compressées pour optimiser le stockage 