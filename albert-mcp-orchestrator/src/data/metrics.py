from typing import Dict, List, Optional, Any, Tuple, Union
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from ..config import settings
from loguru import logger


class MetricsStorage:
    """
    Gère le stockage et la récupération des métriques d'exécution.
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialise le stockage des métriques.
        
        Args:
            base_dir: Répertoire de base pour le stockage (utilise le répertoire par défaut si None)
        """
        self.base_dir = base_dir or settings.METRICS_DIR
        os.makedirs(self.base_dir, exist_ok=True)
    
    def store_execution_metrics(self, 
                               composition_id: str, 
                               metrics: Dict[str, Any]) -> bool:
        """
        Stocke les métriques d'exécution d'une composition.
        
        Args:
            composition_id: ID de la composition
            metrics: Métriques d'exécution à stocker
            
        Returns:
            True si le stockage a réussi, False sinon
        """
        try:
            # Vérifier que les métriques contiennent un timestamp
            if "timestamp" not in metrics:
                metrics["timestamp"] = datetime.now().isoformat()
            
            # Ajouter l'ID de composition si non présent
            if "composition_id" not in metrics:
                metrics["composition_id"] = composition_id
            
            # Chemin du fichier de métriques pour cette composition
            metrics_file = self.base_dir / f"{composition_id}.jsonl"
            
            # Écrire les métriques en format JSONL (append)
            with open(metrics_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(metrics) + "\n")
            
            return True
        except Exception as e:
            logger.error(f"Erreur lors du stockage des métriques pour {composition_id}: {e}")
            return False
    
    def get_execution_metrics(self, 
                             composition_id: str,
                             start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None,
                             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Récupère les métriques d'exécution d'une composition.
        
        Args:
            composition_id: ID de la composition
            start_date: Date de début de la période (optionnel)
            end_date: Date de fin de la période (optionnel)
            limit: Nombre maximum de métriques à récupérer (optionnel)
            
        Returns:
            Liste des métriques d'exécution
        """
        metrics = []
        metrics_file = self.base_dir / f"{composition_id}.jsonl"
        
        if not metrics_file.exists():
            return []
        
        # Convertir les dates en chaînes ISO pour comparaison
        start_str = start_date.isoformat() if start_date else None
        end_str = end_date.isoformat() if end_date else None
        
        try:
            with open(metrics_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        metric = json.loads(line.strip())
                        
                        # Filtrer par date si spécifiée
                        timestamp = metric.get("timestamp", "")
                        if start_str and timestamp < start_str:
                            continue
                        if end_str and timestamp > end_str:
                            continue
                        
                        metrics.append(metric)
                        
                        # Limiter le nombre de résultats si spécifié
                        if limit and len(metrics) >= limit:
                            break
                    except json.JSONDecodeError:
                        logger.warning(f"Ligne de métrique invalide: {line[:50]}...")
                        continue
        except Exception as e:
            logger.error(f"Erreur lors de la lecture des métriques pour {composition_id}: {e}")
        
        # Trier par timestamp (du plus ancien au plus récent)
        metrics.sort(key=lambda m: m.get("timestamp", ""))
        
        return metrics
    
    def get_latest_metrics(self, 
                          composition_id: str, 
                          count: int = 10) -> List[Dict[str, Any]]:
        """
        Récupère les métriques d'exécution les plus récentes.
        
        Args:
            composition_id: ID de la composition
            count: Nombre de métriques à récupérer
            
        Returns:
            Liste des métriques d'exécution les plus récentes
        """
        metrics = self.get_execution_metrics(composition_id)
        
        # Trier par timestamp (du plus récent au plus ancien)
        metrics.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
        
        # Retourner les N plus récentes
        return metrics[:count]
    
    def get_compositions_with_metrics(self) -> List[str]:
        """
        Récupère la liste des IDs de compositions ayant des métriques stockées.
        
        Returns:
            Liste des IDs de compositions
        """
        try:
            # Lister tous les fichiers .jsonl du répertoire
            composition_ids = []
            for file in self.base_dir.glob("*.jsonl"):
                # Extraire l'ID de composition du nom de fichier
                composition_id = file.stem
                composition_ids.append(composition_id)
            
            return composition_ids
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des compositions avec métriques: {e}")
            return []
    
    def delete_metrics(self, 
                      composition_id: str, 
                      before_date: Optional[datetime] = None) -> bool:
        """
        Supprime les métriques d'une composition.
        
        Args:
            composition_id: ID de la composition
            before_date: Supprimer seulement les métriques avant cette date (optionnel)
            
        Returns:
            True si la suppression a réussi, False sinon
        """
        metrics_file = self.base_dir / f"{composition_id}.jsonl"
        
        if not metrics_file.exists():
            return True  # Rien à supprimer
        
        try:
            # Si pas de date, supprimer tout le fichier
            if not before_date:
                os.remove(metrics_file)
                return True
            
            # Sinon, filtrer les métriques à conserver
            before_str = before_date.isoformat()
            metrics_to_keep = []
            
            with open(metrics_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        metric = json.loads(line.strip())
                        timestamp = metric.get("timestamp", "")
                        
                        # Conserver seulement les métriques après la date spécifiée
                        if timestamp >= before_str:
                            metrics_to_keep.append(line)
                    except json.JSONDecodeError:
                        continue
            
            # Réécrire le fichier avec les métriques conservées
            with open(metrics_file, "w", encoding="utf-8") as f:
                for line in metrics_to_keep:
                    f.write(line)
            
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression des métriques pour {composition_id}: {e}")
            return False
    
    def aggregate_metrics(self, 
                         composition_id: str,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Agrège les métriques d'exécution d'une composition sur une période.
        
        Args:
            composition_id: ID de la composition
            start_date: Date de début de la période
            end_date: Date de fin de la période
            
        Returns:
            Métriques agrégées
        """
        # Récupérer les métriques brutes
        metrics = self.get_execution_metrics(
            composition_id=composition_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if not metrics:
            return {
                "composition_id": composition_id,
                "metrics_count": 0,
                "message": "Aucune métrique trouvée pour cette période"
            }
        
        # Initialiser les résultats
        result = {
            "composition_id": composition_id,
            "metrics_count": len(metrics),
            "period": {
                "start": start_date.isoformat() if start_date else min(m["timestamp"] for m in metrics),
                "end": end_date.isoformat() if end_date else max(m["timestamp"] for m in metrics),
            },
            "success_count": 0,
            "error_count": 0,
            "success_rate": 0,
            "avg_duration_ms": 0,
            "min_duration_ms": float('inf'),
            "max_duration_ms": 0,
            "step_metrics": {}
        }
        
        # Agréger les métriques globales
        total_duration = 0
        for metric in metrics:
            # Succès/échec
            if metric.get("success", False):
                result["success_count"] += 1
            else:
                result["error_count"] += 1
            
            # Durée d'exécution
            duration = metric.get("duration_ms", 0)
            if duration > 0:
                total_duration += duration
                result["min_duration_ms"] = min(result["min_duration_ms"], duration)
                result["max_duration_ms"] = max(result["max_duration_ms"], duration)
            
            # Agréger les métriques par étape
            step_executions = metric.get("step_executions", {})
            for step_id, step_data in step_executions.items():
                if step_id not in result["step_metrics"]:
                    result["step_metrics"][step_id] = {
                        "execution_count": 0,
                        "success_count": 0,
                        "error_count": 0,
                        "avg_duration_ms": 0,
                        "total_duration_ms": 0,
                        "min_duration_ms": float('inf'),
                        "max_duration_ms": 0
                    }
                
                # Incrémenter les compteurs
                result["step_metrics"][step_id]["execution_count"] += 1
                
                if step_data.get("success", False):
                    result["step_metrics"][step_id]["success_count"] += 1
                else:
                    result["step_metrics"][step_id]["error_count"] += 1
                
                # Agréger la durée
                step_duration = step_data.get("duration_ms", 0)
                if step_duration > 0:
                    result["step_metrics"][step_id]["total_duration_ms"] += step_duration
                    result["step_metrics"][step_id]["min_duration_ms"] = min(
                        result["step_metrics"][step_id]["min_duration_ms"], step_duration)
                    result["step_metrics"][step_id]["max_duration_ms"] = max(
                        result["step_metrics"][step_id]["max_duration_ms"], step_duration)
        
        # Calculer les moyennes et taux
        if result["metrics_count"] > 0:
            result["success_rate"] = result["success_count"] / result["metrics_count"]
            result["avg_duration_ms"] = total_duration / result["metrics_count"]
            
            # Finaliser les métriques par étape
            for step_id, step_data in result["step_metrics"].items():
                if step_data["execution_count"] > 0:
                    step_data["success_rate"] = step_data["success_count"] / step_data["execution_count"]
                    step_data["avg_duration_ms"] = step_data["total_duration_ms"] / step_data["execution_count"]
                
                # Nettoyer les valeurs utilisées pour le calcul
                step_data.pop("total_duration_ms", None)
                
                # Corriger les valeurs min si aucune donnée
                if step_data["min_duration_ms"] == float('inf'):
                    step_data["min_duration_ms"] = 0
        
        # Corriger la valeur min si aucune donnée
        if result["min_duration_ms"] == float('inf'):
            result["min_duration_ms"] = 0
        
        return result 