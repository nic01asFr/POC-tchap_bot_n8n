"""
Commandes Model Context Protocol (MCP) pour Albert-Tchap.

Ce module ajoute les commandes MCP au bot Albert-Tchap pour interagir avec les outils disponibles
via le Model Context Protocol (MCP) en utilisant le service MCP Registry.
"""

import json
import logging
import re
import aiohttp
import os
from typing import Dict, List, Any, Optional

from matrix_bot.client import MatrixClient
from matrix_bot.config import logger
from matrix_bot.eventparser import EventParser, EventNotConcerned
from nio import RoomMessageText

from bot_msg import AlbertMsg
from config import COMMAND_PREFIX, Config, env_config
from commands import register_feature, command_registry, only_allowed_user, user_configs

# Flag pour utiliser l'API simplifée (uniquement les endpoints disponibles)
USE_SIMPLIFIED_MCP_API = True

class MCPConnector:
    """Connecteur MCP pour Albert Tchapbot."""
    
    def __init__(self, registry_url: str, auth_token: Optional[str] = None):
        """
        Initialise le connecteur MCP.
        
        Args:
            registry_url: URL du service de registre MCP
            auth_token: Token d'authentification (optionnel)
        """
        self.registry_url = registry_url
        self.headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        logger.info(f"Connecteur MCP initialisé avec URL: {registry_url}")
        
    async def get_tools(self, refresh: bool = False) -> List[Dict]:
        """
        Récupère tous les outils disponibles.
        
        Args:
            refresh: Forcer le rafraîchissement
            
        Returns:
            Liste de tous les outils disponibles
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.registry_url}/api/tools"
                if refresh and not USE_SIMPLIFIED_MCP_API:
                    url += "?refresh=true"
                
                logger.info(f"Récupération des outils MCP depuis {url}")
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        tools = await response.json()
                        logger.info(f"Outils MCP récupérés: {len(tools)}")
                        return tools
                    else:
                        logger.error(f"Erreur lors de la récupération des outils: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Exception lors de la récupération des outils MCP: {str(e)}")
            return []
                    
    async def search_tools(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Recherche des outils pertinents pour une requête.
        
        Args:
            query: Requête utilisateur
            limit: Nombre maximum d'outils à retourner
            
        Returns:
            Liste des outils les plus pertinents
        """
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"query": query, "limit": limit}
                
                logger.info(f"Recherche d'outils MCP avec la requête: {query}")
                
                # Utiliser l'endpoint de recherche correct
                if USE_SIMPLIFIED_MCP_API:
                    url = f"{self.registry_url}/api/search"
                else:
                    url = f"{self.registry_url}/search"
                
                async with session.post(
                    url, 
                    json=payload,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        tools = await response.json()
                        logger.info(f"Outils pertinents trouvés: {len(tools)}")
                        return tools
                    else:
                        logger.error(f"Erreur lors de la recherche d'outils: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Exception lors de la recherche d'outils MCP: {str(e)}")
            return []
                    
    async def get_servers(self) -> List[Dict]:
        """
        Récupère la liste des serveurs MCP disponibles.
        
        Returns:
            Liste des serveurs
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.registry_url}/api/servers"
                logger.info(f"Récupération des serveurs MCP depuis {url}")
                async with session.get(
                    url,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        servers = await response.json()
                        logger.info(f"Serveurs MCP récupérés: {len(servers)}")
                        return servers
                    else:
                        logger.error(f"Erreur lors de la récupération des serveurs: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Exception lors de la récupération des serveurs MCP: {str(e)}")
            return []
                    
    async def execute_tool(self, server_id: str, tool_id: str, 
                         parameters: Dict[str, Any]) -> Dict:
        """
        Exécute un outil via le registre MCP.
        
        Args:
            server_id: Identifiant du serveur MCP
            tool_id: Identifiant de l'outil
            parameters: Paramètres pour l'outil
            
        Returns:
            Résultat de l'exécution
        """
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "server_id": server_id,
                    "tool_id": tool_id,
                    "parameters": parameters
                }
                
                logger.info(f"Exécution de l'outil {server_id}/{tool_id} avec paramètres: {parameters}")
                url = f"{self.registry_url}/api/execute"
                async with session.post(
                    url,
                    json=payload,
                    headers=self.headers
                ) as response:
                    if response.status >= 200 and response.status < 300:
                        result = await response.json()
                        logger.info(f"Exécution réussie: {result}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Erreur lors de l'exécution de l'outil: {response.status} - {error_text}")
                        try:
                            return json.loads(error_text)
                        except:
                            return {"error": f"Erreur {response.status}", "message": error_text}
        except Exception as e:
            logger.error(f"Exception lors de l'exécution de l'outil MCP: {str(e)}")
            return {"error": str(e), "message": f"Erreur: {str(e)}"}

    async def get_status(self) -> Dict[str, Any]:
        """
        Vérifie le statut du service MCP.
        
        Returns:
            Informations sur le statut du service
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.registry_url}/api/status"
                logger.info(f"Vérification du statut MCP depuis {url}")
                async with session.get(
                    url,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        status = await response.json()
                        logger.info(f"Statut MCP récupéré: {status}")
                        return status
                    else:
                        logger.error(f"Erreur lors de la récupération du statut: {response.status}")
                        return {"status": "error", "error": f"Erreur {response.status}"}
        except Exception as e:
            logger.error(f"Exception lors de la récupération du statut MCP: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def analyze_message(self, message: str) -> Dict[str, Any]:
        """
        Analyse un message pour détecter les intentions.
        Note: Cette méthode n'utilise pas l'API simplifée - 
        si USE_SIMPLIFIED_MCP_API est True, on simule l'analyse.
        
        Args:
            message: Message à analyser
            
        Returns:
            Résultat de l'analyse
        """
        # Si nous utilisons l'API simplifiée, ne pas appeler les endpoints non disponibles
        if USE_SIMPLIFIED_MCP_API:
            # Analyse simplifiée - rechercher des mots clés sur Grist
            grist_keywords = ["grist", "document", "table", "enregistrement", "donnée", "liste"]
            
            # Vérifier si le message contient des mots clés Grist
            has_grist_intent = any(keyword in message.lower() for keyword in grist_keywords)
            
            if has_grist_intent:
                return {
                    "intent": "grist_query",
                    "confidence": 0.85,
                    "entities": {
                        "action": "list" if "liste" in message.lower() else "query"
                    }
                }
            else:
                return {
                    "intent": None,
                    "confidence": 0,
                    "entities": {}
                }
        
        # Version complète - utilise l'API d'analyse (non disponible dans notre implémentation simplifiée)
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"message": message}
                
                # D'abord essayer /api/analyze
                try:
                    async with session.post(
                        f"{self.registry_url}/api/analyze", 
                        json=payload,
                        headers=self.headers
                    ) as response:
                        if response.status == 200:
                            return await response.json()
                except Exception:
                    pass
                
                # Puis essayer /intent/analyze
                try:
                    async with session.post(
                        f"{self.registry_url}/intent/analyze", 
                        json=payload,
                        headers=self.headers
                    ) as response:
                        if response.status == 200:
                            return await response.json()
                except Exception:
                    pass
                    
                # Finalement essayer /api/intent
                try:
                    async with session.post(
                        f"{self.registry_url}/api/intent", 
                        json=payload,
                        headers=self.headers
                    ) as response:
                        if response.status == 200:
                            return await response.json()
                except Exception:
                    pass
                    
            # Aucun endpoint n'a fonctionné
            logger.error("Aucun endpoint d'analyse disponible")
            return {"intent": None, "confidence": 0, "entities": {}}
        except Exception as e:
            logger.error(f"Exception lors de l'analyse du message: {str(e)}")
            return {"intent": None, "confidence": 0, "entities": {}}

def get_mcp_connector(config: Config) -> Optional[MCPConnector]:
    """
    Obtient un connecteur MCP pour Albert.
    
    Args:
        config: Configuration d'Albert
        
    Returns:
        Connecteur MCP ou None si non configuré
    """
    # Priorité 1: Utiliser les variables d'environnement directes
    registry_url = os.environ.get("MCP_REGISTRY_URL")
    auth_token = os.environ.get("MCP_AUTH_TOKEN")
    
    # Priorité 2: Utiliser la configuration passée
    if not registry_url and hasattr(config, "mcp_registry_url"):
        registry_url = config.mcp_registry_url
        
    if not auth_token and hasattr(config, "mcp_auth_token"):
        auth_token = config.mcp_auth_token
    
    # Vérifier si les informations sont disponibles
    if not registry_url:
        logger.warning("URL du MCP Registry non configurée, les commandes MCP ne seront pas disponibles")
        return None
    
    logger.info(f"Initialisation du connecteur MCP avec {registry_url}")
    return MCPConnector(
        registry_url=registry_url,
        auth_token=auth_token
    )

def format_tools_output(tools: List[Dict]) -> str:
    """
    Formate la liste des outils pour l'affichage.
    
    Args:
        tools: Liste des outils
        
    Returns:
        Texte formaté pour l'affichage
    """
    if not tools:
        return "Aucun outil MCP disponible."
        
    output = "🛠️ **Outils MCP disponibles :**\n\n"
    
    # Regrouper les outils par serveur
    tools_by_server = {}
    for tool in tools:
        server_id = tool.get("server_id", "inconnu")
        if server_id not in tools_by_server:
            tools_by_server[server_id] = []
        tools_by_server[server_id].append(tool)
    
    # Afficher les outils regroupés par serveur
    for server_id, server_tools in tools_by_server.items():
        output += f"**Serveur: {server_id}**\n"
        
        for i, tool in enumerate(server_tools, 1):
            tool_id = tool.get("name", "inconnu")
            description = tool.get("description", "Pas de description disponible")
            
            output += f"{i}. **{tool_id}** - {description}\n"
            
            # Afficher les paramètres s'ils sont disponibles
            parameters = tool.get("parameters", {})
            if isinstance(parameters, dict) and "properties" in parameters:
                properties = parameters["properties"]
                required = parameters.get("required", [])
                
                if properties:
                    output += "   Paramètres:\n"
                    for param_name, param_info in properties.items():
                        param_desc = param_info.get("description", "")
                        param_type = param_info.get("type", "")
                        req_mark = "*" if param_name in required else ""
                        
                        output += f"   - {param_name}{req_mark}: {param_desc} ({param_type})\n"
        
        output += "\n"
    
    output += "\nUtilisez `!mcp-run <serveur> <outil> <paramètres>` pour exécuter un outil."
    return output

def format_servers_output(servers: List[Dict]) -> str:
    """
    Formate la liste des serveurs pour l'affichage.
    
    Args:
        servers: Liste des serveurs
        
    Returns:
        Texte formaté pour l'affichage
    """
    if not servers:
        return "Aucun serveur MCP disponible."
        
    output = "📡 **Serveurs MCP disponibles:**\n\n"
    
    for i, server in enumerate(servers, 1):
        output += f"{i}. **{server.get('name', server.get('id', 'inconnu'))}** ({server.get('id', 'inconnu')})\n"
        if server.get("description"):
            output += f"   {server['description']}\n"
        output += f"   URL: {server.get('url', 'Non spécifiée')}\n"
        output += f"   Outils: {server.get('tools_count', 0)}\n\n"
        
    output += "Pour voir les outils d'un serveur spécifique: `!mcp-tools <server_id>`"
    
    return output

# Fonctions pour les commandes MCP

async def get_mcp_tool_info(ep: EventParser, matrix_client: MatrixClient) -> None:
    """
    Récupère et affiche les informations sur les outils MCP disponibles.
    
    Args:
        ep: Parser d'événements
        matrix_client: Client Matrix
    """
    # Obtenir le connecteur MCP
    connector = get_mcp_connector(env_config)
    if not connector:
        await matrix_client.send_markdown_message(
            ep.room.room_id,
            "❌ La connexion au MCP Registry n'est pas configurée. Contactez l'administrateur."
        )
        return
    
    try:
        # Vérifier l'état du service MCP
        status = await connector.get_status()
        if status.get("status") != "ok":
            await matrix_client.send_markdown_message(
                ep.room.room_id,
                f"⚠️ Le service MCP est actuellement indisponible: {status.get('error', 'Erreur inconnue')}"
            )
            return
        
        # Récupérer la liste des outils
        tools = await connector.get_tools(refresh=True)
        
        if not tools:
            await matrix_client.send_markdown_message(
                ep.room.room_id,
                "ℹ️ Aucun outil MCP n'est disponible actuellement."
            )
            return
        
        # Trier les outils par serveur
        tools_by_server = {}
        for tool in tools:
            server_id = tool.get("server_id", "unknown")
            if server_id not in tools_by_server:
                tools_by_server[server_id] = []
            tools_by_server[server_id].append(tool)
        
        # Construire le message de réponse
        message = f"## 🛠️ Outils MCP disponibles ({len(tools)} au total)\n\n"
        
        for server_id, server_tools in tools_by_server.items():
            message += f"### 🖥️ Serveur: {server_id}\n\n"
            
            for tool in server_tools:
                name = tool.get("name", "Sans nom")
                description = tool.get("description", "Pas de description")
                tool_id = tool.get("id", "unknown")
                
                message += f"- **{name}** (id: `{tool_id}`)\n"
                message += f"  {description}\n"
                
                # Ajouter les infos sur les paramètres si disponibles
                params = tool.get("parameters", {})
                
                if params and isinstance(params, dict) and "properties" in params:
                    properties = params.get("properties", {})
                    if properties:
                        message += "  *Paramètres:*\n"
                        
                        for param_name, param_info in properties.items():
                            param_desc = param_info.get("description", "")
                            param_type = param_info.get("type", "string")
                            required = param_name in params.get("required", [])
                            
                            message += f"  - `{param_name}` ({param_type}{', requis' if required else ''}): {param_desc}\n"
                
                message += "\n"
        
        # Envoyer le message
        await matrix_client.send_markdown_message(
            ep.room.room_id,
            message
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des outils MCP: {str(e)}")
        await matrix_client.send_markdown_message(
            ep.room.room_id,
            f"❌ Erreur lors de la récupération des outils MCP: {str(e)}"
        )

# Commandes MCP
@register_feature(
    name="tools",
    group="mcp",
    help="Liste tous les outils MCP disponibles",
    onEvent=RoomMessageText,
)
@only_allowed_user
async def mcp_tools_command(ep: EventParser, matrix_client: MatrixClient):
    """Commande pour lister tous les outils MCP disponibles."""
    if not ep.is_command(COMMAND_PREFIX, "tools"):
        raise EventNotConcerned
    
    await get_mcp_tool_info(ep, matrix_client)

@register_feature(
    name="mcp",
    group="mcp",
    help="Liste tous les outils MCP disponibles",
    onEvent=RoomMessageText,
)
@only_allowed_user
async def mcp_command(ep: EventParser, matrix_client: MatrixClient):
    """Commande pour lister tous les outils MCP disponibles (alias)."""
    if not ep.is_command(COMMAND_PREFIX, "mcp"):
        raise EventNotConcerned
    
    await get_mcp_tool_info(ep, matrix_client)

@register_feature(
    group="mcp",
    onEvent=RoomMessageText,
    command="mcp-tools",
    help="Affiche la liste des outils MCP disponibles",
)
@only_allowed_user
async def mcp_tools_command(ep: EventParser, matrix_client: MatrixClient):
    """Commande pour lister les outils MCP disponibles."""
    config = user_configs[ep.sender]
    
    # Vérifier que MCP Registry est configuré
    connector = get_mcp_connector(config)
    if not connector:
        message = "⚠️ Le service MCP Registry n'est pas configuré. Définissez mcp_registry_url dans la configuration."
        await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")
        return
    
    logger.info(f"Traitement de la commande !mcp-tools dans le salon {ep.room.room_id}")
    
    # Indiquer à l'utilisateur que nous traitons sa demande
    await matrix_client.room_typing(ep.room.room_id)
    
    # Extraire les arguments de la commande
    command = ep.get_command()
    args = " ".join(command[1:]) if len(command) > 1 else ""
    
    logger.info(f"Arguments de la commande !mcp-tools: '{args}'")
    
    # Message temporaire pour indiquer que la requête est en cours
    temp_message = "Récupération des outils MCP disponibles..."
    temp_event_id = await matrix_client.send_markdown_message(ep.room.room_id, temp_message, msgtype="m.notice")
    
    try:
        if args.startswith("search "):
            # Recherche sémantique
            query = args[7:].strip()
            logger.info(f"Recherche d'outils MCP avec le terme: '{query}'")
            tools = await connector.search_tools(query)
            
            if not tools:
                response = f"⚠️ Aucun outil MCP trouvé pour '{query}'"
            else:
                response = f"🔍 **Résultats pour '{query}':**\n\n"
                response += format_tools_output(tools)
        else:
            # Liste complète ou par serveur
            refresh = "refresh" in args.lower()
            
            if args and not refresh:
                # Liste des outils d'un serveur spécifique
                server_id = args.strip()
                tools = await connector.get_tools(refresh)
                tools = [t for t in tools if t.get("server_id") == server_id]
                
                if not tools:
                    response = f"⚠️ Aucun outil trouvé pour le serveur '{server_id}'"
                else:
                    response = f"🛠️ **Outils du serveur MCP {server_id}:**\n\n"
                    response += format_tools_output(tools)
            else:
                # Liste complète des outils
                tools = await connector.get_tools(refresh)
                response = format_tools_output(tools)
        
        # Supprimer le message temporaire si possible
        if temp_event_id:
            try:
                await matrix_client.redact_message(ep.room.room_id, temp_event_id, reason="Remplacé par la réponse complète")
                logger.info("Message temporaire supprimé")
            except Exception as e:
                logger.warning(f"Impossible de supprimer le message temporaire: {e}")
    
    except Exception as e:
        logger.exception(f"Erreur lors de la commande mcp-tools: {str(e)}")
        response = f"⚠️ Erreur lors de la récupération des outils MCP: {str(e)}"
    
    await matrix_client.send_markdown_message(ep.room.room_id, response, msgtype="m.notice")
    logger.info("Réponse mcp-tools envoyée à l'utilisateur")


@register_feature(
    group="mcp",
    onEvent=RoomMessageText,
    command="mcp-run",
    help="Exécute un outil MCP",
)
@only_allowed_user
async def mcp_run_command(ep: EventParser, matrix_client: MatrixClient):
    """Commande pour exécuter un outil MCP."""
    config = user_configs[ep.sender]
    
    # Vérifier que MCP Registry est configuré
    connector = get_mcp_connector(config)
    if not connector:
        message = "⚠️ Le service MCP Registry n'est pas configuré. Définissez mcp_registry_url dans la configuration."
        await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")
        return
    
    await matrix_client.room_typing(ep.room.room_id)
    
    # Extraire les arguments de la commande
    command = ep.get_command()
    args = " ".join(command[1:]) if len(command) > 1 else ""
    
    if not args:
        help_text = "⚠️ Usage: `!mcp-run <server_id> <nom_outil> [paramètres]`\n\n"
        help_text += "Utilisez `!mcp-tools` pour voir la liste des outils disponibles."
        await matrix_client.send_markdown_message(ep.room.room_id, help_text, msgtype="m.notice")
        return
    
    # Analyse des paramètres
    # Format: <server_id> <nom_outil> [paramètres]
    match = re.match(r'(\S+)\s+(\S+)\s*(.*)', args)
    if not match:
        help_text = "⚠️ Format incorrect. Usage: `!mcp-run <server_id> <nom_outil> [paramètres]`"
        await matrix_client.send_markdown_message(ep.room.room_id, help_text, msgtype="m.notice")
        return
    
    server_id, tool_id, params_str = match.groups()
    logger.info(f"Exécution de l'outil MCP: {server_id}:{tool_id}")
    
    # Message temporaire pour indiquer que la requête est en cours
    temp_message = f"Exécution de l'outil MCP '{tool_id}' sur le serveur '{server_id}'..."
    temp_event_id = await matrix_client.send_markdown_message(ep.room.room_id, temp_message, msgtype="m.notice")
    
    try:
        # Parsing des paramètres
        parameters = {}
        if params_str:
            # Format: param1=valeur1 param2="valeur avec espaces"
            param_matches = re.finditer(r'(\w+)=(?:"([^"]+)"|([^\s]+))', params_str)
            for param_match in param_matches:
                param_name = param_match.group(1)
                param_value = param_match.group(2) if param_match.group(2) else param_match.group(3)
                parameters[param_name] = param_value
        
        # Exécution de l'outil
        result = await connector.execute_tool(server_id, tool_id, parameters)
        
        if "error" in result:
            response = f"❌ Erreur lors de l'exécution de '{tool_id}':\n"
            response += f"{result.get('error')}\n"
            response += f"{result.get('message', '')}"
        else:
            response = f"✅ Résultat de l'exécution de '{tool_id}':\n\n"
            if isinstance(result, dict):
                response += f"```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
            else:
                response += str(result)
    
    except Exception as e:
        logger.exception(f"Erreur lors de l'exécution de l'outil MCP '{tool_id}'")
        response = f"⚠️ Une erreur s'est produite: {str(e)}"
    
    # Supprimer le message temporaire si possible
    if temp_event_id:
        try:
            await matrix_client.redact_message(ep.room.room_id, temp_event_id, reason="Remplacé par la réponse complète")
        except Exception as e:
            logger.warning(f"Impossible de supprimer le message temporaire: {e}")
    
    await matrix_client.send_markdown_message(ep.room.room_id, response, msgtype="m.notice")


@register_feature(
    group="mcp",
    onEvent=RoomMessageText,
    command="mcp-servers",
    help="Liste les serveurs MCP disponibles",
)
@only_allowed_user
async def mcp_servers_command(ep: EventParser, matrix_client: MatrixClient):
    """Commande pour lister les serveurs MCP disponibles."""
    config = user_configs[ep.sender]
    
    # Vérifier que MCP Registry est configuré
    connector = get_mcp_connector(config)
    if not connector:
        message = "⚠️ Le service MCP Registry n'est pas configuré. Définissez mcp_registry_url dans la configuration."
        await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")
        return
    
    logger.info(f"Traitement de la commande !mcp-servers dans le salon {ep.room.room_id}")
    
    await matrix_client.room_typing(ep.room.room_id)
    
    # Message temporaire pour indiquer que la requête est en cours
    temp_message = "Récupération des serveurs MCP disponibles..."
    temp_event_id = await matrix_client.send_markdown_message(ep.room.room_id, temp_message, msgtype="m.notice")
    
    try:
        servers = await connector.get_servers()
        response = format_servers_output(servers)
        
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération des serveurs MCP: {str(e)}")
        response = f"⚠️ Erreur lors de la récupération des serveurs MCP: {str(e)}"
    
    # Supprimer le message temporaire si possible
    if temp_event_id:
        try:
            await matrix_client.redact_message(ep.room.room_id, temp_event_id, reason="Remplacé par la réponse complète")
        except Exception as e:
            logger.warning(f"Impossible de supprimer le message temporaire: {e}")
            
    await matrix_client.send_markdown_message(ep.room.room_id, response, msgtype="m.notice")


@register_feature(
    group="mcp",
    onEvent=RoomMessageText,
    help="Suggère des outils MCP pertinents pour une requête",
)
@only_allowed_user
async def mcp_suggest_command(ep: EventParser, matrix_client: MatrixClient):
    """Suggère des outils MCP pertinents pour une requête de l'utilisateur."""
    config = user_configs[ep.sender]
    
    # Ne traiter que les messages directs
    ep.only_on_direct_message()
    
    # Ignorer les commandes explicites
    if ep.is_command(COMMAND_PREFIX):
        raise EventNotConcerned
    
    # Vérifier que MCP Registry est configuré
    connector = get_mcp_connector(config)
    if not connector:
        # Ne rien faire si MCP n'est pas configuré
        raise EventNotConcerned
    
    # Récupérer le message de l'utilisateur
    query = ep.event.body.strip()
    
    # Rechercher les outils pertinents
    tools = await connector.search_tools(query, limit=3)
    
    if not tools:
        # Aucun outil pertinent trouvé
        raise EventNotConcerned
    
    # Formater une suggestion d'outils
    response = "💡 **Outils MCP suggérés pour votre demande:**\n\n"
    
    for i, tool in enumerate(tools, 1):
        server_id = tool.get("server_id", "inconnu")
        tool_id = tool.get("name", "inconnu")
        description = tool.get("description", "Pas de description disponible")
        
        response += f"{i}. **{tool_id}** ({server_id}) - {description}\n"
        
        # Afficher les paramètres (version simplifiée)
        parameters = tool.get("parameters", {})
        if isinstance(parameters, dict) and "properties" in parameters:
            properties = parameters["properties"]
            required = parameters.get("required", [])
            
            if properties:
                param_list = []
                for param_name, param_info in properties.items():
                    req_mark = "*" if param_name in required else ""
                    param_list.append(f"{param_name}{req_mark}")
                    
                if param_list:
                    response += f"   Paramètres: {', '.join(param_list)}\n"
        
        response += f"   Pour exécuter: `!mcp-run {server_id} {tool_id} [paramètres]`\n\n"
    
    await matrix_client.send_markdown_message(ep.room.room_id, response, msgtype="m.notice")

# Activer les commandes MCP
mcp_features = command_registry.activate_and_retrieve_group("mcp")
logger.info(f"Commandes MCP activées: {len(mcp_features)} commandes")
for feature in mcp_features:
    if "commands" in feature and feature["commands"]:
        logger.info(f"  - {feature['commands'][0]}: {feature.get('help', 'Pas de description')}")
    else:
        logger.info(f"  - {feature.get('name', 'sans nom')}: {feature.get('help', 'Pas de description')}") 