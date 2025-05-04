from typing import Dict, List, Optional, Any, Union
import json
import copy
from datetime import datetime
import uuid

from ..models.composition import Composition, CompositionStep, CompositionStatus
from ..registry.storage import CompositionStorage
from .performance_analyzer import PerformanceAnalyzer
from ..config import settings
from loguru import logger


class CompositionOptimizer:
    """
    Optimiseur de compositions MCP.
    Génère des suggestions d'amélioration et applique des optimisations aux compositions.
    """
    
    def __init__(self, 
                 storage: Optional[CompositionStorage] = None,
                 analyzer: Optional[PerformanceAnalyzer] = None):
        """
        Initialise l'optimiseur de compositions.
        
        Args:
            storage: Gestionnaire de stockage (crée un nouveau si None)
            analyzer: Analyseur de performance (crée un nouveau si None)
        """
        self.storage = storage or CompositionStorage()
        self.analyzer = analyzer or PerformanceAnalyzer(storage)
    
    def optimize_composition(self, composition_id: str) -> Dict[str, Any]:
        """
        Optimise une composition en fonction de l'analyse de ses performances.
        
        Args:
            composition_id: ID de la composition à optimiser
        
        Returns:
            Résultat de l'optimisation avec la nouvelle composition
        """
        # Charger la composition
        composition = self.storage.load_composition(composition_id)
        if not composition:
            logger.error(f"Composition {composition_id} non trouvée")
            return {"success": False, "error": "Composition non trouvée"}
        
        # Analyser les performances
        analysis = self.analyzer.analyze_composition(composition_id)
        if not analysis.get("success") or not analysis.get("metrics_found"):
            logger.warning(f"Pas assez de données pour optimiser {composition_id}")
            return {
                "success": False,
                "error": "Pas assez de données pour l'optimisation",
                "composition_id": composition_id,
                "name": composition.name
            }
        
        # Générer une nouvelle version optimisée
        optimized_composition = self._create_optimized_version(composition, analysis)
        
        # Sauvegarder la nouvelle version
        new_id = optimized_composition.id
        self.storage.save_composition(optimized_composition)
        
        logger.info(f"Composition {composition_id} optimisée => nouvelle version: {new_id}")
        
        return {
            "success": True,
            "original_id": composition_id,
            "optimized_id": new_id,
            "optimized_composition": optimized_composition.dict(),
            "optimizations": self._get_optimizations_summary(composition, optimized_composition, analysis)
        }
    
    def suggest_optimizations(self, composition_id: str) -> Dict[str, Any]:
        """
        Suggère des optimisations pour une composition sans les appliquer.
        
        Args:
            composition_id: ID de la composition
        
        Returns:
            Suggestions d'optimisation
        """
        # Charger la composition
        composition = self.storage.load_composition(composition_id)
        if not composition:
            logger.error(f"Composition {composition_id} non trouvée")
            return {"success": False, "error": "Composition non trouvée"}
        
        # Analyser les performances
        analysis = self.analyzer.analyze_composition(composition_id)
        if not analysis.get("success") or not analysis.get("metrics_found"):
            logger.warning(f"Pas assez de données pour suggérer des optimisations pour {composition_id}")
            return {
                "success": False, 
                "error": "Pas assez de données pour l'analyse",
                "composition_id": composition_id,
                "name": composition.name
            }
        
        # Générer les suggestions d'optimisation
        suggestions = self._generate_optimization_suggestions(composition, analysis)
        
        return {
            "success": True,
            "composition_id": composition_id,
            "name": composition.name,
            "status": composition.status.value,
            "suggestions": suggestions,
            "overall_score": analysis.get("overall_score", 0)
        }
    
    def optimize_multiple_compositions(self, composition_ids: List[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Optimise plusieurs compositions en une seule opération.
        
        Args:
            composition_ids: Liste des IDs de compositions (toutes si None)
        
        Returns:
            Dictionnaire des résultats d'optimisation par ID de composition
        """
        # Si aucun ID spécifié, récupérer toutes les compositions en apprentissage
        if not composition_ids:
            compositions = self.storage.list_compositions(status=CompositionStatus.LEARNING)
            composition_ids = [c.id for c in compositions]
        
        results = {}
        for comp_id in composition_ids:
            try:
                # Uniquement essayer d'optimiser, ignorer les échecs
                result = self.optimize_composition(comp_id)
                results[comp_id] = result
            except Exception as e:
                logger.error(f"Erreur lors de l'optimisation de {comp_id}: {e}")
                results[comp_id] = {
                    "success": False,
                    "error": str(e),
                    "composition_id": comp_id
                }
        
        return results
    
    def _create_optimized_version(self, 
                                 composition: Composition, 
                                 analysis: Dict[str, Any]) -> Composition:
        """
        Crée une version optimisée d'une composition.
        
        Args:
            composition: La composition originale
            analysis: Résultats de l'analyse de performance
        
        Returns:
            La composition optimisée
        """
        # Créer une copie profonde
        optimized = copy.deepcopy(composition)
        
        # Assigner un nouvel ID
        optimized.id = str(uuid.uuid4())
        
        # Incrémenter la version
        version_parts = optimized.version.split(".")
        if len(version_parts) >= 3:
            # Incrémenter la version mineure
            version_parts[1] = str(int(version_parts[1]) + 1)
            version_parts[2] = "0"  # Réinitialiser le patch
        else:
            # Fallback si format inconnu
            version_parts = ["0", "1", "0"]
        
        optimized.version = ".".join(version_parts)
        
        # Mettre à jour les timestamps
        now = datetime.now()
        optimized.created_at = now
        optimized.updated_at = now
        
        # Conserver le statut LEARNING ou promouvoir depuis le DRAFT
        if optimized.status == CompositionStatus.DRAFT:
            optimized.status = CompositionStatus.LEARNING
        
        # Appliquer les optimisations
        self._apply_retry_optimizations(optimized, analysis)
        self._apply_parallel_execution_optimizations(optimized, analysis)
        self._apply_timeout_optimizations(optimized, analysis)
        
        return optimized
    
    def _apply_retry_optimizations(self, 
                                  composition: Composition, 
                                  analysis: Dict[str, Any]) -> None:
        """
        Applique des optimisations liées aux stratégies de retry.
        
        Args:
            composition: La composition à optimiser
            analysis: Résultats de l'analyse de performance
        """
        step_performance = analysis.get("step_performance", {})
        
        for step in composition.steps:
            step_data = step_performance.get(step.id)
            if not step_data:
                continue
            
            # Si le taux de succès est faible et qu'il n'y a pas déjà de stratégie de retry
            if step_data.get("success_rate", 1.0) < 0.9 and not step.retry_strategy:
                # Ajouter une stratégie de retry
                step.retry_strategy = {
                    "max_retries": 3,
                    "delay_ms": 1000,
                    "backoff_factor": 2.0
                }
                logger.info(f"Ajout d'une stratégie de retry pour l'étape {step.id}")
            
            # Si le taux de succès est toujours faible malgré une stratégie existante
            elif step_data.get("success_rate", 1.0) < 0.7 and step.retry_strategy:
                # Augmenter le nombre de tentatives
                current_max = step.retry_strategy.get("max_retries", 3)
                if current_max < 5:
                    step.retry_strategy["max_retries"] = current_max + 1
                    logger.info(f"Augmentation du nombre de retries pour l'étape {step.id} à {current_max + 1}")
    
    def _apply_parallel_execution_optimizations(self, 
                                              composition: Composition, 
                                              analysis: Dict[str, Any]) -> None:
        """
        Applique des optimisations liées à l'exécution parallèle.
        
        Args:
            composition: La composition à optimiser
            analysis: Résultats de l'analyse de performance
        """
        # Cette optimisation est plus complexe et nécessiterait une analyse
        # approfondie du graphe d'exécution pour identifier les étapes indépendantes
        # Pour l'instant, c'est un placeholder pour une future implémentation
        pass
    
    def _apply_timeout_optimizations(self, 
                                    composition: Composition, 
                                    analysis: Dict[str, Any]) -> None:
        """
        Applique des optimisations liées aux timeouts.
        
        Args:
            composition: La composition à optimiser
            analysis: Résultats de l'analyse de performance
        """
        step_performance = analysis.get("step_performance", {})
        
        for step in composition.steps:
            step_data = step_performance.get(step.id)
            if not step_data:
                continue
            
            avg_duration = step_data.get("avg_duration_ms", 0)
            max_duration = step_data.get("max_duration_ms", 0)
            
            if avg_duration > 0:
                # Définir un timeout adapté: max(2 * avg_duration, max_duration * 1.2, 5000 ms)
                recommended_timeout = max(
                    int(avg_duration * 2),
                    int(max_duration * 1.2),
                    5000  # Minimum 5 secondes
                )
                
                # Limiter à 120 secondes maximum par défaut
                recommended_timeout = min(recommended_timeout, 120000)
                
                # Convertir en secondes pour la composition
                recommended_timeout_sec = recommended_timeout // 1000
                
                # Si le timeout actuel est significativement différent
                current_timeout = step.timeout_seconds
                if current_timeout < recommended_timeout_sec * 0.7 or current_timeout > recommended_timeout_sec * 1.5:
                    step.timeout_seconds = recommended_timeout_sec
                    logger.info(f"Ajustement du timeout pour l'étape {step.id} à {recommended_timeout_sec}s")
    
    def _generate_optimization_suggestions(self, 
                                          composition: Composition, 
                                          analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Génère des suggestions d'optimisation sans les appliquer.
        
        Args:
            composition: La composition à analyser
            analysis: Résultats de l'analyse de performance
        
        Returns:
            Liste des suggestions d'optimisation
        """
        suggestions = []
        
        # Réutiliser les recommandations de l'analyse
        recommendations = analysis.get("recommendations", [])
        for rec in recommendations:
            if rec["type"] == "step" and "step_id" in rec:
                step_id = rec["step_id"]
                step = next((s for s in composition.steps if s.id == step_id), None)
                
                if step:
                    # Convertir en suggestion d'optimisation
                    suggestion = {
                        "type": "step_optimization",
                        "step_id": step_id,
                        "step_name": step.name,
                        "priority": rec["priority"],
                        "message": rec["message"],
                        "details": rec["details"],
                        "current_config": {}
                    }
                    
                    # Ajouter des détails spécifiques
                    if "retry" in rec["details"].lower():
                        suggestion["optimization_type"] = "retry_strategy"
                        suggestion["current_config"]["retry_strategy"] = step.retry_strategy
                        
                        if not step.retry_strategy:
                            suggestion["suggested_config"] = {
                                "max_retries": 3,
                                "delay_ms": 1000,
                                "backoff_factor": 2.0
                            }
                    
                    elif "temps d'exécution" in rec["details"].lower():
                        suggestion["optimization_type"] = "timeout"
                        suggestion["current_config"]["timeout_seconds"] = step.timeout_seconds
                        
                        # Calculer un timeout suggéré
                        step_data = analysis.get("step_performance", {}).get(step_id, {})
                        avg_duration = step_data.get("avg_duration_ms", 0)
                        
                        if avg_duration > 0:
                            suggested_timeout = max(int(avg_duration * 2), 5000) // 1000
                            suggestion["suggested_config"] = {
                                "timeout_seconds": suggested_timeout
                            }
                    
                    suggestions.append(suggestion)
            
            elif rec["type"] == "global":
                # Suggestions globales
                suggestion = {
                    "type": "global_optimization",
                    "priority": rec["priority"],
                    "message": rec["message"],
                    "details": rec["details"]
                }
                
                suggestions.append(suggestion)
        
        return suggestions
    
    def _get_optimizations_summary(self, 
                                  original: Composition, 
                                  optimized: Composition, 
                                  analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Génère un résumé des optimisations appliquées.
        
        Args:
            original: La composition originale
            optimized: La composition optimisée
            analysis: Résultats de l'analyse de performance
        
        Returns:
            Résumé des optimisations
        """
        summary = {
            "retry_strategies_added": [],
            "retry_strategies_modified": [],
            "timeouts_adjusted": [],
            "version_increment": f"{original.version} -> {optimized.version}"
        }
        
        # Vérifier les changements dans les stratégies de retry
        for i, step in enumerate(optimized.steps):
            original_step = original.steps[i]
            
            # Vérifier les ajouts de stratégies de retry
            if not original_step.retry_strategy and step.retry_strategy:
                summary["retry_strategies_added"].append({
                    "step_id": step.id,
                    "step_name": step.name,
                    "strategy": step.retry_strategy
                })
            
            # Vérifier les modifications de stratégies existantes
            elif original_step.retry_strategy and step.retry_strategy and original_step.retry_strategy != step.retry_strategy:
                summary["retry_strategies_modified"].append({
                    "step_id": step.id,
                    "step_name": step.name,
                    "old_strategy": original_step.retry_strategy,
                    "new_strategy": step.retry_strategy
                })
            
            # Vérifier les ajustements de timeout
            if original_step.timeout_seconds != step.timeout_seconds:
                summary["timeouts_adjusted"].append({
                    "step_id": step.id,
                    "step_name": step.name,
                    "old_timeout": f"{original_step.timeout_seconds}s",
                    "new_timeout": f"{step.timeout_seconds}s"
                })
        
        # Calculer le nombre total de changements
        total_changes = (
            len(summary["retry_strategies_added"]) +
            len(summary["retry_strategies_modified"]) +
            len(summary["timeouts_adjusted"])
        )
        
        summary["total_changes"] = total_changes
        summary["optimization_date"] = datetime.now().isoformat()
        
        return summary
    
    def optimize_retry_strategies(self, composition: Composition, step_metrics: Dict[str, Dict[str, Any]]) -> Composition:
        """
        Optimise les stratégies de retry pour chaque étape de la composition.
        
        Args:
            composition: La composition à optimiser
            step_metrics: Métriques pour chaque étape
        
        Returns:
            La composition avec des stratégies de retry optimisées
        """
        optimized = copy.deepcopy(composition)
        changes_made = False
        
        for step in optimized.steps:
            if step.id not in step_metrics:
                continue
            
            step_data = step_metrics[step.id]
            
            # Si le taux de succès est inférieur à 90% et qu'il n'y a pas de stratégie de retry
            if step_data.get("success_rate", 1.0) < 0.9 and not step.retry_strategy:
                logger.info(f"Ajout d'une stratégie de retry pour l'étape '{step.name}' (ID: {step.id})")
                step.retry_strategy = {
                    "max_retries": 3,
                    "delay_ms": 1000
                }
                changes_made = True
            
            # Si le taux de succès est inférieur à 70% malgré les retry, augmenter max_retries
            elif step_data.get("success_rate", 1.0) < 0.7 and step.retry_strategy:
                current_max = step.retry_strategy.get("max_retries", 3)
                logger.info(f"Augmentation du nombre de retry pour l'étape '{step.name}' (ID: {step.id})")
                step.retry_strategy["max_retries"] = current_max + 1
                changes_made = True
        
        if changes_made:
            logger.info("Stratégies de retry optimisées")
        
        return optimized
        
    def optimize_fallback_strategies(self, composition: Composition, step_metrics: Dict[str, Dict[str, Any]]) -> Composition:
        """
        Optimise les stratégies de fallback pour les étapes à risque.
        
        Args:
            composition: La composition à optimiser
            step_metrics: Métriques pour chaque étape
        
        Returns:
            La composition avec des stratégies de fallback optimisées
        """
        optimized = copy.deepcopy(composition)
        changes_made = False
        
        for step in optimized.steps:
            if step.id not in step_metrics:
                continue
            
            step_data = step_metrics[step.id]
            
            # Si le taux d'échec est élevé même avec des retry
            if step_data.get("error_rate", 0.0) > 0.3 and step.retry_strategy:
                # Vérifier si la stratégie de fallback existe déjà
                if not step.retry_strategy.get("fallback"):
                    # Déterminer le type de fallback approprié
                    fallback_type = self._determine_fallback_type(step, composition)
                    
                    if fallback_type == "default_value":
                        # Suggérer une valeur par défaut basée sur les résultats précédents réussis
                        default_value = self._generate_default_value(step, step_data)
                        logger.info(f"Ajout d'un fallback 'default_value' pour l'étape '{step.name}' (ID: {step.id})")
                        
                        step.retry_strategy["fallback"] = {
                            "type": "default_value",
                            "value": default_value
                        }
                        changes_made = True
                    
                    elif fallback_type == "alternative_step":
                        # Chercher une étape alternative potentielle
                        alternative_step_id = self._find_alternative_step(step, composition)
                        
                        if alternative_step_id:
                            logger.info(f"Ajout d'un fallback 'alternative_step' pour l'étape '{step.name}' (ID: {step.id})")
                            step.retry_strategy["fallback"] = {
                                "type": "alternative_step",
                                "step_id": alternative_step_id
                            }
                            changes_made = True
                    
                    elif fallback_type == "skip":
                        # Si l'étape peut être ignorée sans trop d'impact
                        logger.info(f"Ajout d'un fallback 'skip' pour l'étape '{step.name}' (ID: {step.id})")
                        step.retry_strategy["fallback"] = {
                            "type": "skip"
                        }
                        changes_made = True
        
        if changes_made:
            logger.info("Stratégies de fallback optimisées")
        
        return optimized
        
    def _determine_fallback_type(self, step: CompositionStep, composition: Composition) -> str:
        """
        Détermine le type de fallback le plus approprié pour une étape.
        
        Args:
            step: L'étape à analyser
            composition: La composition complète
        
        Returns:
            Le type de fallback recommandé: 'default_value', 'alternative_step' ou 'skip'
        """
        # Si l'étape n'a pas d'étapes suivantes, elle peut être ignorée plus facilement
        if not step.next_steps:
            return "skip"
        
        # Si l'étape est utilisée dans des mappages, une valeur par défaut est préférable
        for mapping in composition.data_mappings:
            if mapping.source.startswith(f"{step.id}."):
                return "default_value"
        
        # Chercher une étape alternative potentielle
        if self._find_alternative_step(step, composition):
            return "alternative_step"
        
        # Par défaut, utiliser une valeur par défaut
        return "default_value"
    
    def _generate_default_value(self, step: CompositionStep, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Génère une valeur par défaut basée sur les résultats précédents.
        
        Args:
            step: L'étape pour laquelle générer une valeur par défaut
            step_data: Métriques de l'étape
        
        Returns:
            Une valeur par défaut appropriée
        """
        # Chercher des exemples de résultats réussis dans l'historique
        successful_examples = step_data.get("successful_examples", [])
        
        if successful_examples:
            # Utiliser le résultat le plus fréquent comme valeur par défaut
            return successful_examples[0]
        
        # Sinon, retourner un objet vide
        return {}
    
    def _find_alternative_step(self, step: CompositionStep, composition: Composition) -> Optional[str]:
        """
        Cherche une étape alternative qui pourrait remplacer une étape défaillante.
        
        Args:
            step: L'étape pour laquelle chercher une alternative
            composition: La composition complète
        
        Returns:
            L'ID de l'étape alternative ou None si aucune n'est trouvée
        """
        # Chercher une étape qui utilise un outil similaire
        for other_step in composition.steps:
            if other_step.id != step.id and other_step.tool == step.tool:
                return other_step.id
        
        return None

    def _optimize_composition_by_metrics(self, composition: Composition, step_metrics: Dict[str, Dict[str, Any]]) -> Composition:
        """
        Optimise une composition en fonction des métriques collectées.
        
        Args:
            composition: La composition à optimiser
            step_metrics: Métriques pour chaque étape
            
        Returns:
            La composition optimisée
        """
        if not step_metrics:
            logger.warning(f"Aucune métrique disponible pour {composition.id}")
            return composition
        
        # Optimisation des timeouts
        optimized = self.optimize_timeouts(composition, step_metrics)
        
        # Optimisation des stratégies de retry
        optimized = self.optimize_retry_strategies(optimized, step_metrics)
        
        # Optimisation des stratégies de fallback
        optimized = self.optimize_fallback_strategies(optimized, step_metrics)
        
        # Optimisation des conditions
        optimized = self.optimize_conditions(optimized, step_metrics)
        
        # Incrémentation de la version
        current_version = optimized.version
        version_parts = current_version.split('.')
        if len(version_parts) >= 3:
            patch = int(version_parts[2]) + 1
            optimized.version = f"{version_parts[0]}.{version_parts[1]}.{patch}"
        
        # Si la composition est en mode DRAFT, passer en LEARNING
        if optimized.status == CompositionStatus.DRAFT:
            optimized.status = CompositionStatus.LEARNING
        
        logger.info(f"Composition {composition.id} optimisée (nouvelle version: {optimized.version})")
        
        return optimized 