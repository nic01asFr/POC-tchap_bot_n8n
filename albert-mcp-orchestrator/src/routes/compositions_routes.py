"""
Routes pour la gestion des compositions MCP.

Ce module définit les endpoints pour créer, lire, mettre à jour et supprimer
des compositions MCP, ainsi que pour les exécuter.
"""

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import json
import os
from pathlib import Path

from ..core.auth import get_api_key
from ..config import settings

# Création du routeur avec préfixe et tags pour la documentation
router = APIRouter(
    prefix="/compositions",
    tags=["Compositions"],
    dependencies=[Depends(get_api_key)],
    responses={404: {"description": "Ressource non trouvée"}},
)

@router.get("/", summary="Liste toutes les compositions")
async def get_compositions(
    status: Optional[str] = Query(None, description="Filtre sur le statut (production, validated, learning, archived)"),
    category: Optional[str] = Query(None, description="Filtre sur la catégorie")
) -> List[Dict[str, Any]]:
    """
    Récupère la liste des compositions disponibles.
    
    Optionnellement, filtrer par statut ou catégorie.
    """
    try:
        # Emplacement par défaut (toutes les compositions)
        base_directory = settings.COMPOSITIONS_DIR
        
        # Si un statut est spécifié, changer le répertoire
        if status:
            if status == "production":
                base_directory = settings.PRODUCTION_COMPOSITIONS_DIR
            elif status == "validated":
                base_directory = settings.VALIDATED_COMPOSITIONS_DIR
            elif status == "learning":
                base_directory = settings.LEARNING_COMPOSITIONS_DIR
            elif status == "archived":
                base_directory = settings.ARCHIVED_COMPOSITIONS_DIR
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Statut '{status}' non reconnu"
                )
                
        # Liste pour stocker les compositions
        compositions = []
        
        # Recherche des fichiers JSON dans le répertoire
        for file_path in base_directory.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    composition = json.load(file)
                    
                    # Filtrer par catégorie si spécifiée
                    if category and composition.get("category") != category:
                        continue
                        
                    # Ajouter le chemin au fichier
                    composition["file_path"] = str(file_path)
                    compositions.append(composition)
            except json.JSONDecodeError:
                # Ignorer les fichiers JSON non valides
                continue
        
        return compositions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des compositions: {str(e)}"
        )

@router.get("/{composition_id}", summary="Récupère une composition spécifique")
async def get_composition(composition_id: str) -> Dict[str, Any]:
    """
    Récupère les détails d'une composition spécifique par son ID.
    """
    try:
        # Recherche dans tous les répertoires
        for directory in [
            settings.PRODUCTION_COMPOSITIONS_DIR,
            settings.VALIDATED_COMPOSITIONS_DIR,
            settings.LEARNING_COMPOSITIONS_DIR,
            settings.ARCHIVED_COMPOSITIONS_DIR
        ]:
            file_path = directory / f"{composition_id}.json"
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as file:
                    composition = json.load(file)
                    composition["file_path"] = str(file_path)
                    return composition
        
        # Si on arrive ici, la composition n'existe pas
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Composition '{composition_id}' non trouvée"
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Format de fichier JSON invalide"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de la composition: {str(e)}"
        )

@router.post("/", summary="Crée une nouvelle composition")
async def create_composition(composition: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crée une nouvelle composition MCP.
    """
    try:
        # Validation des champs obligatoires
        if not composition.get("id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le champ 'id' est obligatoire"
            )
            
        composition_id = composition["id"]
        
        # Vérifier l'unicité de l'ID
        existing_composition = None
        try:
            existing_composition = await get_composition(composition_id)
        except HTTPException:
            pass  # L'exception signifie que la composition n'existe pas, c'est ce qu'on veut
            
        if existing_composition:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Une composition avec l'id '{composition_id}' existe déjà"
            )
            
        # Par défaut, enregistrer dans le répertoire learning
        file_path = settings.LEARNING_COMPOSITIONS_DIR / f"{composition_id}.json"
        
        # Sauvegarder le fichier
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(composition, file, indent=2, ensure_ascii=False)
            
        composition["file_path"] = str(file_path)
        return composition
    except HTTPException:
        raise  # Relancer les exceptions HTTP déjà formatées
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création de la composition: {str(e)}"
        )

@router.put("/{composition_id}", summary="Met à jour une composition existante")
async def update_composition(composition_id: str, composition: Dict[str, Any]) -> Dict[str, Any]:
    """
    Met à jour une composition existante.
    """
    try:
        # Vérifier l'existence de la composition
        existing_composition = None
        file_path = None
        
        try:
            existing_composition = await get_composition(composition_id)
            file_path = Path(existing_composition["file_path"])
        except HTTPException as e:
            if e.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Composition '{composition_id}' non trouvée"
                )
            else:
                raise
                
        # S'assurer que l'ID dans le corps correspond à l'ID dans l'URL
        if composition.get("id") and composition["id"] != composition_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="L'ID dans le corps de la requête ne correspond pas à l'ID dans l'URL"
            )
            
        # Mettre à jour l'ID si nécessaire
        composition["id"] = composition_id
        
        # Sauvegarder le fichier mis à jour
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(composition, file, indent=2, ensure_ascii=False)
            
        composition["file_path"] = str(file_path)
        return composition
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour de la composition: {str(e)}"
        )

@router.delete("/{composition_id}", summary="Supprime une composition")
async def delete_composition(composition_id: str) -> Dict[str, str]:
    """
    Supprime une composition existante.
    """
    try:
        # Vérifier l'existence de la composition
        existing_composition = None
        file_path = None
        
        try:
            existing_composition = await get_composition(composition_id)
            file_path = Path(existing_composition["file_path"])
        except HTTPException as e:
            if e.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Composition '{composition_id}' non trouvée"
                )
            else:
                raise
                
        # Supprimer le fichier
        os.remove(file_path)
        
        return {"message": f"Composition '{composition_id}' supprimée avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression de la composition: {str(e)}"
        )

@router.post("/{composition_id}/execute", summary="Exécute une composition")
async def execute_composition(
    composition_id: str, 
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Exécute une composition MCP avec les paramètres spécifiés.
    """
    try:
        # Récupérer la composition
        composition = await get_composition(composition_id)
        
        # Placeholder pour l'exécution de la composition
        # En production, cela appellerait un service d'exécution
        
        return {
            "status": "success",
            "message": f"Exécution de la composition '{composition_id}' simulée",
            "composition": composition,
            "parameters": parameters or {},
            "result": {
                "execution_id": "sim-123456",
                "status": "completed",
                "output": {"message": "Simulation d'exécution réussie"}
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'exécution de la composition: {str(e)}"
        ) 