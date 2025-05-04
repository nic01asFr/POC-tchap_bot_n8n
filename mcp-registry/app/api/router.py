"""
Routes de l'API pour le MCP Registry.
"""

import logging
import os
import json
import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Dict, Any, Optional
import time

from ..core.registry import MCPRegistry
from ..config import settings
from .models import (
    ServerInfo, 
    ToolInfo, 
    SearchQuery, 
    ExecuteToolRequest, 
    ErrorResponse,
    ApiInfo
)

# Configuration du logging
logger = logging.getLogger("mcp_registry.api")

# Créer le routeur FastAPI
router = APIRouter(tags=["MCP Registry"])

# Instance globale du registre MCP
registry = MCPRegistry()

# Configuration Albert API
ALBERT_API_URL = os.environ.get("ALBERT_API_URL", "https://albert.api.etalab.gouv.fr")
ALBERT_API_TOKEN = os.environ.get("ALBERT_API_TOKEN", "")
ALBERT_MODEL = os.environ.get("ALBERT_MODEL", "mixtral-8x7b-instruct-v0.1")

@router.get("/api/status", response_model=Dict[str, Any])
async def get_api_status():
    """Récupère le statut de l'API."""
    return {
        "status": "ok",
        "version": settings.app.version,
        "servers_count": len(registry.servers),
        "tools_count": len(registry.tools)
    }

@router.get("/", response_model=ApiInfo)
async def get_api_info():
    """Récupère les informations sur l'API."""
    return ApiInfo(
        name=settings.app.name,
        version=settings.app.version,
        description=settings.app.description
    )

@router.get("/api/servers", response_model=List[ServerInfo])
@router.get("/servers", response_model=List[ServerInfo])
async def get_servers():
    """
    Récupère la liste des serveurs MCP disponibles.
    """
    try:
        servers = await registry.get_servers()
        return servers
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération des serveurs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/tools", response_model=List[ToolInfo])
@router.get("/tools", response_model=List[ToolInfo])
async def get_tools(refresh: bool = Query(False, description="Forcer le rafraîchissement")):
    """
    Récupère la liste de tous les outils disponibles.
    
    - **refresh**: Forcer le rafraîchissement des serveurs
    """
    try:
        tools = await registry.get_all_tools(refresh=refresh)
        return tools
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération des outils: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/tools/{tool_id}", response_model=Optional[ToolInfo])
@router.get("/tools/{tool_id}", response_model=Optional[ToolInfo])
async def get_tool(tool_id: str):
    """
    Récupère les détails d'un outil par son identifiant.
    
    - **tool_id**: Identifiant complet de l'outil (server_id:tool_name)
    """
    try:
        tool = await registry.get_tool_by_id(tool_id)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Outil {tool_id} non trouvé")
        return tool
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération de l'outil {tool_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/search", response_model=List[ToolInfo])
@router.post("/search", response_model=List[ToolInfo])
async def search_tools(query: SearchQuery):
    """
    Recherche des outils par requête sémantique.
    
    - **query**: Texte de la requête
    - **limit**: Nombre maximum d'outils à retourner
    """
    try:
        tools = await registry.get_tools_for_query(query.query, query.limit)
        return tools
    except Exception as e:
        logger.exception(f"Erreur lors de la recherche d'outils: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/execute", response_model=Dict[str, Any])
@router.post("/execute", response_model=Dict[str, Any])
async def execute_tool(request: ExecuteToolRequest):
    """
    Exécute un outil sur un serveur MCP.
    
    - **server_id**: Identifiant du serveur MCP
    - **tool_id**: Identifiant de l'outil
    - **parameters**: Paramètres à passer à l'outil
    """
    try:
        result = await registry.execute_tool(
            server_id=request.server_id,
            tool_id=request.tool_id,
            parameters=request.parameters
        )
        
        if "error" in result:
            logger.error(f"Erreur lors de l'exécution de l'outil: {result['error']}")
            raise HTTPException(
                status_code=400, 
                detail=result.get("message", result["error"])
            )
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erreur lors de l'exécution de l'outil: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/analyze")
async def analyze_intent(query: Dict[str, Any] = Body(...)):
    """
    Analyse l'intention d'un message utilisateur et recommande des outils pertinents.
    
    Cette route utilise Albert API pour analyser l'intention de l'utilisateur
    et le MCP Registry pour trouver des outils correspondants.
    
    Args:
        query: Requête contenant le message à analyser
        
    Returns:
        Analyse d'intention avec les outils recommandés
    """
    message = query.get("message", "")
    sender = query.get("sender", "")
    
    logger.info(f"Analyse d'intention pour le message: {message[:50]}...")
    
    if not message:
        raise HTTPException(status_code=400, detail="Le message est requis")
    
    try:
        # 1. Rechercher des outils pertinents pour le message
        relevant_tools = await registry.search_tools(message, limit=5)
        
        # 2. Formater les descriptions des outils pour Albert
        tools_descriptions = []
        for tool in relevant_tools:
            # Vérifier si l'outil possède les champs requis
            name = tool.get("name", "")
            description = tool.get("description", "")
            tool_id = tool.get("id", "")
            
            if name and tool_id:
                params_info = ""
                params = tool.get("parameters", {})
                
                # Extraire les informations sur les paramètres si disponibles
                if params and isinstance(params, dict) and "properties" in params:
                    properties = params.get("properties", {})
                    params_info = ", ".join([
                        f"{name}: {prop.get('description', '')}" 
                        for name, prop in properties.items()
                    ])
                
                tool_desc = f"- {name} (id: {tool_id}): {description}"
                if params_info:
                    tool_desc += f". Paramètres: {params_info}"
                
                tools_descriptions.append(tool_desc)
        
        # 3. Analyser l'intention avec Albert API si un token est disponible
        intent_analysis = {}
        
        if ALBERT_API_TOKEN:
            try:
                headers = {
                    "Authorization": f"Bearer {ALBERT_API_TOKEN}",
                    "Content-Type": "application/json"
                }
                
                tools_context = "\n".join(tools_descriptions) if tools_descriptions else "Aucun outil disponible"
                
                prompt = f"""
                Analyse l'intention de l'utilisateur et identifie si un des outils disponibles peut répondre à sa demande.
                
                Voici les outils disponibles:
                {tools_context}
                
                Message de l'utilisateur: "{message}"
                
                Réponds au format JSON avec:
                1. "intent": le type d'intention détecté (ex: "grist_query", "weather_request", etc.)
                2. "confidence": niveau de confiance (0 à 1)
                3. "requires_tool": booléen indiquant si un outil est nécessaire
                4. "tool_id": l'ID de l'outil recommandé (ou null si aucun)
                5. "tool_args": les arguments recommandés pour l'outil (objet)
                6. "rationale": explication de ton raisonnement
                """
                
                # Appeler l'API Albert pour analyser l'intention
                response = requests.post(
                    f"{ALBERT_API_URL}/chat/completions",
                    headers=headers,
                    json={
                        "model": ALBERT_MODEL,
                        "messages": [
                            {"role": "system", "content": "Tu es un assistant d'analyse d'intention. Réponds uniquement au format JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.2
                    }
                )
                
                if response.status_code == 200:
                    # Extraire la réponse de l'API Albert
                    albert_response = response.json()
                    answer_text = albert_response.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    # Essayer de parser la réponse comme JSON
                    try:
                        # Extraire seulement la partie JSON si la réponse contient du texte supplémentaire
                        json_str = answer_text
                        if "```json" in answer_text:
                            json_str = answer_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in answer_text:
                            json_str = answer_text.split("```")[1].strip()
                        
                        intent_analysis = json.loads(json_str)
                        logger.info(f"Analyse d'intention réussie: {intent_analysis.get('intent')}")
                    except json.JSONDecodeError:
                        logger.error(f"Impossible de parser la réponse JSON: {answer_text}")
                        # Fournir une analyse par défaut
                        intent_analysis = {
                            "intent": "unknown",
                            "confidence": 0.0,
                            "requires_tool": False,
                            "error": "Erreur de parsing JSON",
                            "raw_response": answer_text
                        }
                else:
                    logger.error(f"Erreur lors de l'appel à Albert API: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Exception lors de l'analyse d'intention: {str(e)}")
        
        # 4. Si l'analyse Albert a échoué ou n'est pas disponible, faire une analyse simplifiée
        if not intent_analysis:
            # Analyse simplifiée basée sur les outils trouvés
            if relevant_tools:
                top_tool = relevant_tools[0]
                score = top_tool.get("similarity_score", 0)
                
                intent_analysis = {
                    "intent": "tool_request",
                    "confidence": min(score, 0.95),  # Limiter la confiance à 0.95 max
                    "requires_tool": True,
                    "tool_id": top_tool.get("id"),
                    "server_id": top_tool.get("server_id"),
                    "tool_args": {},
                    "rationale": f"L'outil '{top_tool.get('name')}' semble correspondre à la demande de l'utilisateur"
                }
            else:
                intent_analysis = {
                    "intent": None,
                    "confidence": 0.0,
                    "requires_tool": False,
                    "tool_id": None,
                    "rationale": "Aucun outil ne correspond à cette demande"
                }
        
        # 5. Construire la réponse finale
        response = {
            "intent": intent_analysis.get("intent"),
            "confidence": intent_analysis.get("confidence", 0.0),
            "requires_tool": intent_analysis.get("requires_tool", False),
            "tool_id": intent_analysis.get("tool_id"),
            "server_id": intent_analysis.get("server_id", getattr(intent_analysis.get("tool", {}), "server_id", None)),
            "tool_args": intent_analysis.get("tool_args", {}),
            "tools": relevant_tools[:3],  # Inclure les 3 meilleurs outils
            "rationale": intent_analysis.get("rationale", "")
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse d'intention: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse d'intention: {str(e)}")

# Alias pour les autres endpoints d'analyse d'intention
@router.post("/intent/analyze")
async def intent_analyze_alias(query: Dict[str, Any] = Body(...)):
    """Alias pour /api/analyze"""
    return await analyze_intent(query)

@router.post("/api/intent")
async def api_intent_alias(query: Dict[str, Any] = Body(...)):
    """Alias pour /api/analyze"""
    return await analyze_intent(query)

# Endpoint pour vérifier que le service fonctionne
@router.get("/api/ping")
async def api_ping():
    """Vérifie que le service fonctionne."""
    return {"status": "ok", "timestamp": time.time()} 