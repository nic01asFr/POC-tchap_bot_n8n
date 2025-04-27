# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import logging
import time
import json
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from _version import __version__

COMMAND_PREFIX = "!"

APP_VERSION = __version__


class BaseConfig(BaseSettings):
    # allows us to clean up the imports into multiple parts
    # https://stackoverflow.com/questions/77328900/nested-settings-with-pydantic-settings
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env", extra="ignore"
    )  # allows nested configs


class Config(BaseConfig):
    # General
    systemd_logging: bool = Field(
        True, description="Enable / disable logging with systemd.journal.JournalHandler"
    )
    matrix_home_server: str = Field("", description="Tchap home server URL")
    matrix_bot_username: str = Field("", description="Username of our matrix bot")
    matrix_bot_password: str = Field("", description="Password of our matrix bot")
    errors_room_id: str | None = Field(None, description="Room ID to send errors to")
    user_allowed_domains: list[str] = Field(
        ["*"],
        description="List of allowed Tchap users email domains allowed to use Matrix Webhook Bot",
    )
    groups_used: list[str] = Field(["basic", "webhook", "tchap"], description="List of commands groups to use")
    last_activity: int = Field(int(time.time()), description="Last activity timestamp")
    bot_name: str = Field("Matrix Webhook Bot", description="Name of the bot")

    # Webhook configuration
    webhook_enabled: bool = Field(True, description="Enable webhook server")
    webhook_host: str = Field("0.0.0.0", description="Webhook server host")
    webhook_port: int = Field(8080, description="Webhook server port")
    webhook_endpoint: str = Field("/webhook", description="Webhook server endpoint")
    webhook_token: str = Field("", description="Webhook security token")
    webhook_url: dict = Field({}, description="Webhook URLs for each room")
    webhook_method: dict = Field({}, description="Webhook methods (GET/POST) for each room")
    webhook_incoming_rooms: dict = Field({}, description="Room IDs for incoming webhook messages by token")
    message_prefix: str = Field("", description="Prefix for messages sent by the bot")
    
    # Configuration globale des webhooks
    global_webhook_url: str = Field("", description="URL globale du webhook pour tous les salons")
    global_webhook_method: str = Field("GET", description="Méthode HTTP pour le webhook global (GET ou POST)")
    global_webhook_auto_forward: bool = Field(True, description="Transférer automatiquement tous les messages vers le webhook global")
    webhook_incoming_rooms_config: str = Field("{}", description="Configuration des salons pour le webhook entrant en JSON")
    webhook_room_config: str = Field("{}", description="Configuration des webhooks spécifiques par salon en JSON")

    # Activer la configuration d'utilisateurs autorisés pour le bot
    is_user_authorized: bool = Field(True, description="Enable user authorization")
    
    # Attributs d'Albert (pour compatibilité)
    albert_api_url: str = Field("", description="URL de l'API Albert")
    albert_api_token: str = Field("", description="Token de l'API Albert")
    albert_model: str = Field("n8n", description="Modèle Albert")
    albert_mode: str = Field("webhook", description="Mode Albert")
    albert_with_history: bool = Field(False, description="Utiliser l'historique")
    albert_history_lookup: int = Field(0, description="Nombre de messages d'historique")
    albert_max_rewind: int = Field(10, description="Nombre maximum de messages d'historique")
    albert_collections_by_id: dict = Field({}, description="Collections RAG par ID")
    albert_all_public_command: str = Field("all", description="Commande pour utiliser toutes les collections")
    albert_my_private_collection_name: str = Field("My private collection", description="Nom de la collection privée")
    albert_model_embedding: str = Field("", description="Modèle d'embedding")
    is_conversation_obsolete: bool = Field(False, description="Conversation obsolète")

    def update_last_activity(self) -> None:
        self.last_activity = int(time.time())
    
    def init_webhook_config(self):
        """Initialiser la configuration des webhooks à partir des variables d'environnement"""
        # Charger la configuration des webhooks entrants
        try:
            self.webhook_incoming_rooms = json.loads(self.webhook_incoming_rooms_config)
        except json.JSONDecodeError:
            self.webhook_incoming_rooms = {}
        
        # Charger la configuration des webhooks par salon
        try:
            room_config = json.loads(self.webhook_room_config)
            for room_id, config in room_config.items():
                self.webhook_url[room_id] = config.get("url", "")
                self.webhook_method[room_id] = config.get("method", "GET")
        except json.JSONDecodeError:
            pass  # Garder les dictionnaires vides par défaut


# Default config
env_config = Config()
# Initialiser la configuration des webhooks
env_config.init_webhook_config()


def use_systemd_config():
    if not env_config.systemd_logging:
        return

    from systemd import journal

    # remove the default handler, if already initialized
    existing_handlers = logging.getLogger().handlers
    for handlers in existing_handlers:
        logging.getLogger().removeHandler(handlers)
    # Sending logs to systemd-journal if run via systemd, printing out on console otherwise.
    logging_handler = (
        journal.JournalHandler() if env_config.systemd_logging else logging.StreamHandler()
    )
    logging.getLogger().addHandler(logging_handler)
