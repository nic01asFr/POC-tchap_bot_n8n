from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
import json

from ..models.composition import Composition
from loguru import logger


class ExecutionContext:
    """
    Contexte d'exécution pour une composition.
    Stocke l'état d'exécution, les résultats intermédiaires et les données d'entrée/sortie.
    """
    
    def __init__(self, 
                composition: Composition,
                input_data: Dict[str, Any],
                execution_id: Optional[str] = None):
        """
        Initialise un nouveau contexte d'exécution.
        
        Args:
            composition: La composition à exécuter
            input_data: Les données d'entrée
            execution_id: ID d'exécution (généré si None)
        """
        self.composition = composition
        self.input_data = input_data
        self.execution_id = execution_id or str(uuid.uuid4())
        self.start_time = datetime.now()
        self.end_time = None
        self.duration_ms = None
        self.success = None
        
        # Stockage des résultats et erreurs par étape
        self.step_results: Dict[str, Any] = {}
        self.step_errors: Dict[str, str] = {}
        self.step_timings: Dict[str, Dict[str, Any]] = {}
        
        # Variables globales partagées entre les étapes
        self.globals: Dict[str, Any] = {}
    
    def add_step_result(self, step_id: str, result: Any) -> None:
        """
        Ajoute le résultat d'une étape au contexte.
        
        Args:
            step_id: ID de l'étape
            result: Résultat de l'étape
        """
        self.step_results[step_id] = result
    
    def get_step_result(self, step_id: str) -> Optional[Any]:
        """
        Récupère le résultat d'une étape.
        
        Args:
            step_id: ID de l'étape
        
        Returns:
            Résultat de l'étape ou None si non disponible
        """
        return self.step_results.get(step_id)
    
    def add_step_error(self, step_id: str, error: str) -> None:
        """
        Enregistre une erreur pour une étape.
        
        Args:
            step_id: ID de l'étape
            error: Message d'erreur
        """
        self.step_errors[step_id] = error
    
    def add_step_timing(self, step_id: str, start_time: datetime, 
                       end_time: Optional[datetime] = None,
                       duration_ms: Optional[int] = None) -> None:
        """
        Enregistre les informations de timing pour une étape.
        
        Args:
            step_id: ID de l'étape
            start_time: Heure de début
            end_time: Heure de fin (optionnel)
            duration_ms: Durée en millisecondes (optionnel)
        """
        timing = {
            "start_time": start_time,
            "end_time": end_time,
            "duration_ms": duration_ms
        }
        self.step_timings[step_id] = timing
    
    def update_step_timing(self, step_id: str, end_time: datetime, duration_ms: int) -> None:
        """
        Met à jour les informations de timing pour une étape.
        
        Args:
            step_id: ID de l'étape
            end_time: Heure de fin
            duration_ms: Durée en millisecondes
        """
        if step_id in self.step_timings:
            self.step_timings[step_id]["end_time"] = end_time
            self.step_timings[step_id]["duration_ms"] = duration_ms
        else:
            logger.warning(f"Tentative de mise à jour du timing pour l'étape {step_id} non existante")
    
    def set_global(self, key: str, value: Any) -> None:
        """
        Définit une variable globale dans le contexte.
        
        Args:
            key: Nom de la variable
            value: Valeur à stocker
        """
        self.globals[key] = value
    
    def get_global(self, key: str, default: Any = None) -> Any:
        """
        Récupère une variable globale du contexte.
        
        Args:
            key: Nom de la variable
            default: Valeur par défaut si non trouvée
        
        Returns:
            Valeur de la variable ou valeur par défaut
        """
        return self.globals.get(key, default)
    
    def finish_execution(self, success: bool) -> None:
        """
        Finalise l'exécution et enregistre son résultat.
        
        Args:
            success: Indicateur de succès
        """
        self.end_time = datetime.now()
        self.duration_ms = int((self.end_time - self.start_time).total_seconds() * 1000)
        self.success = success
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convertit le contexte en dictionnaire pour la sérialisation.
        
        Returns:
            Représentation dictionnaire du contexte
        """
        return {
            "execution_id": self.execution_id,
            "composition_id": self.composition.id,
            "composition_name": self.composition.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "input_data": self.input_data,
            "step_results": self._serialize_step_results(),
            "step_errors": self.step_errors,
            "step_timings": self._serialize_step_timings(),
            "globals": self._serialize_globals()
        }
    
    def _serialize_step_results(self) -> Dict[str, Any]:
        """
        Sérialise les résultats des étapes pour JSON.
        
        Returns:
            Résultats des étapes sérialisables
        """
        # Cette méthode simplifie les résultats pour la sérialisation
        # Exemple basique, il peut être nécessaire d'adapter selon les résultats
        return {k: self._make_serializable(v) for k, v in self.step_results.items()}
    
    def _serialize_step_timings(self) -> Dict[str, Any]:
        """
        Sérialise les informations de timing pour JSON.
        
        Returns:
            Informations de timing sérialisables
        """
        result = {}
        for step_id, timing in self.step_timings.items():
            serialized_timing = timing.copy()
            if "start_time" in serialized_timing and serialized_timing["start_time"]:
                serialized_timing["start_time"] = serialized_timing["start_time"].isoformat()
            if "end_time" in serialized_timing and serialized_timing["end_time"]:
                serialized_timing["end_time"] = serialized_timing["end_time"].isoformat()
            result[step_id] = serialized_timing
        return result
    
    def _serialize_globals(self) -> Dict[str, Any]:
        """
        Sérialise les variables globales pour JSON.
        
        Returns:
            Variables globales sérialisables
        """
        return {k: self._make_serializable(v) for k, v in self.globals.items()}
    
    def _make_serializable(self, obj: Any) -> Any:
        """
        Rend un objet sérialisable pour JSON.
        
        Args:
            obj: L'objet à rendre sérialisable
        
        Returns:
            Version sérialisable de l'objet
        """
        # Traitement récursif des dictionnaires
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        # Traitement récursif des listes et tuples
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        # Conversion des objets datetime
        elif isinstance(obj, datetime):
            return obj.isoformat()
        # Conversion des objets bytes
        elif isinstance(obj, bytes):
            try:
                return obj.decode('utf-8')
            except UnicodeDecodeError:
                return str(obj)
        # Les types de base sont déjà sérialisables
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        # Pour tout autre type, convertir en chaîne
        else:
            try:
                return str(obj)
            except Exception as e:
                logger.warning(f"Échec de la sérialisation: {e}")
                return f"<Non sérialisable: {type(obj).__name__}>" 