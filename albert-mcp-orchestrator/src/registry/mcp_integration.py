"""
Module d'intégration entre le registre MCP et Albert Tchapbot.

Ce module fournit les fonctionnalités pour enregistrer les outils MCP
auprès d'Albert Tchapbot, permettant ainsi leur utilisation via le chatbot.
"""

import json
import aiohttp
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
from enum import Enum

from ..config import settings
from ..models.composition import Composition, CompositionStatus, ToolDefinition

logger = logging.getLogger(__name__)

async def register_tools_with_albert(tools_manifest: List[Dict[str, Any]]) -> bool:
    """
    Enregistre les outils MCP auprès d'Albert Tchapbot.
    
    Args:
        tools_manifest: Liste des outils MCP à enregistrer
        
    Returns:
        True si l'enregistrement a réussi, False sinon
    """
    if not tools_manifest:
        logger.warning("Aucun outil à enregistrer auprès d'Albert")
        return False
        
    if not hasattr(settings, 'ALBERT_TCHAP_API_URL') or not settings.ALBERT_TCHAP_API_URL:
        logger.error("URL de l'API Albert non configurée")
        return False
        
    try:
        api_url = f"{settings.ALBERT_TCHAP_API_URL}/mcp/register"
        
        # Préparer les données d'enregistrement
        registration_data = {
            "tools": tools_manifest,
            "source": "mcp_orchestrator",
            "version": settings.APP_VERSION
        }
        
        # Préparer les en-têtes
        headers = {"Content-Type": "application/json"}
        if hasattr(settings, 'ALBERT_TCHAP_API_KEY') and settings.ALBERT_TCHAP_API_KEY:
            headers["Authorization"] = f"Bearer {settings.ALBERT_TCHAP_API_KEY}"
            
        # Envoyer la requête
        async with aiohttp.ClientSession() as session:
            async with session.post(
                api_url,
                json=registration_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    response_data = await response.json()
                    logger.info(f"Outils MCP enregistrés auprès d'Albert: {len(tools_manifest)} outils")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Erreur lors de l'enregistrement des outils auprès d'Albert: {response.status} - {error_text}")
                    return False
    except Exception as e:
        logger.error(f"Exception lors de l'enregistrement des outils auprès d'Albert: {str(e)}")
        return False

async def format_tool_for_albert(tool: Dict[str, Any]) -> Dict[str, Any]:
    """
    Formate un outil MCP pour l'utilisation avec Albert Tchapbot.
    
    Args:
        tool: Description de l'outil MCP
        
    Returns:
        Outil formaté pour Albert
    """
    # Vérifier les champs requis
    if not tool.get("id") or not tool.get("name"):
        logger.warning(f"Outil MCP invalide (manque id ou name): {json.dumps(tool)}")
        return None
        
    # Formater l'outil pour Albert
    formatted_tool = {
        "id": tool["id"],
        "name": tool["name"],
        "description": tool.get("description", ""),
        "category": tool.get("category", "MCP"),
        "parameters": tool.get("parameters", []),
    }
    
    # Ajouter les champs facultatifs
    if "server_id" in tool:
        formatted_tool["server_id"] = tool["server_id"]
        
    if "url" in tool:
        formatted_tool["url"] = tool["url"]
        
    return formatted_tool

class MCPToolGenerator:
    """
    Générateur d'outils MCP à partir des compositions.
    Convertit les compositions en format d'outil MCP prêt à être exposé à Albert Tchapbot.
    """
    
    def __init__(self):
        """Initialise le générateur d'outils MCP."""
        pass
    
    def composition_to_mcp_tool(self, composition: Composition) -> Dict[str, Any]:
        """
        Convertit une composition en outil MCP.
        
        Args:
            composition: La composition à convertir
        
        Returns:
            Définition de l'outil MCP au format JSON
        """
        # Extraire les paramètres d'entrée du schéma
        parameters = self._extract_parameters_from_schema(composition.input_schema)
        
        # Créer la définition de l'outil
        tool_definition = {
            "id": f"mcp_composition_{composition.id}",
            "name": composition.name,
            "description": composition.description,
            "category": "Compositions",
            "server_id": "mcp_orchestrator",
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": self._get_required_params(composition.input_schema),
            }
        }
        
        return tool_definition
    
    def _extract_parameters_from_schema(self, schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Extrait les paramètres depuis un schéma JSON.
        
        Args:
            schema: Schéma JSON des entrées
        
        Returns:
            Dictionnaire de paramètres au format MCP
        """
        properties = schema.get("properties", {})
        result = {}
        
        for name, prop in properties.items():
            param_def = {
                "type": prop.get("type", "string"),
                "title": prop.get("title", name),
            }
            
            # Ajouter la description si disponible
            if "description" in prop:
                param_def["description"] = prop["description"]
            
            # Traiter les formats spéciaux
            if "format" in prop:
                param_def["format"] = prop["format"]
            
            # Traiter les valeurs par défaut
            if "default" in prop:
                param_def["default"] = prop["default"]
            
            # Traiter les contraintes
            for constraint in ["minimum", "maximum", "minLength", "maxLength", "pattern"]:
                if constraint in prop:
                    param_def[constraint] = prop[constraint]
            
            # Traiter les énumérations
            if "enum" in prop:
                param_def["enum"] = prop["enum"]
            
            result[name] = param_def
        
        return result
    
    def _get_required_params(self, schema: Dict[str, Any]) -> List[str]:
        """
        Extrait les paramètres requis depuis un schéma JSON.
        
        Args:
            schema: Schéma JSON des entrées
        
        Returns:
            Liste des noms de paramètres requis
        """
        return schema.get("required", [])
    
    def generate_mcp_tools_manifest(self, compositions: List[Composition]) -> List[Dict[str, Any]]:
        """
        Génère un manifeste d'outils MCP à partir d'une liste de compositions.
        
        Args:
            compositions: Liste des compositions à convertir
        
        Returns:
            Liste d'outils MCP au format JSON
        """
        tools = []
        
        for composition in compositions:
            # N'inclure que les compositions en statut VALIDATED ou PRODUCTION
            if composition.status in [CompositionStatus.VALIDATED, CompositionStatus.PRODUCTION]:
                try:
                    tool = self.composition_to_mcp_tool(composition)
                    tools.append(tool)
                except Exception as e:
                    logger.error(f"Erreur lors de la conversion de {composition.id} en outil MCP: {e}")
        
        return tools 