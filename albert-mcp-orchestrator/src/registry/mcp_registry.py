"""
Module pour l'intégration avec le registre MCP.

Ce module fournit les fonctionnalités pour interagir avec le registre MCP,
y compris la découverte et l'exécution d'outils.
"""

import json
import aiohttp
import asyncio
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)

class MCPRegistry:
    """
    Gestionnaire de registre MCP.
    
    Cette classe gère l'interaction avec le registre MCP, y compris:
    - Découverte de serveurs MCP
    - Récupération des outils disponibles
    - Exécution d'outils
    """
    
    _instance = None
    _initialized = False
    
    def __init__(self):
        """Initialise une nouvelle instance du registre MCP."""
        if MCPRegistry._instance is not None:
            raise RuntimeError("MCPRegistry est un singleton, utilisez get_instance()")
            
        self._registry_url = settings.MCP_REGISTRY_URL
        self._api_key = settings.MCP_REGISTRY_API_KEY
        self._servers = {}
        self._tools = {}
        self._discovery_urls = []
        
        # Charger les URLs de découverte depuis la configuration
        if hasattr(settings, 'MCP_DISCOVERY_URLS'):
            self._discovery_urls = settings.MCP_DISCOVERY_URLS
    
    @classmethod
    def initialize(cls):
        """Initialise l'instance singleton du registre MCP."""
        if cls._instance is None:
            cls._instance = MCPRegistry()
            cls._initialized = True
            
        return cls._instance
    
    @classmethod
    def get_instance(cls):
        """Récupère l'instance singleton du registre MCP."""
        if cls._instance is None:
            logger.warning("MCPRegistry n'est pas initialisé. Appeler initialize() d'abord.")
            return None
            
        return cls._instance
    
    def get_servers(self) -> List[Dict[str, Any]]:
        """Récupère la liste des serveurs MCP enregistrés."""
        return list(self._servers.values())
    
    def get_server(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un serveur MCP par son ID."""
        return self._servers.get(server_id)
    
    def get_tools(self, server_id: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Récupère la liste des outils MCP disponibles.
        
        Args:
            server_id: Filtre par serveur MCP
            category: Filtre par catégorie d'outil
        """
        tools = list(self._tools.values())
        
        # Filtrer par serveur si spécifié
        if server_id:
            tools = [tool for tool in tools if tool.get("server_id") == server_id]
            
        # Filtrer par catégorie si spécifiée
        if category:
            tools = [tool for tool in tools if tool.get("category") == category]
            
        return tools
    
    def get_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un outil MCP par son ID."""
        return self._tools.get(tool_id)
    
    def get_tools_manifest(self) -> List[Dict[str, Any]]:
        """
        Génère un manifeste d'outils pour l'enregistrement avec Albert.
        
        Returns:
            Liste d'outils formatés pour Albert Tchapbot
        """
        manifest = []
        
        for tool_id, tool in self._tools.items():
            manifest_tool = {
                "id": tool_id,
                "name": tool.get("name", tool_id),
                "description": tool.get("description", ""),
                "category": tool.get("category", "Autre"),
                "parameters": tool.get("parameters", []),
                "server_id": tool.get("server_id", ""),
                "url": tool.get("url", ""),
            }
            
            manifest.append(manifest_tool)
            
        return manifest
    
    async def discover_servers(self) -> Dict[str, Any]:
        """
        Découvre les serveurs MCP disponibles à partir des URLs configurées.
        
        Returns:
            Dictionnaire avec le nombre de serveurs découverts et leur liste
        """
        discovered_servers = []
        
        for url in self._discovery_urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            server_data = await response.json()
                            
                            # Vérifier que le format est valide
                            if "id" in server_data and "url" in server_data:
                                server_id = server_data["id"]
                                self._servers[server_id] = server_data
                                
                                # Découvrir les outils du serveur
                                tools = await self._discover_tools(server_data)
                                
                                discovered_servers.append({
                                    "id": server_id,
                                    "url": server_data["url"],
                                    "tools_count": len(tools)
                                })
            except Exception as e:
                logger.error(f"Erreur lors de la découverte du serveur {url}: {str(e)}")
                
        return {
            "servers_discovered": len(discovered_servers),
            "servers": discovered_servers
        }
                
    async def _discover_tools(self, server: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Découvre les outils disponibles sur un serveur MCP.
        
        Args:
            server: Informations sur le serveur MCP
            
        Returns:
            Liste des outils découverts
        """
        discovered_tools = []
        server_id = server["id"]
        server_url = server["url"]
        
        try:
            # Construire l'URL pour récupérer les outils
            tools_url = f"{server_url}/tools"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(tools_url) as response:
                    if response.status == 200:
                        tools_data = await response.json()
                        
                        for tool in tools_data:
                            if "id" in tool:
                                tool_id = tool["id"]
                                
                                # Ajouter le serveur d'origine à l'outil
                                tool["server_id"] = server_id
                                
                                # Enregistrer l'outil
                                self._tools[tool_id] = tool
                                discovered_tools.append(tool)
        except Exception as e:
            logger.error(f"Erreur lors de la découverte des outils du serveur {server_id}: {str(e)}")
            
        return discovered_tools
    
    async def execute_tool(
        self, 
        server_id: str, 
        tool_id: str, 
        parameters: Dict[str, Any],
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Exécute un outil MCP sur un serveur spécifique.
        
        Args:
            server_id: ID du serveur MCP
            tool_id: ID de l'outil à exécuter
            parameters: Paramètres pour l'exécution
            timeout: Délai d'attente en secondes
            
        Returns:
            Résultat de l'exécution
        """
        server = self.get_server(server_id)
        if not server:
            raise ValueError(f"Serveur MCP '{server_id}' non trouvé")
            
        tool = self.get_tool(tool_id)
        if not tool:
            raise ValueError(f"Outil MCP '{tool_id}' non trouvé")
            
        server_url = server["url"]
        execution_url = f"{server_url}/tools/{tool_id}/execute"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    execution_url,
                    json=parameters,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result
                    else:
                        error_text = await response.text()
                        raise RuntimeError(f"Erreur lors de l'exécution de l'outil: {error_text}")
        except asyncio.TimeoutError:
            raise TimeoutError(f"Délai d'attente dépassé lors de l'exécution de l'outil '{tool_id}'")
        except Exception as e:
            raise RuntimeError(f"Erreur lors de l'exécution de l'outil '{tool_id}': {str(e)}")
            
    async def check_health(self) -> bool:
        """
        Vérifie l'état de santé du registre MCP.
        
        Returns:
            True si le registre est opérationnel, False sinon
        """
        try:
            # Pour l'instant, on considère que le registre est sain s'il a des serveurs
            return len(self._servers) > 0
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de l'état du registre MCP: {str(e)}")
            return False 