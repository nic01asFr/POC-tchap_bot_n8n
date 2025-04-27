"""
Client pour interagir avec l'API n8n.

Ce module permet de découvrir et d'utiliser les capacités exposées par n8n.
"""

import json
import aiohttp
import logging
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin

from .models import N8nTool, N8nCategory, N8nExecutionResult, N8nToolParameter

logger = logging.getLogger(__name__)


class N8nClient:
    """Client pour interagir avec l'API n8n."""

    def __init__(self, base_url: str, auth_token: str):
        """
        Initialise le client n8n.
        
        Args:
            base_url: URL de base de l'instance n8n
            auth_token: Token Bearer pour l'authentification
        """
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {auth_token}"}
        self.tools_cache = None
        self.categories_cache = None
        
    async def fetch_capabilities(self) -> Dict:
        """Récupère toutes les capacités disponibles depuis n8n"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/webhook/catalog/all", 
                                       headers=self.headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.tools_cache = result
                        logger.info(f"Capacités récupérées: {len(result.get('tools', []))} outils")
                        
                        # Organiser par catégories
                        categories = {}
                        for tool in result.get("tools", []):
                            category = tool.get("category", "general")
                            if category not in categories:
                                categories[category] = []
                            categories[category].append(tool)
                        
                        self.categories_cache = categories
                        return result
                    else:
                        logger.error(f"Erreur lors de la récupération des capacités: {response.status}")
                        return {"error": f"Erreur {response.status}", "tools": []}
        except Exception as e:
            logger.exception("Exception lors de la récupération des capacités")
            return {"error": str(e), "tools": []}
    
    async def get_mcp_schema(self, mcp_url: str) -> Dict:
        """Récupère le schéma d'un serveur MCP"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{mcp_url}/schema", 
                                       headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"error": f"Erreur {response.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_tools_by_category(self) -> Dict[str, List[N8nTool]]:
        """Récupère les outils regroupés par catégorie"""
        if self.categories_cache is None:
            await self.fetch_capabilities()
            
        if not self.categories_cache:
            return {}
            
        return self.categories_cache
    
    async def get_tool_categories(self) -> List[str]:
        """Récupère la liste des catégories d'outils disponibles"""
        if self.categories_cache is None:
            await self.fetch_capabilities()
            
        if not self.categories_cache:
            return []
            
        return list(self.categories_cache.keys())
    
    async def get_tools_in_category(self, category: str) -> List[N8nTool]:
        """Récupère les outils d'une catégorie spécifique"""
        if self.categories_cache is None:
            await self.fetch_capabilities()
            
        if not self.categories_cache or category not in self.categories_cache:
            return []
            
        return self.categories_cache[category]
    
    async def search_tools(self, query: str) -> List[Dict]:
        """Recherche des outils par mot-clé"""
        if self.tools_cache is None:
            await self.fetch_capabilities()
            
        if not self.tools_cache or "tools" not in self.tools_cache:
            return []
            
        query = query.lower()
        return [tool for tool in self.tools_cache["tools"] 
                if query in tool.get("name", "").lower() or 
                   query in tool.get("description", "").lower()]
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> N8nExecutionResult:
        """
        Exécute un outil spécifique avec les paramètres fournis.
        
        Args:
            tool_name: Nom de l'outil à exécuter
            parameters: Paramètres à passer à l'outil
            
        Returns:
            Résultat de l'exécution
        """
        if self.tools_cache is None:
            await self.fetch_capabilities()
            
        if not self.tools_cache or "tools" not in self.tools_cache:
            return N8nExecutionResult(
                success=False,
                message="Aucun outil disponible",
                error="Configuration non initialisée"
            )
            
        # Trouver l'outil par son nom
        tool = next((t for t in self.tools_cache["tools"] 
                     if t.get("name") == tool_name), None)
                     
        if not tool:
            return N8nExecutionResult(
                success=False,
                message=f"Outil '{tool_name}' non trouvé",
                error="Outil non trouvé"
            )
            
        try:
            async with aiohttp.ClientSession() as session:
                if tool.get("type") == "mcp":
                    # Exécution via MCP
                    url = f"{tool.get('url')}/run/{tool_name}"
                else:
                    # Exécution via Webhook direct
                    url = tool.get("url")
                    
                logger.info(f"Exécution de {tool_name} sur {url} avec {parameters}")
                
                async with session.post(url, json=parameters, 
                                       headers=self.headers) as response:
                    response_text = await response.text()
                    try:
                        result = json.loads(response_text)
                    except json.JSONDecodeError:
                        result = {"message": response_text}
                    
                    logger.info(f"Résultat: {result}")
                    
                    if response.status >= 200 and response.status < 300:
                        return N8nExecutionResult(
                            success=True,
                            message=result.get("message", "Exécution réussie"),
                            data=result
                        )
                    else:
                        return N8nExecutionResult(
                            success=False,
                            message=f"Erreur: {response.status}",
                            error=result.get("error", response_text),
                            data=result
                        )
        except Exception as e:
            logger.exception(f"Exception lors de l'exécution de {tool_name}")
            return N8nExecutionResult(
                success=False,
                message=f"Erreur: {str(e)}",
                error=str(e)
            ) 