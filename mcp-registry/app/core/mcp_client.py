"""
MCP Client module for interacting with MCP servers.

This module provides functionality to discover, connect to, and interact with
Model Context Protocol (MCP) servers.
"""

import asyncio
import json
import logging
import os
import base64
from typing import Any, Dict, List, Optional, Union

import aiohttp
from pydantic import BaseModel, Field, ValidationError

from ..config.settings import ServerConfig

logger = logging.getLogger(__name__)


class ServerDiscoveryError(Exception):
    """Exception raised when server discovery fails."""
    pass


class ServerConnectionError(Exception):
    """Exception raised when connection to a server fails."""
    pass


class ToolExecutionError(Exception):
    """Exception raised when tool execution fails."""
    pass


class MCPServer(BaseModel):
    """MCP Server information model."""
    
    id: str
    name: str
    description: Optional[str] = None
    url: str
    version: Optional[str] = None
    status: str = "unknown"
    tools_count: int = 0
    
    class Config:
        arbitrary_types_allowed = True


class MCPTool(BaseModel):
    """MCP Tool information model."""
    
    id: str
    server_id: str
    name: str
    description: Optional[str] = None
    parameters: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True


class MCPClient:
    """
    Client for interacting with MCP servers.
    
    This class provides methods to discover and interact with MCP servers,
    retrieve available tools, and execute tools with parameters.
    """
    
    def __init__(self, config: ServerConfig):
        """
        Initialize the MCP client with the given configuration.
        
        Args:
            config: Server configuration for MCP
        """
        self.config = config
        self.servers: Dict[str, MCPServer] = {}
        self.tools: Dict[str, MCPTool] = {}
        self._session = None
        self._additional_server_urls = set()
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
        return self._session
        
    async def close(self) -> None:
        """Close any open connections."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            
    async def add_server_url(self, url: str) -> None:
        """
        Ajoute une URL de serveur à explorer lors de la prochaine découverte.
        
        Args:
            url: URL du serveur MCP
        """
        if url and url.strip():
            self._additional_server_urls.add(url.strip())
            logger.debug(f"URL de serveur ajoutée pour la découverte: {url}")
            
    async def discover_servers(self) -> List[MCPServer]:
        """
        Discover available MCP servers from the configured server list or discovery endpoints.
        
        Returns:
            List of discovered MCP servers
        
        Raises:
            ServerDiscoveryError: If server discovery fails
        """
        discovered_servers = []
        
        # Combiner les URLs configurées et les URLs additionnelles
        all_urls = set(self.config.server_urls or [])
        all_urls.update(self._additional_server_urls)
        
        # Use static server list if provided
        for url in all_urls:
            try:
                # Essayer en premier avec l'URL standard MCP /info
                info_url = f"{url.rstrip('/')}/info"
                logger.debug(f"Tentative de découverte via endpoint standard: {info_url}")
                
                session = await self._get_session()
                async with session.get(info_url) as response:
                    if response.status == 200:
                        server_info = await response.json()
                        
                        # Vérifier la présence des champs requis
                        if "id" in server_info:
                            server_id = server_info["id"]
                            server = MCPServer(
                                id=server_id,
                                name=server_info.get("name", server_id),
                                description=server_info.get("description", ""),
                                url=url,
                                version=server_info.get("version", "1.0.0"),
                                status="available",
                                tools_count=server_info.get("tools_count", 0)
                            )
                            
                            discovered_servers.append(server)
                            self.servers[server_id] = server
                            
                            # Récupérer les outils du serveur
                            await self._fetch_tools(server)
                            
                            logger.info(f"Serveur MCP standard découvert: {server.name} ({server.url})")
                            continue
                
                # Si ça échoue, essayer avec l'ancienne méthode
                server = await self._fetch_server_info(url.strip())
                if server:
                    discovered_servers.append(server)
                    continue
                    
                # Si tout échoue, essayer le mode de compatibilité Claude pour MCP
                server = await self._try_claude_mcp_discovery(url.strip())
                if server:
                    discovered_servers.append(server)
                    continue
                    
            except Exception as e:
                logger.warning(f"Connection error for server {url}: {str(e)}")
                    
        # Use discovery endpoints if provided
        if self.config.discovery_urls:
            for discovery_url in self.config.discovery_urls:
                try:
                    servers = await self._discover_from_endpoint(discovery_url.strip())
                    discovered_servers.extend(servers)
                except Exception as e:
                    logger.warning(f"Failed to discover MCP servers from {discovery_url}: {str(e)}")
        
        # Update internal server registry
        for server in discovered_servers:
            self.servers[server.id] = server
            
        if not discovered_servers and (self.config.server_urls or self.config.discovery_urls or self._additional_server_urls):
            logger.warning("No MCP servers discovered")
            
        return discovered_servers
        
    async def _try_claude_mcp_discovery(self, url: str) -> Optional[MCPServer]:
        """
        Essaie de découvrir un serveur MCP compatible avec le format Claude.
        
        Args:
            url: URL du serveur MCP
            
        Returns:
            Server information or None if unavailable
        """
        try:
            # Configuration minimale pour Claude MCP
            config = {
                "client_id": "mcp-registry-client",
                "client_version": "1.0.0"
            }
            
            # Encoder la configuration en base64
            config_base64 = base64.b64encode(json.dumps(config).encode()).decode()
            
            # Construire l'URL complète
            full_url = f"{url.rstrip('/')}?config={config_base64}"
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            session = await self._get_session()
            
            # Tenter une connexion avec le format Claude MCP
            async with session.post(full_url, json={"type": "init", "body": {}}, headers=headers) as response:
                if response.status == 200:
                    # Lire la première ligne pour extraire les outils
                    async for line in response.content:
                        try:
                            data = json.loads(line.decode())
                            if data.get("type") == "tools" and "body" in data:
                                tools = data.get("body", [])
                                
                                # Créer un serveur factice avec les outils découverts
                                server_id = f"claude-mcp-{url.replace('://', '-').replace('/', '-').replace(':', '-')}"
                                
                                server = MCPServer(
                                    id=server_id,
                                    name=f"Claude MCP ({url})",
                                    description="Serveur MCP compatible Claude",
                                    url=url,
                                    version="1.0.0",
                                    status="available",
                                    tools_count=len(tools)
                                )
                                
                                # Enregistrer le serveur
                                self.servers[server_id] = server
                                
                                # Ajouter les outils
                                for tool in tools:
                                    if "name" in tool:
                                        tool_id = f"{server_id}:{tool['name']}"
                                        tool_obj = MCPTool(
                                            id=tool_id,
                                            server_id=server_id,
                                            name=tool["name"],
                                            description=tool.get("description", ""),
                                            parameters=tool.get("parameters", [])
                                        )
                                        self.tools[tool_id] = tool_obj
                                
                                logger.info(f"Serveur Claude MCP découvert: {server.name} ({url}) avec {len(tools)} outils")
                                return server
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.debug(f"Erreur lors du parsing de la ligne: {str(e)}")
                        
                        # Ne lire que la première ligne
                        break
                        
        except Exception as e:
            logger.debug(f"Échec de la découverte au format Claude MCP pour {url}: {str(e)}")
            
        return None
        
    async def _discover_from_endpoint(self, discovery_url: str) -> List[MCPServer]:
        """
        Discover MCP servers from a discovery endpoint.
        
        Args:
            discovery_url: URL of the discovery endpoint
            
        Returns:
            List of discovered servers
        """
        session = await self._get_session()
        
        try:
            async with session.get(discovery_url) as response:
                if response.status != 200:
                    logger.warning(f"Discovery endpoint {discovery_url} returned status {response.status}")
                    return []
                    
                data = await response.json()
                
                if not isinstance(data, list):
                    logger.warning(f"Discovery endpoint {discovery_url} returned invalid data format")
                    return []
                    
                servers = []
                for server_data in data:
                    try:
                        url = server_data.get("url")
                        if url:
                            server = await self._fetch_server_info(url)
                            if server:
                                servers.append(server)
                    except Exception as e:
                        logger.warning(f"Failed to process server from discovery: {str(e)}")
                        
                return servers
                
        except Exception as e:
            logger.error(f"Error connecting to discovery endpoint {discovery_url}: {str(e)}")
            return []
            
    async def _fetch_server_info(self, server_url: str) -> Optional[MCPServer]:
        """
        Fetch information about an MCP server.
        
        Args:
            server_url: URL of the MCP server
            
        Returns:
            Server information or None if unavailable
        """
        session = await self._get_session()
        
        # Normalize URL
        if not server_url.endswith("/"):
            server_url += "/"
            
        try:
            headers = {}
            if self.config.auth_token:
                headers["Authorization"] = f"Bearer {self.config.auth_token}"
                
            # Essayer d'utiliser directement l'URL fournie
            async with session.get(server_url, headers=headers) as response:
                if response.status != 200:
                    logger.warning(f"Server {server_url} returned status {response.status}")
                    return None
                    
                data = await response.json()
                
                # Basic validation
                if not isinstance(data, dict):
                    logger.warning(f"Server {server_url} returned invalid data format")
                    return None
                
                # Extraire l'ID et le nom du serveur, avec des valeurs par défaut
                server_id = data.get("id", os.path.basename(server_url.rstrip("/")))
                server_name = data.get("name", f"MCP Server {server_id}")
                
                # Create server object
                server = MCPServer(
                    id=server_id,
                    name=server_name,
                    description=data.get("description", "Serveur MCP"),
                    url=server_url,
                    version=data.get("version", "1.0.0"),
                    status="available"
                )
                
                # Try to get tools count
                try:
                    tools = await self._fetch_tools(server)
                    server.tools_count = len(tools)
                except Exception as e:
                    logger.warning(f"Could not fetch tools from {server_url}: {str(e)}")
                    
                return server
                
        except aiohttp.ClientError as e:
            logger.warning(f"Connection error for server {server_url}: {str(e)}")
            return None
        except Exception as e:
            logger.warning(f"Error processing server {server_url}: {str(e)}")
            return None
            
    async def get_tools(self, server_id: Optional[str] = None, 
                        refresh: bool = False) -> List[MCPTool]:
        """
        Get available tools from MCP servers.
        
        Args:
            server_id: Optional server ID to filter tools by server
            refresh: Whether to refresh the tools cache
            
        Returns:
            List of available tools
        """
        if refresh or not self.tools:
            await self.refresh_tools()
            
        if server_id:
            return [tool for tool in self.tools.values() if tool.server_id == server_id]
        else:
            return list(self.tools.values())
            
    async def refresh_tools(self) -> None:
        """
        Refresh the tools cache by fetching tools from all known servers.
        """
        # Discover servers if none are known
        if not self.servers:
            await self.discover_servers()
            
        all_tools = {}
        
        # Fetch tools from each server
        for server in self.servers.values():
            try:
                tools = await self._fetch_tools(server)
                for tool in tools:
                    all_tools[tool.id] = tool
            except Exception as e:
                logger.warning(f"Failed to fetch tools from server {server.id}: {str(e)}")
                
        self.tools = all_tools
        
    async def _fetch_tools(self, server: MCPServer) -> List[MCPTool]:
        """
        Fetch available tools from an MCP server.
        
        Args:
            server: The server to fetch tools from
            
        Returns:
            List of available tools
        """
        session = await self._get_session()
        
        # Format standard MCP pour l'URL des outils
        tools_url = f"{server.url.rstrip('/')}/tools"
        
        try:
            headers = {}
            if self.config.auth_token:
                headers["Authorization"] = f"Bearer {self.config.auth_token}"
                
            # Premier essai: endpoint standard /tools
            async with session.get(tools_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Traitement selon le format de la réponse
                    tools_list = []
                    
                    # Format 1: Liste d'outils directe
                    if isinstance(data, list):
                        tools_list = data
                    # Format 2: {"tools": [...]}
                    elif isinstance(data, dict) and "tools" in data:
                        tools_list = data["tools"]
                    # Format 3: Response wrapper
                    elif isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                        tools_list = data["data"]
                    else:
                        logger.warning(f"Format de données inconnu reçu de {server.url}")
                        tools_list = []
                    
                    # Création des objets MCPTool
                    tools = []
                    for tool_data in tools_list:
                        try:
                            if "name" not in tool_data:
                                logger.warning(f"Outil sans nom reçu de {server.url}")
                                continue
                                
                            tool_id = f"{server.id}:{tool_data['name']}"
                            
                            # Standardisation des paramètres
                            parameters = tool_data.get("parameters", [])
                            
                            # Format standard: {"parameters": {"properties": {...}, "required": [...]}}
                            if isinstance(parameters, dict):
                                # Ne rien faire, déjà au bon format
                                pass
                            # Format liste: [{"name": "x", "type": "string", ...}, ...]
                            elif isinstance(parameters, list):
                                # Conversion au format standard JSONSchema
                                properties = {}
                                required = []
                                
                                for param in parameters:
                                    if "name" in param:
                                        param_name = param["name"]
                                        properties[param_name] = {
                                            "type": param.get("type", "string"),
                                            "description": param.get("description", "")
                                        }
                                        
                                        if param.get("required", False):
                                            required.append(param_name)
                                
                                parameters = {
                                    "properties": properties,
                                    "required": required
                                }
                            
                            # Création de l'outil avec les paramètres standardisés
                            tool = MCPTool(
                                id=tool_id,
                                server_id=server.id,
                                name=tool_data["name"],
                                description=tool_data.get("description", ""),
                                parameters=parameters
                            )
                            tools.append(tool)
                            
                            # Enregistrer l'outil dans le cache
                            self.tools[tool_id] = tool
                            
                        except Exception as e:
                            logger.warning(f"Erreur lors du traitement d'un outil de {server.id}: {str(e)}")
                    
                    logger.info(f"Récupéré {len(tools)} outils depuis {server.url}")
                    return tools
                    
            # Deuxième essai: /schema endpoint (Claude Desktop, VSCode, etc.)
            schema_url = f"{server.url.rstrip('/')}/schema"
            async with session.get(schema_url, headers=headers) as response:
                if response.status == 200:
                    schema = await response.json()
                    
                    # Extraction des outils du schéma
                    tools_list = []
                    if "tools" in schema:
                        tools_list = schema["tools"]
                    elif "functions" in schema:
                        # Format utilisé par OpenAI et certains clients
                        tools_list = schema["functions"]
                    
                    # Création des objets MCPTool
                    tools = []
                    for tool_data in tools_list:
                        try:
                            if "name" not in tool_data:
                                continue
                                
                            tool_id = f"{server.id}:{tool_data['name']}"
                            
                            # Extraction des paramètres du schéma
                            parameters = {}
                            if "parameters" in tool_data:
                                parameters = tool_data["parameters"]
                            
                            tool = MCPTool(
                                id=tool_id,
                                server_id=server.id,
                                name=tool_data["name"],
                                description=tool_data.get("description", ""),
                                parameters=parameters
                            )
                            tools.append(tool)
                            
                            # Enregistrer l'outil dans le cache
                            self.tools[tool_id] = tool
                            
                        except Exception as e:
                            logger.warning(f"Erreur lors du traitement d'un outil de {server.id}: {str(e)}")
                    
                    logger.info(f"Récupéré {len(tools)} outils depuis le schéma de {server.url}")
                    return tools
                    
            logger.warning(f"Aucun outil trouvé pour le serveur {server.id}")
            return []
                
        except aiohttp.ClientError as e:
            logger.error(f"Erreur de connexion lors de la récupération des outils de {server.url}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des outils de {server.url}: {str(e)}")
            return []
            
    async def execute_tool(self, server_id: str, tool_name: str, 
                          parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool on an MCP server with the given parameters.
        
        Args:
            server_id: ID of the server to execute the tool on
            tool_name: Name of the tool to execute
            parameters: Parameters to pass to the tool
            
        Returns:
            Tool execution result
        
        Raises:
            ServerConnectionError: If the server connection fails
            ToolExecutionError: If tool execution fails
        """
        # Get server information
        server = self.servers.get(server_id)
        if not server:
            try:
                await self.discover_servers()
                server = self.servers.get(server_id)
            except Exception as e:
                raise ServerConnectionError(f"Failed to discover server {server_id}: {str(e)}")
                
        if not server:
            raise ServerConnectionError(f"Unknown server ID: {server_id}")
            
        session = await self._get_session()
        
        # Normaliser l'URL du serveur
        server_url = server.url.rstrip("/")
        
        # Essayer plusieurs formats d'endpoint d'exécution
        endpoints_to_try = [
            # Format standard MCP
            {
                "url": f"{server_url}/execute",
                "payload": {
                    "name": tool_name,
                    "parameters": parameters
                }
            },
            # Format alternatif Claude Desktop
            {
                "url": f"{server_url}/tools/{tool_name}/execute",
                "payload": parameters
            },
            # Format alternatif VSCode
            {
                "url": f"{server_url}/run",
                "payload": {
                    "name": tool_name,
                    "parameters": parameters
                }
            },
            # Format OpenAI
            {
                "url": f"{server_url}/v1/functions/{tool_name}",
                "payload": parameters
            }
        ]
        
        # En-têtes communs
        headers = {
            "Content-Type": "application/json"
        }
        
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
            
        # Essayer chaque endpoint jusqu'à ce qu'un fonctionne
        last_error = None
        for endpoint in endpoints_to_try:
            try:
                logger.debug(f"Tentative d'exécution de {tool_name} sur {endpoint['url']}")
                
                async with session.post(
                    endpoint["url"], 
                    headers=headers,
                    json=endpoint["payload"],
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    # Vérifier si la réponse est valide
                    if response.status >= 200 and response.status < 300:
                        try:
                            response_data = await response.json()
                            logger.info(f"Exécution réussie de {tool_name} sur {server_id}")
                            return response_data
                        except json.JSONDecodeError:
                            # Essayer de lire en texte si pas JSON
                            text = await response.text()
                            if text:
                                return {"result": text}
                    else:
                        error_text = await response.text()
                        last_error = f"Statut HTTP {response.status}: {error_text}"
                        logger.debug(f"Échec avec l'endpoint {endpoint['url']}: {last_error}")
                        
            except aiohttp.ClientError as e:
                last_error = f"Erreur de connexion: {str(e)}"
                logger.debug(f"Erreur de connexion avec {endpoint['url']}: {last_error}")
            except Exception as e:
                last_error = str(e)
                logger.debug(f"Exception avec {endpoint['url']}: {last_error}")
        
        # Si tous les endpoints ont échoué, lever une exception
        error_msg = f"Échec de l'exécution de l'outil {tool_name} sur {server_id}: {last_error}"
        logger.error(error_msg)
        raise ToolExecutionError(error_msg) 