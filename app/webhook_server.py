# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import asyncio
import json
from aiohttp import web
from matrix_bot.config import logger
from config import env_config
import aiohttp
import hashlib

class WebhookServer:
    def __init__(self, matrix_client):
        self.matrix_client = matrix_client
        self.app = web.Application()
        
        # Stockage des identifiants de messages traités pour éviter les boucles
        self.processed_events = set()
        
        # Stockage des hashes de contenu des messages pour détecter les doublons
        self.processed_message_hashes = set()
        
        # Configurer les routes pour le webhook
        self.app.add_routes([
            # Route par défaut définie dans la config
            web.post(env_config.webhook_endpoint, self.handle_webhook),
            web.get(env_config.webhook_endpoint, self.handle_webhook),
            
            # Route spécifique pour matrix-webhook (pour la compatibilité avec Matrix/Tchap)
            web.post('/webhook-test/matrix_webhook', self.handle_webhook),
            web.get('/webhook-test/matrix_webhook', self.handle_webhook),
            
            # Suppression des routes spécifiques n8n
            # web.get('/webhook/catalog/all', self.handle_catalog),
            # web.post('/webhook/tool_agent', self.handle_tool_agent),
            # web.get('/webhook/tool_agent', self.handle_tool_agent)
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
            
            # Extraire les informations clés
            event_id = data.get("event_id", "")
            original_event_id = data.get("original_event_id", event_id)
            sender = data.get("sender", "")
            
            # Loguer l'événement pour le débogage
            logger.info(f"Webhook received: {request.method} {request.path} - event_id: {event_id}")
            
            # Vérifier si c'est un message du bot lui-même
            expected_bot_id = f"@{env_config.matrix_username}:{env_config.matrix_homeserver.split('//')[1]}"
            if sender == expected_bot_id:
                logger.info(f"Message envoyé par le bot lui-même ({sender}), ignoré pour éviter une boucle")
                return web.Response(
                    status=200,
                    text=json.dumps({"status": "ignored", "reason": "sender is bot"}),
                    content_type='application/json'
                )
            
            # Vérifier si le message a déjà été traité
            if event_id and (event_id in self.processed_events or original_event_id in self.processed_events):
                logger.info(f"Message déjà traité (event_id: {event_id}), ignoré")
                return web.Response(
                    status=200,
                    text=json.dumps({"status": "ignored", "reason": "already processed"}),
                    content_type='application/json'
                )
            
            # Ajouter aux événements traités
            if event_id:
                self.processed_events.add(event_id)
                if original_event_id and original_event_id != event_id:
                    self.processed_events.add(original_event_id)
                
                # Nettoyage périodique pour éviter fuite mémoire
                if len(self.processed_events) > 1000:
                    # Garder seulement les 500 plus récents
                    events_list = list(self.processed_events)
                    self.processed_events = set(events_list[-500:])
            
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
            
            # Récupérer les détails de reply/thread si présents
            reply_to = data.get('reply_to')
            
            # Utiliser Markdown par défaut
            sent_event_id = None
            if format_type == 'markdown':
                sent_event_id = await self.matrix_client.send_markdown_message(room_id, formatted_message, reply_to=reply_to)
            else:
                sent_event_id = await self.matrix_client.send_text_message(room_id, formatted_message, reply_to=reply_to)
            
            # Ajouter le nouveau message à la liste des traités
            if sent_event_id:
                self.processed_events.add(sent_event_id)
                logger.info(f"Message envoyé avec ID {sent_event_id}, ajouté aux messages traités")
            
            # Essayer d'envoyer au webhook global si configuré
            await self._forward_to_global_webhook(data)
            
            return web.Response(
                status=200, 
                text=json.dumps({
                    "status": "success", 
                    "message": "Message sent",
                    "event_id": sent_event_id
                }), 
                content_type='application/json'
            )
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return web.Response(status=500, text=json.dumps({"status": "error", "message": str(e)}),
                               content_type='application/json')
    
    async def _forward_to_global_webhook(self, data):
        """Transfère les données au webhook global si configuré"""
        if not env_config.global_webhook_url or not env_config.global_webhook_auto_forward:
            # Si le webhook global n'est pas configuré ou le transfert automatique est désactivé, ne rien faire
            return None
        
        try:
            method = env_config.global_webhook_method
            response = await send_to_webhook(env_config.global_webhook_url, data, method=method)
            logger.info(f"Message transféré au webhook global: {env_config.global_webhook_url}")
            return response
        except Exception as e:
            logger.warning(f"Échec d'envoi au webhook global: {str(e)}")
            return None
    
    # Suppression des méthodes spécifiques n8n
    # async def handle_catalog(self, request):
    # async def handle_tool_agent(self, request):

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