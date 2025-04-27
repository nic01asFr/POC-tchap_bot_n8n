# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import time
import asyncio

from .matrix_bot.bot import MatrixBot
from .matrix_bot.config import logger

from .webhook_commands import command_registry
from .config import env_config
from .webhook_server import WebhookServer
# Importer le module tchap_commands pour charger les commandes
from . import tchap_commands  
from . import n8n_commands  # Charger les commandes n8n

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
