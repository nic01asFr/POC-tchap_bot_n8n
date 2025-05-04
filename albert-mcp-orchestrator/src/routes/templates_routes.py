"""
Routes pour la gestion des templates de compositions MCP.

Ce module définit les endpoints pour créer, lire, mettre à jour et supprimer
des templates de compositions MCP.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
import json
import os
from pathlib import Path

from ..core.auth import get_api_key, check_admin_permission
from ..config import settings

# Création du routeur avec préfixe et tags pour la documentation
router = APIRouter(
    prefix="/templates",
    tags=["Templates"],
    dependencies=[Depends(get_api_key)],
    responses={404: {"description": "Ressource non trouvée"}},
)

@router.get("/", summary="Liste tous les templates")
async def get_templates(
    category: Optional[str] = Query(None, description="Filtre sur la catégorie")
) -> List[Dict[str, Any]]:
    """
    Récupère la liste des templates disponibles.
    
    Optionnellement, filtrer par catégorie.
    """
    try:
        # Répertoire des templates
        base_directory = settings.TEMPLATES_COMPOSITIONS_DIR
                
        # Liste pour stocker les templates
        templates = []
        
        # Recherche des fichiers JSON dans le répertoire
        for file_path in base_directory.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    template = json.load(file)
                    
                    # Filtrer par catégorie si spécifiée
                    if category and template.get("category") != category:
                        continue
                        
                    # Ajouter le chemin au fichier
                    template["file_path"] = str(file_path)
                    templates.append(template)
            except json.JSONDecodeError:
                # Ignorer les fichiers JSON non valides
                continue
        
        return templates
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des templates: {str(e)}"
        )

@router.get("/{template_id}", summary="Récupère un template spécifique")
async def get_template(template_id: str) -> Dict[str, Any]:
    """
    Récupère les détails d'un template spécifique par son ID.
    """
    try:
        file_path = settings.TEMPLATES_COMPOSITIONS_DIR / f"{template_id}.json"
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_id}' non trouvé"
            )
            
        with open(file_path, "r", encoding="utf-8") as file:
            template = json.load(file)
            template["file_path"] = str(file_path)
            return template
            
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Format de fichier JSON invalide"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération du template: {str(e)}"
        )

@router.post("/", summary="Crée un nouveau template", dependencies=[Depends(check_admin_permission)])
async def create_template(template: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crée un nouveau template de composition MCP.
    
    Nécessite des droits d'administration.
    """
    try:
        # Validation des champs obligatoires
        if not template.get("id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le champ 'id' est obligatoire"
            )
            
        template_id = template["id"]
        
        # Vérifier si le template existe déjà
        file_path = settings.TEMPLATES_COMPOSITIONS_DIR / f"{template_id}.json"
        
        if file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Un template avec l'id '{template_id}' existe déjà"
            )
            
        # Sauvegarder le fichier
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(template, file, indent=2, ensure_ascii=False)
            
        template["file_path"] = str(file_path)
        return template
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création du template: {str(e)}"
        )

@router.put("/{template_id}", summary="Met à jour un template existant", dependencies=[Depends(check_admin_permission)])
async def update_template(template_id: str, template: Dict[str, Any]) -> Dict[str, Any]:
    """
    Met à jour un template existant.
    
    Nécessite des droits d'administration.
    """
    try:
        # Vérifier si le template existe
        file_path = settings.TEMPLATES_COMPOSITIONS_DIR / f"{template_id}.json"
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_id}' non trouvé"
            )
                
        # S'assurer que l'ID dans le corps correspond à l'ID dans l'URL
        if template.get("id") and template["id"] != template_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="L'ID dans le corps de la requête ne correspond pas à l'ID dans l'URL"
            )
            
        # Mettre à jour l'ID si nécessaire
        template["id"] = template_id
        
        # Sauvegarder le fichier mis à jour
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(template, file, indent=2, ensure_ascii=False)
            
        template["file_path"] = str(file_path)
        return template
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour du template: {str(e)}"
        )

@router.delete("/{template_id}", summary="Supprime un template", dependencies=[Depends(check_admin_permission)])
async def delete_template(template_id: str) -> Dict[str, str]:
    """
    Supprime un template existant.
    
    Nécessite des droits d'administration.
    """
    try:
        # Vérifier si le template existe
        file_path = settings.TEMPLATES_COMPOSITIONS_DIR / f"{template_id}.json"
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_id}' non trouvé"
            )
                
        # Supprimer le fichier
        os.remove(file_path)
        
        return {"message": f"Template '{template_id}' supprimé avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression du template: {str(e)}"
        )

@router.post("/{template_id}/create-composition", summary="Crée une composition à partir d'un template")
async def create_composition_from_template(
    template_id: str, 
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Crée une nouvelle composition à partir d'un template.
    
    Parameters:
        template_id: ID du template à utiliser
        parameters: Paramètres pour personnaliser la composition
    """
    try:
        # Récupérer le template
        template = await get_template(template_id)
        
        # Vérifier que l'ID de la nouvelle composition est fourni
        composition_id = parameters.get("composition_id")
        if not composition_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le paramètre 'composition_id' est obligatoire"
            )
            
        # Créer une nouvelle composition à partir du template
        composition = template.copy()
        del composition["file_path"]  # Supprimer le chemin du fichier du template
        
        # Mettre à jour l'ID et les autres paramètres
        composition["id"] = composition_id
        composition["source_template"] = template_id
        
        # Fusionner les paramètres spécifiques
        for key, value in parameters.items():
            if key != "composition_id":
                composition[key] = value
                
        # Sauvegarder la nouvelle composition dans le répertoire learning
        file_path = settings.LEARNING_COMPOSITIONS_DIR / f"{composition_id}.json"
        
        # Vérifier si une composition avec cet ID existe déjà
        if file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Une composition avec l'ID '{composition_id}' existe déjà"
            )
            
        # Sauvegarder la composition
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(composition, file, indent=2, ensure_ascii=False)
            
        composition["file_path"] = str(file_path)
        return composition
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création de la composition à partir du template: {str(e)}"
        ) 