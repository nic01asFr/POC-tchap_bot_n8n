# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import asyncio
import json
from aiohttp import web
from matrix_bot.config import logger
from config import env_config
import aiohttp

class WebhookServer:
    def __init__(self, matrix_client):
        self.matrix_client = matrix_client
        self.app = web.Application()
        
        # Configurer les routes pour le webhook
        self.app.add_routes([
            # Route par défaut définie dans la config
            web.post(env_config.webhook_endpoint, self.handle_webhook),
            web.get(env_config.webhook_endpoint, self.handle_webhook),
            
            # Route spécifique pour matrix-webhook (pour la compatibilité avec n8n)
            web.post('/webhook-test/matrix_webhook', self.handle_webhook),
            web.get('/webhook-test/matrix_webhook', self.handle_webhook),
            
            # Route spécifique pour le catalogue des outils n8n
            web.get('/webhook/catalog/all', self.handle_catalog),
            
            # Route pour l'agent d'outil (tool_agent)
            web.post('/webhook/tool_agent', self.handle_tool_agent),
            web.get('/webhook/tool_agent', self.handle_tool_agent)
        ])
        
        self.runner = None
        self.site = None
    
    async def start(self):
        """Start the webhook server"""
        if not env_config.webhook_enabled:
            logger.info("Webhook server is disabled")
            return
        
        if not env_config.webhook_token:
            logger.warning("Webhook server is enabled but no token is configured. This is insecure!")
        
        try:
            # Journaliser les informations sur la configuration des webhooks
            
            # Configuration globale
            if env_config.global_webhook_url:
                logger.info(f"Global webhook URL configured: {env_config.global_webhook_url} (method: {env_config.global_webhook_method})")
                logger.info(f"Auto-forward all messages: {'Enabled' if env_config.global_webhook_auto_forward else 'Disabled'}")
            
            # Configuration par salon (sortants)
            if env_config.webhook_url:
                logger.info(f"Room-specific outgoing webhooks configured: {len(env_config.webhook_url)}")
                for room_id, url in env_config.webhook_url.items():
                    method = env_config.webhook_method.get(room_id, "GET")
                    logger.info(f"  - Room {room_id} -> {url} (method: {method})")
            
            # Webhooks entrants configurés
            if env_config.webhook_incoming_rooms:
                logger.info(f"Incoming webhooks configured: {len(env_config.webhook_incoming_rooms)}")
                for token, room_id in env_config.webhook_incoming_rooms.items():
                    logger.info(f"  - Token '{token}' -> Room {room_id}")
            
            # Démarrer le serveur
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, env_config.webhook_host, env_config.webhook_port)
            await self.site.start()
            logger.info(f"Webhook server started on http://{env_config.webhook_host}:{env_config.webhook_port}{env_config.webhook_endpoint}")
            logger.info(f"Additional webhook endpoint: http://{env_config.webhook_host}:{env_config.webhook_port}/webhook-test/matrix_webhook")
            logger.info(f"Catalog endpoint: http://{env_config.webhook_host}:{env_config.webhook_port}/webhook/catalog/all")
        except Exception as e:
            logger.error(f"Failed to start webhook server: {e}")
    
    async def stop(self):
        """Stop the webhook server"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Webhook server stopped")
    
    async def handle_webhook(self, request):
        """Handle incoming webhook requests (GET or POST)"""
        try:
            # Récupérer les données selon la méthode HTTP
            if request.method == "GET":
                data = dict(request.query)
            else:  # POST
                data = await request.json() if request.can_read_body else {}
            
            # Loguer l'événement pour le débogage
            logger.info(f"Webhook received: {request.method} {request.path} - {data}")
            
            # Valider le token si configuré
            token = request.query.get('token') or data.get('token')
            if env_config.webhook_token and token != env_config.webhook_token:
                return web.Response(status=401, text="Invalid token")
            
            # Get room ID from token if specified
            room_id = env_config.webhook_incoming_rooms.get(token or '')
            
            # Otherwise use room_id from request
            if not room_id:
                room_id = data.get('room_id')
                
            if not room_id:
                return web.Response(status=400, text="Room ID is required")
            
            # Get message content
            message = data.get('message')
            if not message:
                return web.Response(status=400, text="Message is required")
            
            # Ajouter le préfixe du bot si configuré
            if env_config.message_prefix:
                message = f"{env_config.message_prefix} {message}"
            
            # Format the message if needed
            formatted_message = message
            format_type = data.get('format', 'markdown').lower()
            
            # Utiliser Markdown par défaut
            if format_type == 'markdown':
                await self.matrix_client.send_markdown_message(room_id, formatted_message)
            else:
                await self.matrix_client.send_text_message(room_id, formatted_message)
            
            return web.Response(status=200, text=json.dumps({"status": "success", "message": "Message sent"}), 
                               content_type='application/json')
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return web.Response(status=500, text=json.dumps({"status": "error", "message": str(e)}),
                               content_type='application/json')
    
    async def handle_catalog(self, request):
        """Gère les requêtes pour le catalogue des outils"""
        try:
            # Vérifier l'authentification Bearer si n8n_auth_token est configuré
            auth_header = request.headers.get('Authorization', '')
            expected_token = f"Bearer {env_config.n8n_auth_token}"
            
            if env_config.n8n_auth_token and auth_header != expected_token:
                return web.Response(status=401, text="Unauthorized - Invalid token")
            
            # Valider que n8n est activé et configuré
            if not env_config.n8n_enabled or not env_config.n8n_base_url:
                return web.Response(status=503, text="N8n integration is not enabled or properly configured")
            
            # Rediriger la requête vers l'instance n8n configurée
            try:
                logger.info(f"Forwarding catalog request to n8n: {env_config.n8n_base_url}/webhook/catalog/all")
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{env_config.n8n_base_url}/webhook/catalog/all",
                        headers={'Authorization': expected_token}
                    ) as response:
                        # Récupérer la réponse du serveur n8n
                        response_data = await response.text()
                        status = response.status
                        
                        # Construire la réponse avec le même statut et contenu
                        return web.Response(
                            status=status,
                            text=response_data,
                            content_type=response.headers.get('Content-Type', 'application/json')
                        )
            except Exception as e:
                logger.error(f"Error forwarding to n8n: {str(e)}")
                return web.Response(
                    status=502,
                    text=json.dumps({"error": f"Error forwarding to n8n: {str(e)}"}),
                    content_type='application/json'
                )
        
        except Exception as e:
            logger.error(f"Error handling catalog request: {str(e)}")
            return web.Response(
                status=500,
                text=json.dumps({"error": str(e)}),
                content_type='application/json'
            )
    
    async def handle_tool_agent(self, request):
        """Gère les requêtes pour l'agent d'outil (!tools)"""
        try:
            # Récupérer les données selon la méthode HTTP
            if request.method == "GET":
                data = dict(request.query)
            else:  # POST
                data = await request.json() if request.can_read_body else {}
            
            # Vérifier si c'est une commande !tools
            chat_input = data.get('chatInput', '')
            if chat_input == "!tools":
                logger.info("Detected !tools command in tool_agent webhook, handling with catalog data")
                
                # Rediriger vers le catalogue
                try:
                    auth_header = {'Authorization': f"Bearer {env_config.n8n_auth_token}"} if env_config.n8n_auth_token else {}
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"{env_config.n8n_base_url}/webhook/catalog/all",
                            headers=auth_header
                        ) as response:
                            if response.status == 200:
                                catalog_data = await response.json()
                                
                                # Formatter la réponse comme le ferait n8n_command_handler.handle_tools_command
                                categories = {}
                                for tool in catalog_data.get("tools", []):
                                    category = tool.get("category", "general")
                                    if category not in categories:
                                        categories[category] = []
                                    categories[category].append(tool)
                                
                                if not categories:
                                    return web.Response(
                                        status=200,
                                        text=json.dumps({"output": "⚠️ Aucun outil n'est disponible pour le moment."}),
                                        content_type='application/json'
                                    )
                                
                                response_text = "📋 **Catégories d'outils disponibles:**\n\n"
                                for category in sorted(categories.keys()):
                                    cat_tools = categories.get(category, [])
                                    response_text += f"**{category.upper()}** ({len(cat_tools)} outils)\n"
                                    
                                response_text += "\nUtilisez `!tools <catégorie>` pour voir les outils d'une catégorie"
                                response_text += "\nUtilisez `!tools search <terme>` pour rechercher des outils"
                                
                                return web.Response(
                                    status=200,
                                    text=json.dumps({"output": response_text}),
                                    content_type='application/json'
                                )
                            else:
                                error_msg = f"Erreur lors de la récupération du catalogue: {response.status}"
                                logger.error(error_msg)
                                return web.Response(
                                    status=200,  # On renvoie 200 avec un message d'erreur pour ne pas bloquer l'UI
                                    text=json.dumps({"output": f"⚠️ {error_msg}"}),
                                    content_type='application/json'
                                )
                except Exception as e:
                    logger.error(f"Error processing catalog for tool_agent: {str(e)}")
                    return web.Response(
                        status=200,
                        text=json.dumps({"output": f"⚠️ Erreur lors de l'accès au catalogue d'outils: {str(e)}"}),
                        content_type='application/json'
                    )
            
            # Si ce n'est pas !tools, laisser le webhook gérer normalement
            # Vous pourriez ajouter d'autres cas comme !tools <category> ou !run <tool>
            
            # Par défaut, laissez passer au webhook configuré dans tool_agent
            return await self.handle_webhook(request)
            
        except Exception as e:
            logger.error(f"Error in tool_agent handler: {str(e)}")
            return web.Response(
                status=500,
                text=json.dumps({"error": str(e)}),
                content_type='application/json'
            )

# Register a room to receive webhook messages
async def register_webhook_room(matrix_client, room_id, token=None):
    """Register a room to receive webhook messages with a specific token"""
    if not token:
        # Generate a random token if none is provided
        import uuid
        token = str(uuid.uuid4())
    
    env_config.webhook_incoming_rooms[token] = room_id
    
    # Construct the webhook URL - utiliser le host Docker si configuré
    host = env_config.webhook_host
    if host == "0.0.0.0":
        # Si on est dans Docker, utiliser host.docker.internal ou le nom du service
        import socket
        try:
            # Essayer de résoudre host.docker.internal (fonctionne dans Docker Desktop)
            socket.gethostbyname("host.docker.internal")
            host = "host.docker.internal"
        except socket.gaierror:
            # Sinon, utiliser l'IP de la machine hôte
            host = "127.0.0.1"  # ou "albert-tchap" si c'est le nom du service Docker
    
    # Construire l'URL avec le chemin spécifique /webhook-test/matrix_webhook
    webhook_url = f"http://{host}:{env_config.webhook_port}/webhook-test/matrix_webhook?token={token}"
    
    return webhook_url 