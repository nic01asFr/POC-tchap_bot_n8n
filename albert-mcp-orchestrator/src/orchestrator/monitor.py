from typing import Dict, List, Optional, Any, Union, Callable
import json
import os
from datetime import datetime
import time
from pathlib import Path
import asyncio
from pyee.asyncio import AsyncIOEventEmitter

from ..models.composition import Composition
from ..config import settings
from loguru import logger


class ExecutionMonitor:
    """
    Moniteur d'exécution pour les compositions MCP.
    Enregistre les métriques d'exécution et les événements pour l'analyse et l'apprentissage.
    """
    
    def __init__(self, metrics_collection: bool = True):
        """
        Initialise le moniteur d'exécution.
        
        Args:
            metrics_collection: Activer ou non la collecte de métriques
        """
        self.metrics_collection = metrics_collection
        
        # Émetteur d'événements pour la communication asynchrone
        self.emitter = AsyncIOEventEmitter()
        
        # Chemin pour les logs d'exécution
        self.logs_dir = settings.BASE_DIR / "logs" / "executions"
        os.makedirs(self.logs_dir, exist_ok=True)
    
    def start_execution(self, context):
        """
        Démarre le monitoring d'une exécution.
        
        Args:
            context: Contexte d'exécution
        """
        execution_id = context.execution_id
        composition_id = context.composition.id
        composition_name = context.composition.name
        
        logger.info(f"Démarrage de l'exécution {execution_id} de la composition '{composition_name}' (ID: {composition_id})")
        
        # Émettre un événement de début d'exécution
        event_data = {
            "execution_id": execution_id,
            "composition_id": composition_id,
            "composition_name": composition_name,
            "start_time": datetime.now().isoformat(),
            "input_data": context.input_data
        }
        
        # Émettre l'événement de manière asynchrone
        asyncio.create_task(self._emit_event("execution_started", event_data))
        
        # Enregistrer le début dans le journal
        self._log_execution_event(execution_id, "started", event_data)
    
    def end_execution(self, context, success: bool, result: Any, execution_time: float):
        """
        Finalise le monitoring d'une exécution.
        
        Args:
            context: Contexte d'exécution
            success: Indicateur de succès
            result: Résultat de l'exécution
            execution_time: Temps d'exécution en secondes
        """
        execution_id = context.execution_id
        composition_id = context.composition.id
        composition_name = context.composition.name
        
        # Mise à jour du contexte
        context.finish_execution(success)
        
        # Événement de fin d'exécution
        event_data = {
            "execution_id": execution_id,
            "composition_id": composition_id,
            "composition_name": composition_name,
            "end_time": datetime.now().isoformat(),
            "execution_time_ms": int(execution_time * 1000),
            "success": success,
            "result": self._sanitize_for_logging(result)
        }
        
        status = "succès" if success else "échec"
        logger.info(f"Fin de l'exécution {execution_id} avec {status} en {execution_time:.2f}s")
        
        # Émettre l'événement de manière asynchrone
        asyncio.create_task(self._emit_event("execution_ended", event_data))
        
        # Enregistrer la fin dans le journal
        self._log_execution_event(execution_id, "ended", event_data)
        
        # Enregistrer les métriques d'exécution si activé
        if self.metrics_collection:
            asyncio.create_task(self._save_execution_metrics(context, success, execution_time))
    
    def start_step(self, context, step_id: str):
        """
        Démarre le monitoring d'une étape.
        
        Args:
            context: Contexte d'exécution
            step_id: ID de l'étape
        """
        execution_id = context.execution_id
        
        # Enregistrer le timing de début
        start_time = datetime.now()
        context.add_step_timing(step_id, start_time)
        
        # Événement de début d'étape
        event_data = {
            "execution_id": execution_id,
            "step_id": step_id,
            "start_time": start_time.isoformat()
        }
        
        logger.debug(f"Début de l'étape {step_id} pour l'exécution {execution_id}")
        
        # Émettre l'événement de manière asynchrone
        asyncio.create_task(self._emit_event("step_started", event_data))
    
    def end_step(self, context, step_id: str, success: bool, result: Any, execution_time: float):
        """
        Finalise le monitoring d'une étape.
        
        Args:
            context: Contexte d'exécution
            step_id: ID de l'étape
            success: Indicateur de succès
            result: Résultat de l'étape
            execution_time: Temps d'exécution en secondes
        """
        execution_id = context.execution_id
        
        # Mettre à jour le timing de l'étape
        end_time = datetime.now()
        duration_ms = int(execution_time * 1000)
        context.update_step_timing(step_id, end_time, duration_ms)
        
        # Événement de fin d'étape
        event_data = {
            "execution_id": execution_id,
            "step_id": step_id,
            "end_time": end_time.isoformat(),
            "execution_time_ms": duration_ms,
            "success": success,
            "result": self._sanitize_for_logging(result)
        }
        
        status = "succès" if success else "échec"
        logger.debug(f"Fin de l'étape {step_id} avec {status} en {execution_time:.2f}s")
        
        # Émettre l'événement de manière asynchrone
        asyncio.create_task(self._emit_event("step_ended", event_data))
    
    def register_feedback(self, execution_id: str, feedback: Dict[str, Any]):
        """
        Enregistre un retour utilisateur pour une exécution.
        
        Args:
            execution_id: ID de l'exécution
            feedback: Données de retour utilisateur
        """
        # Événement de retour utilisateur
        event_data = {
            "execution_id": execution_id,
            "feedback_time": datetime.now().isoformat(),
            "feedback": feedback
        }
        
        logger.info(f"Retour utilisateur reçu pour l'exécution {execution_id}")
        
        # Émettre l'événement de manière asynchrone
        asyncio.create_task(self._emit_event("user_feedback", event_data))
        
        # Enregistrer le retour dans le journal
        self._log_execution_event(execution_id, "feedback", event_data)
    
    def on(self, event: str, callback: Callable):
        """
        Enregistre un gestionnaire d'événements.
        
        Args:
            event: Nom de l'événement
            callback: Fonction de callback
        """
        self.emitter.on(event, callback)
    
    def off(self, event: str, callback: Callable):
        """
        Supprime un gestionnaire d'événements.
        
        Args:
            event: Nom de l'événement
            callback: Fonction de callback
        """
        self.emitter.remove_listener(event, callback)
    
    async def _emit_event(self, event: str, data: Dict[str, Any]):
        """
        Émet un événement de manière asynchrone.
        
        Args:
            event: Nom de l'événement
            data: Données de l'événement
        """
        self.emitter.emit(event, data)
    
    def _log_execution_event(self, execution_id: str, event_type: str, data: Dict[str, Any]):
        """
        Enregistre un événement d'exécution dans le journal.
        
        Args:
            execution_id: ID de l'exécution
            event_type: Type d'événement
            data: Données de l'événement
        """
        try:
            # Créer le répertoire pour cette exécution
            execution_dir = self.logs_dir / execution_id
            os.makedirs(execution_dir, exist_ok=True)
            
            # Fichier de journal pour cet événement
            log_file = execution_dir / f"{event_type}.json"
            
            # Écrire les données
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de l'événement {event_type} pour {execution_id}: {e}")
    
    async def _save_execution_metrics(self, context, success: bool, execution_time: float):
        """
        Enregistre les métriques d'exécution pour analyse ultérieure.
        
        Args:
            context: Contexte d'exécution
            success: Indicateur de succès
            execution_time: Temps d'exécution en secondes
        """
        try:
            # Préparer les métriques
            metrics = {
                "execution_id": context.execution_id,
                "composition_id": context.composition.id,
                "composition_name": context.composition.name,
                "timestamp": datetime.now().isoformat(),
                "execution_time_ms": int(execution_time * 1000),
                "success": success,
                "step_metrics": self._extract_step_metrics(context),
                "input_size": self._calculate_size(context.input_data)
            }
            
            # Créer le répertoire pour les métriques
            metrics_dir = settings.BASE_DIR / "metrics"
            os.makedirs(metrics_dir, exist_ok=True)
            
            # Fichier de métriques pour cette composition
            metrics_file = metrics_dir / f"{context.composition.id}.jsonl"
            
            # Ajouter les métriques au fichier (format JSONL)
            with open(metrics_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(metrics, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement des métriques pour {context.execution_id}: {e}")
    
    def _extract_step_metrics(self, context) -> Dict[str, Dict[str, Any]]:
        """
        Extrait les métriques des étapes depuis le contexte.
        
        Args:
            context: Contexte d'exécution
        
        Returns:
            Dictionnaire des métriques par étape
        """
        step_metrics = {}
        
        for step_id, timing in context.step_timings.items():
            success = step_id not in context.step_errors
            
            metric = {
                "duration_ms": timing.get("duration_ms", 0),
                "success": success
            }
            
            if not success:
                metric["error"] = context.step_errors.get(step_id)
            
            step_metrics[step_id] = metric
        
        return step_metrics
    
    def _calculate_size(self, data: Any) -> int:
        """
        Calcule une estimation de la taille des données.
        
        Args:
            data: Les données à mesurer
        
        Returns:
            Taille estimée en octets
        """
        try:
            # Sérialiser en JSON et mesurer la taille
            serialized = json.dumps(data)
            return len(serialized.encode("utf-8"))
        except Exception:
            # Fallback si non sérialisable
            return 0
    
    def _sanitize_for_logging(self, data: Any) -> Any:
        """
        Sanitise les données pour le logging.
        
        Args:
            data: Les données à sanitiser
        
        Returns:
            Données sanitisées
        """
        try:
            # Vérifier si sérialisable
            json.dumps(data)
            return data
        except (TypeError, OverflowError):
            # Convertir en chaîne si non sérialisable
            if isinstance(data, dict):
                return {k: self._sanitize_for_logging(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [self._sanitize_for_logging(item) for item in data]
            else:
                return str(data) 