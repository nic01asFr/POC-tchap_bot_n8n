# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import logging
import os
import sys
from bot import main
from config import use_systemd_config

# Importer les modules de commandes pour enregistrer les commandes
from . import tchap_commands  # Commandes pour Tchap
from . import n8n_commands    # Commandes pour n8n
from . import mcp_commands    # Commandes pour MCP

# Configurer le logging
logging.basicConfig(level=int(os.environ.get("LOG_LEVEL", "10")))
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Mode webhook-only est activé par défaut pour l'intégration n8n
    if os.environ.get("WEBHOOK_ENABLED", "").lower() == "true":
        from .webhook_optimized import start_webhook_server
        import asyncio
        
        # Initialiser le MCP au démarrage pour vérifier sa connectivité
        from .mcp_commands import get_mcp_connector
        from .config import Config
        
        # Vérifier la connectivité MCP
        async def check_mcp_connectivity():
            try:
                logger.info("Vérification de la connectivité MCP...")
                config = Config()
                connector = get_mcp_connector(config)
                
                if connector:
                    # Récupérer les serveurs disponibles
                    servers = await connector.get_servers()
                    logger.info(f"Connectivité MCP OK - {len(servers)} serveurs disponibles")
                    
                    # Récupérer les outils pour chaque serveur
                    for server in servers:
                        server_id = server.get("id")
                        tools = await connector.get_tools()
                        grist_tools = [t for t in tools if t.get("server_id") == server_id]
                        logger.info(f"Serveur MCP {server_id}: {len(grist_tools)} outils disponibles")
                else:
                    logger.warning("MCP non configuré - les commandes MCP ne seront pas disponibles")
            except Exception as e:
                logger.error(f"Erreur lors de la vérification MCP: {str(e)}")
        
        # Exécuter la vérification MCP
        loop = asyncio.get_event_loop()
        loop.run_until_complete(check_mcp_connectivity())
        
        # Démarrer le serveur webhook
        logger.info("Démarrage du serveur webhook...")
        asyncio.run(start_webhook_server())
    else:
        # Mode bot classique
        use_systemd_config()
        main()
