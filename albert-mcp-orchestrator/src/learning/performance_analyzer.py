from typing import Dict, List, Optional, Any, Tuple, Union
import json
import os
import pandas as pd
import numpy as np
import statistics
from datetime import datetime, timedelta
from pathlib import Path

from ..models.composition import Composition, CompositionStep, CompositionStatus
from ..registry.storage import CompositionStorage
from ..data.metrics import MetricsStorage
from ..config import settings
from loguru import logger


class PerformanceAnalyzer:
    """
    Analyseur de performance pour les compositions MCP.
    Agrège et analyse les métriques d'exécution pour générer des recommandations d'amélioration.
    """
    
    def __init__(self, storage: Optional[CompositionStorage] = None):
        """
        Initialise l'analyseur de performance.
        
        Args:
            storage: Gestionnaire de stockage (crée un nouveau si None)
        """
        self.storage = storage or CompositionStorage()
        self.metrics_storage = MetricsStorage()
        
        # Configuration des seuils d'analyse
        self.minimum_executions = settings.ANALYZER_MINIMUM_EXECUTIONS or 5
        self.success_rate_threshold = settings.ANALYZER_SUCCESS_RATE_THRESHOLD or 0.95
        self.error_rate_warning = settings.ANALYZER_ERROR_RATE_WARNING or 0.05
        self.latency_threshold_ms = settings.ANALYZER_LATENCY_THRESHOLD_MS or 1000
    
    def analyze_composition(self, composition_id: str) -> Dict[str, Any]:
        """
        Analyse les performances d'une composition et génère des recommandations.
        
        Args:
            composition_id: ID de la composition à analyser
            
        Returns:
            Résultats de l'analyse avec métriques et recommandations
        """
        # Charger la composition
        composition = self.storage.load_composition(composition_id)
        if not composition:
            logger.error(f"Composition {composition_id} non trouvée")
            return {"success": False, "error": "Composition non trouvée"}
        
        # Récupérer les métriques d'exécution
        metrics = self._get_execution_metrics(composition_id)
        if not metrics or len(metrics) < self.minimum_executions:
            logger.warning(f"Pas assez de données d'exécution pour {composition_id}. Trouvé: {len(metrics) if metrics else 0}")
            return {
                "success": True,
                "metrics_found": False,
                "composition_id": composition_id,
                "name": composition.name,
                "message": f"Pas assez de données pour une analyse fiable (minimum {self.minimum_executions} exécutions requises)"
            }
        
        # Agréger les métriques par étape
        step_metrics = self._aggregate_step_metrics(metrics, composition)
        
        # Calculer les métriques globales
        global_metrics = self._calculate_global_metrics(metrics, step_metrics)
        
        # Générer des recommandations
        recommendations = self._generate_recommendations(step_metrics, global_metrics, composition)
        
        # Résultat final
        return {
            "success": True,
            "metrics_found": True,
            "composition_id": composition_id,
            "name": composition.name,
            "analysis_timestamp": datetime.now().isoformat(),
            "metrics_count": len(metrics),
            "time_period": {
                "start": min(m["timestamp"] for m in metrics),
                "end": max(m["timestamp"] for m in metrics)
            },
            "overall_score": self._calculate_performance_score(global_metrics, step_metrics),
            "global_metrics": global_metrics,
            "step_performance": step_metrics,
            "recommendations": recommendations
        }
    
    def analyze_all_learning_compositions(self) -> Dict[str, Dict[str, Any]]:
        """
        Analyse toutes les compositions en phase d'apprentissage.
        
        Returns:
            Dictionnaire des résultats d'analyse par ID de composition
        """
        compositions = self.storage.list_compositions(status=CompositionStatus.LEARNING)
        
        results = {}
        for composition in compositions:
            try:
                result = self.analyze_composition(composition.id)
                results[composition.id] = result
            except Exception as e:
                logger.error(f"Erreur lors de l'analyse de {composition.id}: {e}")
                results[composition.id] = {
                    "success": False,
                    "error": str(e),
                    "composition_id": composition.id,
                    "name": composition.name
                }
        
        return results
    
    def _get_execution_metrics(self, composition_id: str) -> List[Dict[str, Any]]:
        """
        Récupère les métriques d'exécution pour une composition.
        
        Args:
            composition_id: ID de la composition
            
        Returns:
            Liste des métriques d'exécution
        """
        # Récupérer les métriques des 30 derniers jours par défaut
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        metrics = self.metrics_storage.get_execution_metrics(
            composition_id=composition_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return metrics
    
    def _aggregate_step_metrics(self, 
                               metrics: List[Dict[str, Any]], 
                               composition: Composition) -> Dict[str, Dict[str, Any]]:
        """
        Agrège les métriques par étape de la composition.
        
        Args:
            metrics: Liste des métriques d'exécution
            composition: La composition analysée
            
        Returns:
            Métriques agrégées par étape
        """
        step_metrics = {}
        
        # Initialiser les métriques pour chaque étape
        for step in composition.steps:
            step_metrics[step.id] = {
                "step_id": step.id,
                "step_name": step.name,
                "execution_count": 0,
                "success_count": 0,
                "success_rate": 0,
                "error_count": 0,
                "error_rate": 0,
                "avg_duration_ms": 0,
                "min_duration_ms": float('inf'),
                "max_duration_ms": 0,
                "median_duration_ms": 0,
                "duration_p95_ms": 0,
                "durations": [],
                "error_types": {},
                "memory_avg_mb": 0,
                "memory_max_mb": 0
            }
        
        # Agréger les métriques
        for execution in metrics:
            step_executions = execution.get("step_executions", {})
            
            for step_id, step_data in step_executions.items():
                if step_id not in step_metrics:
                    # Ignorer les étapes qui ne font plus partie de la composition
                    continue
                
                step_metrics[step_id]["execution_count"] += 1
                
                success = step_data.get("success", False)
                if success:
                    step_metrics[step_id]["success_count"] += 1
                else:
                    step_metrics[step_id]["error_count"] += 1
                    
                    # Compter les types d'erreurs
                    error_type = step_data.get("error_type", "unknown")
                    if error_type in step_metrics[step_id]["error_types"]:
                        step_metrics[step_id]["error_types"][error_type] += 1
                    else:
                        step_metrics[step_id]["error_types"][error_type] = 1
                
                # Mesures de durée
                duration_ms = step_data.get("duration_ms", 0)
                if duration_ms > 0:
                    step_metrics[step_id]["durations"].append(duration_ms)
                    step_metrics[step_id]["min_duration_ms"] = min(
                        step_metrics[step_id]["min_duration_ms"], duration_ms)
                    step_metrics[step_id]["max_duration_ms"] = max(
                        step_metrics[step_id]["max_duration_ms"], duration_ms)
                
                # Mesures de mémoire
                memory_mb = step_data.get("memory_mb", 0)
                if memory_mb > 0:
                    if "memory_values" not in step_metrics[step_id]:
                        step_metrics[step_id]["memory_values"] = []
                    step_metrics[step_id]["memory_values"].append(memory_mb)
                    step_metrics[step_id]["memory_max_mb"] = max(
                        step_metrics[step_id]["memory_max_mb"], memory_mb)
        
        # Calculer les statistiques finales pour chaque étape
        for step_id, metrics in step_metrics.items():
            if metrics["execution_count"] > 0:
                metrics["success_rate"] = metrics["success_count"] / metrics["execution_count"]
                metrics["error_rate"] = metrics["error_count"] / metrics["execution_count"]
                
                durations = metrics["durations"]
                if durations:
                    metrics["avg_duration_ms"] = sum(durations) / len(durations)
                    
                    if len(durations) > 1:
                        metrics["median_duration_ms"] = statistics.median(durations)
                        
                        # p95 approximation
                        sorted_durations = sorted(durations)
                        p95_index = int(len(sorted_durations) * 0.95)
                        metrics["duration_p95_ms"] = sorted_durations[p95_index]
                    else:
                        metrics["median_duration_ms"] = durations[0]
                        metrics["duration_p95_ms"] = durations[0]
                
                # Éviter de conserver toutes les durées dans le résultat
                metrics.pop("durations", None)
                
                memory_values = metrics.get("memory_values", [])
                if memory_values:
                    metrics["memory_avg_mb"] = sum(memory_values) / len(memory_values)
                
                # Nettoyer les valeurs temporaires
                metrics.pop("memory_values", None)
            
            # Si aucune exécution, définir des valeurs par défaut
            if metrics["min_duration_ms"] == float('inf'):
                metrics["min_duration_ms"] = 0
        
        return step_metrics
    
    def _calculate_global_metrics(self, 
                                 metrics: List[Dict[str, Any]], 
                                 step_metrics: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calcule les métriques globales d'une composition.
        
        Args:
            metrics: Liste des métriques d'exécution
            step_metrics: Métriques agrégées par étape
            
        Returns:
            Métriques globales de la composition
        """
        global_metrics = {
            "execution_count": len(metrics),
            "success_count": 0,
            "success_rate": 0,
            "error_count": 0,
            "error_rate": 0,
            "avg_duration_ms": 0,
            "min_duration_ms": float('inf'),
            "max_duration_ms": 0,
            "median_duration_ms": 0,
            "duration_p95_ms": 0,
            "error_types": {},
            "durations": []
        }
        
        # Agréger les statistiques globales
        for execution in metrics:
            success = execution.get("success", False)
            if success:
                global_metrics["success_count"] += 1
            else:
                global_metrics["error_count"] += 1
                
                # Compter les types d'erreurs
                error_type = execution.get("error_type", "unknown")
                if error_type in global_metrics["error_types"]:
                    global_metrics["error_types"][error_type] += 1
                else:
                    global_metrics["error_types"][error_type] = 1
            
            # Durée totale de l'exécution
            duration_ms = execution.get("duration_ms", 0)
            if duration_ms > 0:
                global_metrics["durations"].append(duration_ms)
                global_metrics["min_duration_ms"] = min(global_metrics["min_duration_ms"], duration_ms)
                global_metrics["max_duration_ms"] = max(global_metrics["max_duration_ms"], duration_ms)
        
        # Calculer les statistiques finales
        if global_metrics["execution_count"] > 0:
            global_metrics["success_rate"] = global_metrics["success_count"] / global_metrics["execution_count"]
            global_metrics["error_rate"] = global_metrics["error_count"] / global_metrics["execution_count"]
            
            durations = global_metrics["durations"]
            if durations:
                global_metrics["avg_duration_ms"] = sum(durations) / len(durations)
                
                if len(durations) > 1:
                    global_metrics["median_duration_ms"] = statistics.median(durations)
                    
                    # p95 approximation
                    sorted_durations = sorted(durations)
                    p95_index = int(len(sorted_durations) * 0.95)
                    global_metrics["duration_p95_ms"] = sorted_durations[p95_index]
                else:
                    global_metrics["median_duration_ms"] = durations[0]
                    global_metrics["duration_p95_ms"] = durations[0]
        
        # Éviter de conserver toutes les durées dans le résultat
        global_metrics.pop("durations", None)
        
        # Si aucune exécution, définir des valeurs par défaut
        if global_metrics["min_duration_ms"] == float('inf'):
            global_metrics["min_duration_ms"] = 0
        
        # Calculer des métriques additionnelles
        step_counts = len(step_metrics)
        if step_counts > 0:
            global_metrics["avg_steps_per_execution"] = sum(
                m["step_count"] for m in metrics if "step_count" in m
            ) / len(metrics)
            
            # Identifier les étapes les plus lentes et les plus sujettes aux erreurs
            slowest_step_id = max(
                step_metrics.keys(),
                key=lambda s: step_metrics[s]["avg_duration_ms"],
                default=None
            )
            
            most_failing_step_id = max(
                step_metrics.keys(),
                key=lambda s: step_metrics[s]["error_rate"],
                default=None
            )
            
            if slowest_step_id:
                global_metrics["slowest_step"] = {
                    "id": slowest_step_id,
                    "name": step_metrics[slowest_step_id]["step_name"],
                    "avg_duration_ms": step_metrics[slowest_step_id]["avg_duration_ms"]
                }
            
            if most_failing_step_id and step_metrics[most_failing_step_id]["error_rate"] > 0:
                global_metrics["most_failing_step"] = {
                    "id": most_failing_step_id,
                    "name": step_metrics[most_failing_step_id]["step_name"],
                    "error_rate": step_metrics[most_failing_step_id]["error_rate"]
                }
        
        return global_metrics
    
    def _calculate_performance_score(self, 
                                    global_metrics: Dict[str, Any],
                                    step_metrics: Dict[str, Dict[str, Any]]) -> float:
        """
        Calcule un score global de performance pour la composition.
        
        Args:
            global_metrics: Métriques globales
            step_metrics: Métriques par étape
            
        Returns:
            Score de performance entre 0 et 100
        """
        # Poids de chaque facteur dans le score final
        weights = {
            "success_rate": 0.5,      # 50% pour le taux de succès global
            "response_time": 0.3,     # 30% pour le temps de réponse
            "step_consistency": 0.2   # 20% pour la consistance des étapes
        }
        
        # Score basé sur le taux de succès (0-50 points)
        success_score = global_metrics["success_rate"] * 100 * weights["success_rate"]
        
        # Score basé sur le temps de réponse (0-30 points)
        # Plus le temps est court, meilleur est le score
        avg_duration = global_metrics["avg_duration_ms"]
        if avg_duration <= 500:
            response_score = 30
        elif avg_duration <= 1000:
            response_score = 25
        elif avg_duration <= 2000:
            response_score = 20
        elif avg_duration <= 5000:
            response_score = 15
        elif avg_duration <= 10000:
            response_score = 10
        elif avg_duration <= 30000:
            response_score = 5
        else:
            response_score = 0
        response_score *= weights["response_time"]
        
        # Score basé sur la consistance des étapes (0-20 points)
        if not step_metrics:
            step_consistency_score = 0
        else:
            # Calculer le score moyen pour chaque étape
            step_scores = []
            for step_id, metrics in step_metrics.items():
                step_success_rate = metrics.get("success_rate", 0)
                step_score = step_success_rate * 100
                step_scores.append(step_score)
            
            # La consistance est la moyenne des scores des étapes
            if step_scores:
                step_consistency_score = (sum(step_scores) / len(step_scores)) * weights["step_consistency"]
            else:
                step_consistency_score = 0
        
        # Score total arrondi à l'entier
        total_score = round(success_score + response_score + step_consistency_score)
        
        # Limiter entre 0 et 100
        return max(0, min(100, total_score))
    
    def _generate_recommendations(self, 
                                 step_metrics: Dict[str, Dict[str, Any]],
                                 global_metrics: Dict[str, Any],
                                 composition: Composition) -> List[Dict[str, Any]]:
        """
        Génère des recommandations d'amélioration en fonction des métriques.
        
        Args:
            step_metrics: Métriques par étape
            global_metrics: Métriques globales
            composition: La composition analysée
            
        Returns:
            Liste des recommandations
        """
        recommendations = []
        
        # Valider le taux de succès global
        global_success_rate = global_metrics.get("success_rate", 1.0)
        if global_success_rate < self.success_rate_threshold:
            recommendations.append({
                "type": "global",
                "priority": "high",
                "message": "Taux de succès global insuffisant",
                "details": (f"Le taux de succès global est de {global_success_rate:.1%}, "
                           f"ce qui est inférieur au seuil recommandé de {self.success_rate_threshold:.1%}")
            })
        
        # Examiner chaque étape pour des recommandations spécifiques
        for step_id, metrics in step_metrics.items():
            step = next((s for s in composition.steps if s.id == step_id), None)
            if not step:
                continue
            
            # Recommandations sur le taux de succès
            success_rate = metrics.get("success_rate", 1.0)
            if success_rate < 0.9:
                # Taux d'échec élevé
                recommendation = {
                    "type": "step",
                    "step_id": step_id,
                    "priority": "high",
                    "message": f"Taux d'échec élevé pour l'étape '{step.name}'",
                    "details": f"Cette étape échoue dans {(1-success_rate):.1%} des cas"
                }
                
                # Ajouter des suggestions spécifiques
                if not step.retry_strategy:
                    recommendation["details"] += ". Envisager d'ajouter une stratégie de retry"
                elif step.retry_strategy.get("max_retries", 0) < 3:
                    recommendation["details"] += ". Envisager d'augmenter le nombre de retries"
                
                # Ajouter des informations sur les types d'erreurs
                error_types = metrics.get("error_types", {})
                if error_types:
                    top_error = max(error_types.items(), key=lambda x: x[1], default=(None, 0))
                    if top_error[0]:
                        recommendation["details"] += f". Erreur principale: {top_error[0]} ({top_error[1]} occurrences)"
                
                recommendations.append(recommendation)
            
            # Recommandations sur le temps d'exécution
            avg_duration = metrics.get("avg_duration_ms", 0)
            if avg_duration > self.latency_threshold_ms:
                # Temps d'exécution long
                priority = "medium"
                if avg_duration > self.latency_threshold_ms * 3:
                    priority = "high"
                
                recommendation = {
                    "type": "step",
                    "step_id": step_id,
                    "priority": priority,
                    "message": f"Temps d'exécution long pour l'étape '{step.name}'",
                    "details": (f"Durée moyenne: {avg_duration:.0f}ms, "
                               f"max: {metrics.get('max_duration_ms', 0):.0f}ms")
                }
                
                # Ajouter des suggestions spécifiques
                current_timeout = step.timeout_seconds
                if current_timeout * 1000 < avg_duration * 2:
                    recommendation["details"] += f". Le timeout actuel ({current_timeout}s) pourrait être insuffisant"
                
                recommendations.append(recommendation)
            
            # Recommandations sur l'utilisation de mémoire
            memory_max = metrics.get("memory_max_mb", 0)
            if memory_max > 500:  # Seuil arbitraire à 500 MB
                recommendations.append({
                    "type": "step",
                    "step_id": step_id,
                    "priority": "medium",
                    "message": f"Utilisation élevée de mémoire pour l'étape '{step.name}'",
                    "details": f"Utilisation maximale: {memory_max}MB, moyenne: {metrics.get('memory_avg_mb', 0):.1f}MB"
                })
        
        # Recommandation globale sur le temps d'exécution
        avg_duration = global_metrics.get("avg_duration_ms", 0)
        if avg_duration > self.latency_threshold_ms * 2:
            recommendations.append({
                "type": "global",
                "priority": "medium",
                "message": "Temps d'exécution global élevé",
                "details": (f"Durée moyenne: {avg_duration:.0f}ms. Chercher les étapes avec les temps "
                           f"d'exécution les plus longs ou envisager l'exécution parallèle si possible")
            })
        
        return recommendations 