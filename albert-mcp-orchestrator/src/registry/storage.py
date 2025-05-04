import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import shutil
from datetime import datetime
import uuid

from ..models.composition import Composition, CompositionStatus
from ..config import settings
from loguru import logger


class CompositionStorage:
    """
    Gestionnaire de stockage des compositions MCP.
    Gère le stockage, le chargement et la manipulation des fichiers de composition.
    """
    
    def __init__(self):
        """Initialise le gestionnaire de stockage."""
        self.validated_dir = settings.VALIDATED_COMPOSITIONS_DIR
        self.learning_dir = settings.LEARNING_COMPOSITIONS_DIR
        self.templates_dir = settings.TEMPLATES_COMPOSITIONS_DIR
        self.production_dir = settings.PRODUCTION_COMPOSITIONS_DIR
        self.archived_dir = settings.ARCHIVED_COMPOSITIONS_DIR
        
        # Créer les répertoires s'ils n'existent pas
        for directory in [self.validated_dir, self.learning_dir, self.templates_dir, self.production_dir, self.archived_dir]:
            os.makedirs(directory, exist_ok=True)
    
    def get_storage_path(self, composition: Union[Composition, str], status: Optional[CompositionStatus] = None) -> Path:
        """
        Détermine le chemin de stockage d'une composition en fonction de son statut.
        
        Args:
            composition: La composition ou son ID
            status: Le statut souhaité (si différent du statut actuel de la composition)
        
        Returns:
            Le chemin où la composition doit être stockée
        """
        composition_id = composition if isinstance(composition, str) else composition.id
        
        if status is None and not isinstance(composition, str):
            status = composition.status
        elif status is None:
            # Si on a juste l'ID et pas de statut spécifié, chercher dans tous les répertoires
            for directory in [self.validated_dir, self.learning_dir, self.templates_dir, self.production_dir]:
                file_path = directory / f"{composition_id}.json"
                if file_path.exists():
                    return file_path
            
            # Par défaut, si non trouvé, considérer comme une nouvelle composition en apprentissage
            return self.learning_dir / f"{composition_id}.json"
        
        # Déterminer le répertoire en fonction du statut
        if status == CompositionStatus.VALIDATED:
            return self.validated_dir / f"{composition_id}.json"
        elif status == CompositionStatus.LEARNING:
            return self.learning_dir / f"{composition_id}.json"
        elif status == CompositionStatus.DRAFT:
            return self.templates_dir / f"{composition_id}.json"
        elif status == CompositionStatus.PRODUCTION:
            return self.production_dir / f"{composition_id}.json"
        else:  # ARCHIVED ou autre
            return self.archived_dir / f"{composition_id}.json"
    
    def save_composition(self, composition: Composition) -> str:
        """
        Sauvegarde une composition dans le bon répertoire.
        
        Args:
            composition: La composition à sauvegarder
        
        Returns:
            Le chemin où la composition a été sauvegardée
        """
        # Mettre à jour le timestamp
        composition.updated_at = datetime.now()
        
        # Déterminer le chemin de sauvegarde
        file_path = self.get_storage_path(composition)
        
        # Sérialiser et sauvegarder
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(composition.dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"Composition '{composition.name}' (ID: {composition.id}) sauvegardée dans {file_path}")
        return str(file_path)
    
    def load_composition(self, composition_id: str) -> Optional[Composition]:
        """
        Charge une composition depuis son ID.
        
        Args:
            composition_id: L'ID de la composition à charger
        
        Returns:
            La composition chargée ou None si non trouvée
        """
        # Chercher le fichier dans tous les répertoires
        for directory in [self.validated_dir, self.learning_dir, self.templates_dir, self.production_dir]:
            file_path = directory / f"{composition_id}.json"
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return Composition(**data)
                except Exception as e:
                    logger.error(f"Erreur lors du chargement de la composition {composition_id}: {e}")
                    return None
        
        logger.warning(f"Composition {composition_id} non trouvée.")
        return None
    
    def list_compositions(self, status: Optional[CompositionStatus] = None) -> List[Composition]:
        """
        Liste toutes les compositions avec un statut optionnel.
        
        Args:
            status: Le statut des compositions à lister (None pour toutes)
        
        Returns:
            La liste des compositions correspondantes
        """
        compositions = []
        
        # Déterminer les répertoires à explorer
        directories = []
        if status == CompositionStatus.VALIDATED:
            directories = [self.validated_dir]
        elif status == CompositionStatus.LEARNING:
            directories = [self.learning_dir]
        elif status == CompositionStatus.DRAFT:
            directories = [self.templates_dir]
        elif status == CompositionStatus.PRODUCTION:
            directories = [self.production_dir]
        elif status == CompositionStatus.ARCHIVED:
            directories = [self.archived_dir]
        else:
            directories = [self.validated_dir, self.learning_dir, self.templates_dir, self.production_dir, self.archived_dir]
        
        # Charger les compositions
        for directory in directories:
            for file_path in directory.glob("*.json"):
                if file_path.name.startswith("archived_") and status != CompositionStatus.ARCHIVED:
                    continue
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    composition = Composition(**data)
                    
                    # Vérifier que le statut correspond si spécifié
                    if status is None or composition.status == status:
                        compositions.append(composition)
                except Exception as e:
                    logger.error(f"Erreur lors du chargement de {file_path}: {e}")
        
        return compositions
    
    def delete_composition(self, composition_id: str) -> bool:
        """
        Supprime une composition.
        
        Args:
            composition_id: L'ID de la composition à supprimer
        
        Returns:
            True si la suppression a réussi, False sinon
        """
        # Rechercher la composition dans tous les répertoires
        for directory in [self.validated_dir, self.learning_dir, self.templates_dir, self.production_dir]:
            file_path = directory / f"{composition_id}.json"
            if file_path.exists():
                try:
                    os.remove(file_path)
                    logger.info(f"Composition {composition_id} supprimée de {file_path}")
                    return True
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression de {composition_id}: {e}")
                    return False
        
        logger.warning(f"Composition {composition_id} non trouvée pour suppression.")
        return False
    
    def change_composition_status(self, composition_id: str, new_status: CompositionStatus) -> Optional[Composition]:
        """
        Change le statut d'une composition et la déplace vers le bon répertoire.
        
        Args:
            composition_id: L'ID de la composition
            new_status: Le nouveau statut
        
        Returns:
            La composition mise à jour ou None si échec
        """
        # Charger la composition
        composition = self.load_composition(composition_id)
        if not composition:
            return None
        
        # Ancien et nouveau chemins
        old_path = self.get_storage_path(composition)
        
        # Mettre à jour le statut
        composition.status = new_status
        composition.updated_at = datetime.now()
        
        # Nouveau chemin
        new_path = self.get_storage_path(composition)
        
        # Sauvegarder au nouvel emplacement
        try:
            with open(new_path, "w", encoding="utf-8") as f:
                json.dump(composition.dict(), f, ensure_ascii=False, indent=2)
            
            # Supprimer l'ancien fichier s'il est différent
            if old_path != new_path and old_path.exists():
                os.remove(old_path)
            
            logger.info(f"Composition {composition_id} déplacée vers {new_path} avec statut {new_status}")
            return composition
        except Exception as e:
            logger.error(f"Erreur lors du changement de statut de {composition_id}: {e}")
            return None
    
    def create_composition_from_template(self, template_id: str, new_data: Dict[str, Any]) -> Optional[Composition]:
        """
        Crée une nouvelle composition à partir d'un template.
        
        Args:
            template_id: L'ID du template
            new_data: Les nouvelles données à appliquer
        
        Returns:
            La nouvelle composition créée ou None si échec
        """
        # Charger le template
        template_path = self.templates_dir / f"{template_id}.json"
        if not template_path.exists():
            logger.error(f"Template {template_id} non trouvé.")
            return None
        
        try:
            # Charger le template
            with open(template_path, "r", encoding="utf-8") as f:
                template_data = json.load(f)
            
            # Créer une nouvelle composition avec un nouvel ID
            new_data = {**template_data, **new_data}
            new_data["id"] = str(uuid.uuid4())
            new_data["created_at"] = datetime.now().isoformat()
            new_data["updated_at"] = datetime.now().isoformat()
            
            # Par défaut en apprentissage
            new_data["status"] = CompositionStatus.LEARNING.value
            
            # Créer et sauvegarder
            composition = Composition(**new_data)
            self.save_composition(composition)
            
            logger.info(f"Nouvelle composition {composition.id} créée à partir du template {template_id}")
            return composition
        except Exception as e:
            logger.error(f"Erreur lors de la création depuis le template {template_id}: {e}")
            return None 