"""
Routes pour l'exécution des outils MCP.

Ce module définit les endpoints pour exécuter des outils MCP 
et récupérer les résultats de ces exécutions.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import json
import uuid
import asyncio
from datetime import datetime

from ..core.auth import get_api_key
from ..config import settings
from ..registry.mcp_registry import MCPRegistry

# Création du routeur avec préfixe et tags pour la documentation
router = APIRouter(
    prefix="/tools",
    tags=["Tools"],
    dependencies=[Depends(get_api_key)],
    responses={404: {"description": "Ressource non trouvée"}},
)

# Stockage en mémoire des résultats d'exécution (à remplacer par une BD en production)
_execution_results = {}
_execution_status = {}

@router.post("/execute/{tool_id}", summary="Exécute un outil MCP")
async def execute_tool(
    tool_id: str,
    parameters: Dict[str, Any],
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Exécute un outil MCP avec les paramètres spécifiés.
    
    Les exécutions sont asynchrones et leur statut peut être vérifié via l'endpoint /status.
    """
    try:
        registry = MCPRegistry.get_instance()
        if not registry or not registry._initialized:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le registre MCP n'est pas disponible"
            )
        
        # Récupérer l'outil
        tool = registry.get_tool(tool_id)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Outil MCP '{tool_id}' non trouvé"
            )
        
        # Générer un ID d'exécution unique
        execution_id = str(uuid.uuid4())
        
        # Initialiser le statut
        _execution_status[execution_id] = {
            "status": "pending",
            "tool_id": tool_id,
            "started_at": datetime.now().isoformat(),
            "parameters": parameters
        }
        
        # Ajouter la tâche d'exécution en arrière-plan
        background_tasks.add_task(
            _execute_tool_async,
            tool_id=tool_id,
            tool=tool,
            parameters=parameters,
            execution_id=execution_id
        )
        
        return {
            "execution_id": execution_id,
            "status": "pending",
            "message": f"Exécution de l'outil '{tool_id}' démarrée"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'exécution de l'outil: {str(e)}"
        )

@router.get("/status/{execution_id}", summary="Vérifie le statut d'une exécution")
async def check_execution_status(execution_id: str) -> Dict[str, Any]:
    """
    Vérifie le statut d'une exécution d'outil MCP.
    """
    if execution_id not in _execution_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exécution '{execution_id}' non trouvée"
        )
    
    status_info = _execution_status[execution_id].copy()
    
    # Si l'exécution est terminée, inclure les résultats
    if status_info["status"] == "completed" and execution_id in _execution_results:
        status_info["result"] = _execution_results[execution_id]
    
    return status_info

@router.get("/results/{execution_id}", summary="Récupère les résultats d'une exécution")
async def get_execution_results(execution_id: str) -> Dict[str, Any]:
    """
    Récupère les résultats d'une exécution d'outil MCP.
    """
    if execution_id not in _execution_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exécution '{execution_id}' non trouvée"
        )
    
    status_info = _execution_status[execution_id]
    
    if status_info["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"L'exécution '{execution_id}' n'est pas encore terminée (statut: {status_info['status']})"
        )
    
    if execution_id not in _execution_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Résultats de l'exécution '{execution_id}' non trouvés"
        )
    
    return {
        "execution_id": execution_id,
        "status": "completed",
        "tool_id": status_info["tool_id"],
        "started_at": status_info["started_at"],
        "completed_at": status_info.get("completed_at"),
        "result": _execution_results[execution_id]
    }

@router.delete("/results/{execution_id}", summary="Supprime les résultats d'une exécution")
async def delete_execution_results(execution_id: str) -> Dict[str, Any]:
    """
    Supprime les résultats d'une exécution d'outil MCP.
    """
    if execution_id not in _execution_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exécution '{execution_id}' non trouvée"
        )
    
    if execution_id in _execution_results:
        del _execution_results[execution_id]
    
    del _execution_status[execution_id]
    
    return {
        "message": f"Résultats de l'exécution '{execution_id}' supprimés"
    }

# Fonction d'exécution asynchrone en arrière-plan
async def _execute_tool_async(
    tool_id: str,
    tool: Dict[str, Any],
    parameters: Dict[str, Any],
    execution_id: str
):
    """
    Exécute un outil MCP de manière asynchrone.
    
    Met à jour le statut et les résultats de l'exécution.
    """
    try:
        # Mettre à jour le statut
        _execution_status[execution_id]["status"] = "running"
        
        # Obtenir le serveur MCP et les détails d'exécution
        registry = MCPRegistry.get_instance()
        server_id = tool.get("server_id")
        
        if not server_id:
            raise ValueError(f"L'outil '{tool_id}' n'a pas de serveur associé")
            
        server = registry.get_server(server_id)
        if not server:
            raise ValueError(f"Le serveur '{server_id}' n'est pas disponible")
            
        # Exécuter l'outil
        result = await registry.execute_tool(
            server_id=server_id,
            tool_id=tool_id,
            parameters=parameters,
            timeout=settings.EXECUTION_TIMEOUT_SECONDS
        )
        
        # Stocker les résultats
        _execution_results[execution_id] = result
        
        # Mettre à jour le statut
        _execution_status[execution_id]["status"] = "completed"
        _execution_status[execution_id]["completed_at"] = datetime.now().isoformat()
        
    except Exception as e:
        # En cas d'erreur, mettre à jour le statut
        _execution_status[execution_id]["status"] = "failed"
        _execution_status[execution_id]["error"] = str(e)
        _execution_status[execution_id]["completed_at"] = datetime.now().isoformat() 