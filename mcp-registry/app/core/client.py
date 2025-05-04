"""
Client pour interagir avec les serveurs Model Context Protocol (MCP).
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Any, Optional

# Configuration du logging
logger = logging.getLogger("mcp_registry.client")

class MCPClient:
    """Client pour interagir avec un serveur Model Context Protocol."""

    def __init__(self, server_id: str, server_url: str, headers: Dict[str, str] = None):
        """
        Initialise le client MCP.
        
        Args:
            server_id: Identifiant du serveur
            server_url: URL du serveur MCP
            headers: En-têtes HTTP optionnels pour les requêtes
        """
        self.server_id = server_id
        self.server_url = server_url.rstrip('/')
        self.headers = headers or {}
        
    async def get_schema(self) -> Dict:
        """
        Récupère le schéma du serveur MCP.
        
        Returns:
            Schéma des outils disponibles
        """
        try:
            logger.info(f"Récupération du schéma MCP depuis {self.server_url}/schema")
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.server_url}/schema", 
                    headers=self.headers,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        schema = await response.json()
                        logger.info(f"Schéma récupéré avec succès pour {self.server_id}")
                        return schema
                    else:
                        error_text = await response.text()
                        logger.error(f"Erreur lors de la récupération du schéma: {response.status} - {error_text}")
                        return {"error": f"Erreur {response.status}", "message": error_text}
        except asyncio.TimeoutError:
            logger.error(f"Timeout lors de la récupération du schéma pour {self.server_id}")
            return {"error": "Timeout", "message": "La requête a expiré"}
        except Exception as e:
            logger.exception(f"Exception lors de la récupération du schéma pour {self.server_id}: {str(e)}")
            return {"error": str(e)}
            
    def extract_tools_from_schema(self, schema: Dict) -> List[Dict]:
        """
        Extrait et enrichit la liste des outils d'un schéma MCP.
        
        Args:
            schema: Schéma MCP complet
            
        Returns:
            Liste des outils disponibles enrichis
        """
        tools = []
        
        # Extraction standard des outils
        raw_tools = []
        if "tools" in schema:
            raw_tools = schema["tools"]
        elif "functions" in schema:
            raw_tools = schema["functions"]
            
        # Enrichir chaque outil avec l'ID du serveur et l'URL
        for tool in raw_tools:
            enriched_tool = dict(tool)
            enriched_tool["server_id"] = self.server_id
            enriched_tool["server_url"] = self.server_url
            tools.append(enriched_tool)
            
        return tools
        
    async def run_tool(self, tool_id: str, parameters: Dict[str, Any]) -> Dict:
        """
        Exécute un outil spécifique.
        
        Args:
            tool_id: Identifiant de l'outil à exécuter
            parameters: Paramètres à passer à l'outil
            
        Returns:
            Résultat de l'exécution
        """
        try:
            logger.info(f"Exécution de l'outil {tool_id} sur {self.server_id} avec paramètres: {parameters}")
            
            async with aiohttp.ClientSession() as session:
                # Format du payload selon le protocole MCP
                payload = {
                    "name": tool_id,
                    "parameters": parameters
                }
                
                async with session.post(
                    f"{self.server_url}/run",
                    headers=self.headers,
                    json=payload,
                    timeout=60  # Timeout plus long pour l'exécution
                ) as response:
                    if response.status >= 200 and response.status < 300:
                        result = await response.json()
                        logger.info(f"Outil {tool_id} exécuté avec succès sur {self.server_id}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Erreur lors de l'exécution de l'outil: {response.status} - {error_text}")
                        return {"error": f"Erreur {response.status}", "message": error_text}
        except asyncio.TimeoutError:
            logger.error(f"Timeout lors de l'exécution de l'outil {tool_id} sur {self.server_id}")
            return {"error": "Timeout", "message": "La requête a expiré"}
        except Exception as e:
            logger.exception(f"Exception lors de l'exécution de l'outil {tool_id} sur {self.server_id}: {str(e)}")
            return {"error": str(e)} 