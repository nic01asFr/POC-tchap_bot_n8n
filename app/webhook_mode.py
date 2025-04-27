# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import asyncio
import logging
import sys
import os
import json
from aiohttp import web

# Configuration du logging
logging.basicConfig(level=int(os.environ.get("LOG_LEVEL", "20")), 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("webhook-n8n")

# Configuration par défaut
DEFAULT_CONFIG = {
    "webhook_enabled": True,
    "webhook_host": "0.0.0.0",
    "webhook_port": 8080,
    "webhook_endpoint": "/webhook",
    "webhook_token": "votre_token_secret_n8n",
    "webhook_incoming_rooms": {}
}

# Charger la configuration depuis les variables d'environnement
def load_config():
    config = DEFAULT_CONFIG.copy()
    
    # Charger depuis les variables d'environnement
    if os.environ.get("WEBHOOK_ENABLED"):
        config["webhook_enabled"] = os.environ.get("WEBHOOK_ENABLED").lower() == "true"
    if os.environ.get("WEBHOOK_HOST"):
        config["webhook_host"] = os.environ.get("WEBHOOK_HOST")
    if os.environ.get("WEBHOOK_PORT"):
        config["webhook_port"] = int(os.environ.get("WEBHOOK_PORT"))
    if os.environ.get("WEBHOOK_ENDPOINT"):
        config["webhook_endpoint"] = os.environ.get("WEBHOOK_ENDPOINT")
    if os.environ.get("WEBHOOK_TOKEN"):
        config["webhook_token"] = os.environ.get("WEBHOOK_TOKEN")
    
    # Charger les webhooks entrants configurés
    if os.environ.get("WEBHOOK_INCOMING_ROOMS_CONFIG"):
        try:
            config["webhook_incoming_rooms"] = json.loads(os.environ.get("WEBHOOK_INCOMING_ROOMS_CONFIG"))
        except json.JSONDecodeError:
            logger.warning("Erreur de décodage JSON pour WEBHOOK_INCOMING_ROOMS_CONFIG")
    
    return config


class SimpleWebhookServer:
    """Serveur webhook simplifié qui ne dépend pas de matrix_bot"""
    
    def __init__(self, config):
        self.config = config
        self.app = None
        self.runner = None
        self.site = None
    
    async def start(self):
        """Démarrer le serveur webhook"""
        try:
            # Import aiohttp ici pour éviter les problèmes d'importation
            from aiohttp import web
            
            self.app = web.Application()
            
            # Configurer les routes
            self.app.add_routes([
                web.post(self.config["webhook_endpoint"], self.handle_webhook),
                web.get(self.config["webhook_endpoint"], self.handle_webhook),
                web.post('/webhook-test/matrix_webhook', self.handle_webhook),
                web.get('/webhook-test/matrix_webhook', self.handle_webhook)
            ])
            
            # Démarrer le serveur
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, self.config["webhook_host"], self.config["webhook_port"])
            await self.site.start()
            
            logger.info(f"Webhook server started on http://{self.config['webhook_host']}:{self.config['webhook_port']}{self.config['webhook_endpoint']}")
            logger.info(f"Additional webhook endpoint: http://{self.config['webhook_host']}:{self.config['webhook_port']}/webhook-test/matrix_webhook")
            
            # Afficher les configurations de webhook
            if self.config["webhook_incoming_rooms"]:
                logger.info(f"Configured incoming webhooks: {len(self.config['webhook_incoming_rooms'])}")
                for token, room_id in self.config["webhook_incoming_rooms"].items():
                    logger.info(f"  - Token '{token}' -> Room {room_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start webhook server: {e}")
            return False
    
    async def stop(self):
        """Arrêter le serveur webhook"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Webhook server stopped")
    
    async def handle_webhook(self, request):
        """Gérer les requêtes webhook entrantes"""
        from aiohttp import web
        
        try:
            # Récupérer les données selon la méthode HTTP
            if request.method == "GET":
                data = dict(request.query)
            else:  # POST
                try:
                    data = await request.json() if request.can_read_body else {}
                except:
                    data = {}
            
            # Loguer l'événement pour le débogage
            logger.info(f"Webhook received: {request.method} {request.path} - {data}")
            
            # Valider le token si configuré
            token = request.query.get('token') or data.get('token')
            if self.config["webhook_token"] and token != self.config["webhook_token"]:
                logger.warning(f"Invalid token: {token}")
                return web.Response(status=401, text="Invalid token")
            
            # Get room ID from token if specified
            room_id = self.config["webhook_incoming_rooms"].get(token or '')
            
            # Otherwise use room_id from request
            if not room_id:
                room_id = data.get('room_id')
                
            if not room_id:
                logger.warning("Room ID is required")
                return web.Response(status=400, text="Room ID is required")
            
            # Get message content
            message = data.get('message')
            if not message:
                logger.warning("Message is required")
                return web.Response(status=400, text="Message is required")
            
            # En mode webhook seul, on affiche simplement le message au lieu de l'envoyer
            format_type = data.get('format', '').lower()
            if format_type == 'markdown':
                logger.info(f"[WEBHOOK] Message Markdown to room '{room_id}': {message}")
            else:
                logger.info(f"[WEBHOOK] Message to room '{room_id}': {message}")
            
            return web.Response(status=200, text=json.dumps({"status": "success", "message": "Message received"}), 
                               content_type='application/json')
                               
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return web.Response(status=500, text=json.dumps({"status": "error", "message": str(e)}),
                               content_type='application/json')


async def run_webhook_server():
    """Démarrer uniquement le serveur webhook"""
    # Charger la configuration
    config = load_config()
    
    logger.info("Starting in WEBHOOK ONLY mode...")
    
    if not config["webhook_enabled"]:
        logger.error("Webhook server is disabled in configuration. Enable it with WEBHOOK_ENABLED=True")
        return False
    
    try:
        # Démarrer le serveur webhook
        logger.info("Starting webhook server...")
        webhook_server = SimpleWebhookServer(config)
        success = await webhook_server.start()
        
        if not success:
            return False
        
        # Garder le serveur en cours d'exécution
        while True:
            await asyncio.sleep(3600)  # Attendre indéfiniment
            
    except KeyboardInterrupt:
        logger.info("Shutting down webhook server...")
        await webhook_server.stop() if 'webhook_server' in locals() else None
        
    except Exception as e:
        logger.error(f"Error in webhook server: {e}")
        return False
        
    return True


def main():
    """Point d'entrée principal"""
    logger.info("Starting in webhook-only mode...")
    
    try:
        # Exécuter le serveur webhook de manière asynchrone
        loop = asyncio.get_event_loop()
        success = loop.run_until_complete(run_webhook_server())
        
        if not success:
            logger.error("Failed to start webhook server")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 