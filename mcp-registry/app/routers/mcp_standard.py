"""
Endpoints standardisés pour la compatibilité avec le Model Context Protocol.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Body
from typing import Dict, Any, List, Optional
import json

from ..core.registry import MCPRegistry

router = APIRouter(
    tags=["mcp-standard"],
    responses={404: {"description": "Not found"}},
)

# Utiliser l'instance existante du registry
from ..api.router import registry

@router.get("/info")
async def get_mcp_info():
    """
    Endpoint standardisé pour les informations du MCP Registry.
    Compatible avec le standard MCP.
    """
    return await registry.get_info()

@router.get("/servers")
async def get_mcp_servers():
    """
    Endpoint standardisé pour obtenir la liste des serveurs MCP.
    """
    return {
        "servers": await registry.get_servers()
    }

@router.get("/tools")
async def get_mcp_tools(query: Optional[str] = None):
    """
    Endpoint standardisé pour obtenir la liste des outils MCP.
    Peut inclure un paramètre de recherche pour filtrer les outils.
    Compatible avec le standard MCP.
    """
    if query:
        # Si une requête de recherche est fournie, utiliser la recherche sémantique
        search_results = await registry.search_tools(query, limit=10)
        tools = [tool.dict() for tool in search_results]
    else:
        # Sinon, renvoyer tous les outils
        all_tools = await registry.get_tools()
        tools = [tool.dict() for tool in all_tools]
    
    # Normaliser le format des outils selon le standard MCP
    formatted_tools = []
    for tool in tools:
        # Assurer que les outils ont le format attendu
        formatted_tool = {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("parameters", {})
        }
        formatted_tools.append(formatted_tool)
    
    return {
        "tools": formatted_tools
    }

@router.post("/execute")
async def execute_mcp_tool(request: Request):
    """
    Endpoint standardisé pour exécuter un outil MCP.
    Compatible avec le standard MCP.
    """
    try:
        # Lire et analyser le corps de la requête
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Requête JSON invalide")
    
    # Extraire les données de la requête selon plusieurs formats possibles
    tool_name = None
    parameters = {}
    
    # Format 1: {"name": "...", "parameters": {...}}
    if "name" in body:
        tool_name = body["name"]
        parameters = body.get("parameters", {})
    # Format 2: {"tool": "...", "parameters": {...}}
    elif "tool" in body:
        tool_name = body["tool"]
        parameters = body.get("parameters", {})
    # Format 3: {"function": "...", "arguments": {...}}
    elif "function" in body:
        tool_name = body["function"]
        parameters = body.get("arguments", {})
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                parameters = {"text": parameters}
    else:
        raise HTTPException(status_code=400, detail="Format de requête non reconnu")
    
    # Déterminer le serveur à utiliser
    server_id = body.get("server_id")
    
    # Si aucun serveur n'est spécifié, essayer d'analyser l'intention pour déterminer le meilleur serveur
    if not server_id:
        result = await registry.analyze_intent(tool_name, parameters)
        server_id = result.get("server_id")
        
        if not server_id:
            # Parcourir tous les serveurs pour trouver celui qui a l'outil
            all_tools = await registry.get_tools()
            for tool in all_tools:
                if tool.name == tool_name:
                    server_id = tool.server_id
                    break
    
    if not server_id:
        raise HTTPException(status_code=404, detail=f"Aucun serveur trouvé pour l'outil {tool_name}")
    
    # Exécuter l'outil
    try:
        result = await registry.execute_tool(server_id, tool_name, parameters)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'exécution de l'outil: {str(e)}")

@router.post("/tools/{tool_name}/execute")
async def execute_specific_tool(tool_name: str, parameters: Dict[str, Any] = Body(...)):
    """
    Endpoint alternatif pour exécuter un outil spécifique par son nom.
    Format utilisé par Claude Desktop et d'autres clients.
    """
    # Rechercher l'outil par son nom
    all_tools = await registry.get_tools()
    server_id = None
    
    for tool in all_tools:
        if tool.name == tool_name:
            server_id = tool.server_id
            break
    
    if not server_id:
        raise HTTPException(status_code=404, detail=f"Outil {tool_name} non trouvé")
    
    # Exécuter l'outil
    try:
        result = await registry.execute_tool(server_id, tool_name, parameters)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'exécution de l'outil: {str(e)}") 