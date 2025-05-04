# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import time
import asyncio
import os
import logging
from typing import Union

from .matrix_bot.bot import MatrixBot
from .matrix_bot.config import logger
from .matrix_bot.auth import auth_matrix
from .matrix_bot.callbacks import Callbacks
from .matrix_bot.client import MatrixClient

from .webhook_commands import command_registry
from .config import env_config
from .webhook_server import WebhookServer
# Importer le module tchap_commands pour charger les commandes
from . import tchap_commands  
from . import n8n_commands  # Charger les commandes n8n
import mcp_commands

# TODO/IMPROVE:
# - if albert-bot is invited in a salon, make it answer only when if it is tagged.
# - !models: show available models.
# - show sources of a mesage for some given reactions of an answer.
# - !info: show the chat setting (model, with_history).


async def startup_tasks(bot):
    """Run startup tasks for the bot"""
    # Start webhook server if enabled
    if env_config.webhook_enabled:
        logger.info("Starting webhook server...")
        webhook_server = WebhookServer(bot.matrix_client)
        await webhook_server.start()
        # Store webhook server in bot instance for later reference
        bot.webhook_server = webhook_server
        logger.info("Webhook server started successfully")


async def main():
    # Récupérer l'authentification Matrix
    auth = auth_matrix(
        {
            "username": env_config.matrix_bot_username,
            "password": env_config.matrix_bot_password,
            "homeserver": env_config.matrix_home_server,
        }
    )
    
    # Créer le client Matrix et le bot
    matrix_client = MatrixClient(auth)
    callbacks = Callbacks(matrix_client)
    bot = MatrixBot(matrix_client, callbacks)
    
    # Ajouter les groupes de commandes
    used_groups = set(env_config.groups_used)
    features = []
    
    # Ajouter toujours les commandes de base
    if "basic" in used_groups:
        features.extend(command_registry.activate_and_retrieve_group("basic"))
    
    # Ajouter les commandes Tchap
    if "tchap" in used_groups:
        features.extend(command_registry.activate_and_retrieve_group("tchap"))
    
    # Ajouter les commandes webhook
    if "webhook" in used_groups:
        features.extend(command_registry.activate_and_retrieve_group("webhook"))
    
    # Ajouter les commandes MCP
    if "mcp" in used_groups:
        features.extend(command_registry.activate_and_retrieve_group("mcp"))

    # Ajouter les commandes n8n
    if "n8n" in used_groups:
        features.extend(command_registry.activate_and_retrieve_group("n8n"))
    
    bot.setup_features(features)
    
    # Démarrer le bot
    await bot.start(try_joining_invited_rooms=env_config.join_on_invite)


def main():
    logger.info(f"Starting Matrix Webhook Bot...")
    matrix_bot = MatrixBot(
        env_config.matrix_home_server,
        env_config.matrix_bot_username,
        env_config.matrix_bot_password,
    )

    # Charger les commandes webhook uniquement
    for feature in [
        feature
        for feature_group in env_config.groups_used
        for feature in command_registry.activate_and_retrieve_group(feature_group)
    ]:
        callback = feature["func"]
        onEvent = feature["onEvent"]
        matrix_bot.callbacks.register_on_custom_event(callback, onEvent, feature)
        logger.info(f"Loaded feature: {feature['name']}")

    # Register startup tasks
    async def startup_action(room_id):
        await startup_tasks(matrix_bot)
        # Envoyer un message dans chaque salon lorsque le bot est connecté
        await matrix_bot.matrix_client.send_text_message(
            room_id, 
            "🤖 Je suis en ligne et prêt à vous aider !",
            msgtype="m.notice"
        )
    matrix_bot.callbacks.register_on_startup(startup_action)

    n_tries = 4
    err = None
    for i in range(n_tries):
        try:
            logger.info("Starting Matrix bot...")
            matrix_bot.run()
        except Exception as e:
            err = e
            logger.error(f"Bot startup failed with error: {e}")
            time.sleep(3)

    if err:
        raise err


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
