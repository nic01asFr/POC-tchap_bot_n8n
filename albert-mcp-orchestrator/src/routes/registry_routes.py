"""
Routes pour l'interaction avec le registre MCP.

Ce module définit les endpoints pour découvrir et interagir avec
les serveurs et outils MCP enregistrés dans le registre.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
import json

from ..core.auth import get_api_key, check_admin_permission
from ..config import settings
from ..registry.mcp_registry import MCPRegistry

# Création du routeur avec préfixe et tags pour la documentation
router = APIRouter(
    prefix="/registry",
    tags=["MCP Registry"],
    dependencies=[Depends(get_api_key)],
    responses={404: {"description": "Ressource non trouvée"}},
)

@router.get("/servers", summary="Liste tous les serveurs MCP")
async def get_servers() -> List[Dict[str, Any]]:
    """
    Récupère la liste des serveurs MCP enregistrés.
    """
    try:
        registry = MCPRegistry.get_instance()
        if not registry or not registry._initialized:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le registre MCP n'est pas disponible"
            )
        
        servers = registry.get_servers()
        return servers
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des serveurs MCP: {str(e)}"
        )

@router.get("/servers/{server_id}", summary="Récupère un serveur MCP spécifique")
async def get_server(server_id: str) -> Dict[str, Any]:
    """
    Récupère les détails d'un serveur MCP spécifique par son ID.
    """
    try:
        registry = MCPRegistry.get_instance()
        if not registry or not registry._initialized:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le registre MCP n'est pas disponible"
            )
        
        server = registry.get_server(server_id)
        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Serveur MCP '{server_id}' non trouvé"
            )
        
        return server
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération du serveur MCP: {str(e)}"
        )

@router.get("/tools", summary="Liste tous les outils MCP")
async def get_tools(
    server_id: Optional[str] = Query(None, description="Filtre par serveur MCP"),
    category: Optional[str] = Query(None, description="Filtre par catégorie")
) -> List[Dict[str, Any]]:
    """
    Récupère la liste des outils MCP disponibles.
    
    Optionnellement, filtrer par serveur ou catégorie.
    """
    try:
        registry = MCPRegistry.get_instance()
        if not registry or not registry._initialized:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le registre MCP n'est pas disponible"
            )
        
        tools = registry.get_tools(server_id=server_id, category=category)
        return tools
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des outils MCP: {str(e)}"
        )

@router.get("/tools/{tool_id}", summary="Récupère un outil MCP spécifique")
async def get_tool(tool_id: str) -> Dict[str, Any]:
    """
    Récupère les détails d'un outil MCP spécifique par son ID.
    """
    try:
        registry = MCPRegistry.get_instance()
        if not registry or not registry._initialized:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le registre MCP n'est pas disponible"
            )
        
        tool = registry.get_tool(tool_id)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Outil MCP '{tool_id}' non trouvé"
            )
        
        return tool
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'outil MCP: {str(e)}"
        )

@router.post("/discover", summary="Découvre de nouveaux serveurs MCP", dependencies=[Depends(check_admin_permission)])
async def discover_servers() -> Dict[str, Any]:
    """
    Force la découverte de nouveaux serveurs MCP.
    
    Nécessite des droits d'administration.
    """
    try:
        registry = MCPRegistry.get_instance()
        if not registry or not registry._initialized:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le registre MCP n'est pas disponible"
            )
        
        result = await registry.discover_servers()
        return {
            "message": "Découverte des serveurs MCP effectuée",
            "servers_discovered": result.get("servers_discovered", 0),
            "servers": result.get("servers", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la découverte des serveurs MCP: {str(e)}"
        )

@router.post("/register-with-albert", summary="Enregistre les outils MCP auprès d'Albert", dependencies=[Depends(check_admin_permission)])
async def register_with_albert() -> Dict[str, Any]:
    """
    Enregistre les outils MCP auprès d'Albert Tchapbot.
    
    Nécessite des droits d'administration.
    """
    try:
        from ..registry.mcp_integration import register_tools_with_albert
        
        registry = MCPRegistry.get_instance()
        if not registry or not registry._initialized:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le registre MCP n'est pas disponible"
            )
        
        tools_manifest = registry.get_tools_manifest()
        success = await register_tools_with_albert(tools_manifest)
        
        if success:
            return {
                "message": "Enregistrement des outils MCP auprès d'Albert réussi",
                "tools_count": len(tools_manifest)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Échec de l'enregistrement des outils MCP auprès d'Albert"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'enregistrement des outils MCP auprès d'Albert: {str(e)}"
        )

@router.get("/status", summary="Vérifie l'état du registre MCP")
async def check_registry_status() -> Dict[str, Any]:
    """
    Vérifie l'état du registre MCP et sa connexion.
    """
    try:
        registry = MCPRegistry.get_instance()
        
        if not registry:
            return {
                "status": "unavailable",
                "message": "Le registre MCP n'est pas initialisé"
            }
            
        if not registry._initialized:
            return {
                "status": "initializing",
                "message": "Le registre MCP est en cours d'initialisation"
            }
            
        # Vérifier la connexion au registre
        health_status = await registry.check_health()
        
        if health_status:
            return {
                "status": "online",
                "message": "Le registre MCP est opérationnel",
                "servers_count": len(registry.get_servers()),
                "tools_count": len(registry.get_tools())
            }
        else:
            return {
                "status": "degraded",
                "message": "Le registre MCP est en mode dégradé"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la vérification de l'état du registre MCP: {str(e)}"
        } 