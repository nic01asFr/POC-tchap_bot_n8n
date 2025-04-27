# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import json
import aiohttp
from dataclasses import dataclass
from functools import wraps

from matrix_bot.client import MatrixClient
from matrix_bot.config import logger
from matrix_bot.eventparser import EventNotConcerned, EventParser
from nio import Event, RoomMemberEvent, RoomMessageText

from config import COMMAND_PREFIX, Config, env_config
from tchap_utils import get_cleanup_body

@dataclass
class CommandRegistry:
    function_register: dict
    activated_functions: set[str]

    def add_command(
        self,
        name: str,
        group: str,
        onEvent: Event,
        command: str | None,
        aliases: list[str] | None,
        prefix: str | None,
        help_message: str | None,
        func,
    ):
        commands = [command] if command else None
        if aliases:
            commands += aliases

        self.function_register[name] = {
            "name": name,
            "group": group,
            "onEvent": onEvent,
            "commands": commands,
            "prefix": prefix,
            "help": help_message,
            "func": func,
        }

    def activate_and_retrieve_group(self, group_name: str) -> list:
        features = []
        for name, feature in self.function_register.items():
            if feature["group"] == group_name:
                self.activated_functions |= {name}
                features.append(feature)
        return features

    def is_valid_command(self, command) -> bool:
        valid_commands = []
        for name, feature in self.function_register.items():
            if name in self.activated_functions:
                if feature.get("commands"):
                    valid_commands += feature["commands"]
        return command in valid_commands

    def get_help(self) -> str:
        help_messages = []
        for name, feature in self.function_register.items():
            if name in self.activated_functions and feature["help"]:
                help_messages.append(feature["help"])
        
        help_text = f"# {env_config.bot_name}\n\n"
        help_text += "Ce bot sert d'intermédiaire entre n8n et les salons Matrix Tchap.\n\n"
        help_text += "## Commandes disponibles\n\n"
        for help_msg in sorted(help_messages):
            help_text += f"- {help_msg}\n"
        
        return help_text


# Globales
command_registry = CommandRegistry({}, set())
user_configs = {}


def register_feature(
    group: str,
    onEvent: Event,
    command: str | None = None,
    aliases: list[str] | None = None,
    prefix: str = COMMAND_PREFIX,
    help: str | None = None,
):
    def decorator(func):
        command_registry.add_command(
            name=func.__name__,
            group=group,
            onEvent=onEvent,
            command=command,
            aliases=aliases,
            prefix=prefix,
            help_message=help,
            func=func,
        )
        return func

    return decorator


def only_allowed_user(func):
    """decorator to use with async function using EventParser"""
    @wraps(func)
    async def wrapper(ep: EventParser, matrix_client: MatrixClient):
        ep.do_not_accept_own_message()  # avoid infinite loop
        
        # Vérifier si l'utilisateur est autorisé
        if env_config.is_user_authorized:
            user_domain = ep.sender.split(":", 1)[1]
            allowed_domains = env_config.user_allowed_domains
            if "*" not in allowed_domains and user_domain not in allowed_domains:
                await matrix_client.send_markdown_message(
                    ep.room.room_id, 
                    "Vous n'êtes pas autorisé à utiliser ce bot.",
                    msgtype="m.notice"
                )
                return
        
        # Initialiser la configuration utilisateur si nécessaire
        if ep.sender not in user_configs:
            user_configs[ep.sender] = Config()
        
        await func(ep, matrix_client)
        await matrix_client.room_typing(ep.room.room_id, typing_state=False)

    return wrapper


# ================================================================================
# Bot commands
# ================================================================================

@register_feature(
    group="basic",
    onEvent=RoomMessageText,
    command="aide",
    aliases=["help"],
    help="Affiche ce message d'aide",
)
@only_allowed_user
async def help(ep: EventParser, matrix_client: MatrixClient):
    """Affiche l'aide du bot"""
    await matrix_client.send_markdown_message(ep.room.room_id, command_registry.get_help())


@register_feature(
    group="basic",
    onEvent=RoomMemberEvent,
    help=None,
)
@only_allowed_user
async def welcome(ep: EventParser, matrix_client: MatrixClient):
    """Message de bienvenue lorsque le bot rejoint un salon"""
    try:
        ep.only_on_join()
        await matrix_client.send_markdown_message(ep.room.room_id, command_registry.get_help())
    except EventNotConcerned:
        pass


@register_feature(
    group="webhook",
    onEvent=RoomMessageText,
    command="webhook",
    help="Configure le webhook n8n sortant. Utilisation: !webhook set URL [GET/POST] ou !webhook status",
)
@only_allowed_user
async def set_webhook(ep: EventParser, matrix_client: MatrixClient):
    """Configure un webhook pour envoyer des messages de ce salon vers n8n"""
    config = user_configs[ep.sender]
    
    # Initialize webhook config if it doesn't exist
    if not hasattr(config, 'webhook_url'):
        config.webhook_url = {}
    if not hasattr(config, 'webhook_method'):
        config.webhook_method = {}
    
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    
    if not parts:
        message = "Utilisation: !webhook set URL [GET/POST] ou !webhook status"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    action = parts[0].lower()
    
    if action == "set" and len(parts) > 1:
        webhook_url = parts[1]
        
        # Par défaut, utiliser GET comme méthode, mais permettre de spécifier POST
        webhook_method = "GET"
        if len(parts) > 2:
            method = parts[2].upper()
            if method in ["GET", "POST"]:
                webhook_method = method
        
        config.webhook_url[ep.room.room_id] = webhook_url
        config.webhook_method[ep.room.room_id] = webhook_method
        
        message = f"Webhook configuré avec succès pour ce salon:\nURL: {webhook_url}\nMéthode: {webhook_method}"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
    
    elif action == "status":
        webhook_url = config.webhook_url.get(ep.room.room_id, "Non configuré")
        webhook_method = config.webhook_method.get(ep.room.room_id, "GET")
        message = f"Configuration webhook actuelle:\nURL: {webhook_url}\nMéthode: {webhook_method}"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
    
    elif action == "test" and config.webhook_url.get(ep.room.room_id):
        webhook_url = config.webhook_url.get(ep.room.room_id)
        webhook_method = config.webhook_method.get(ep.room.room_id, "GET")
        try:
            await send_to_webhook(webhook_url, {
                "event": "test",
                "room_id": ep.room.room_id,
                "sender": ep.sender,
                "message": "Test du webhook n8n"
            }, method=webhook_method)
            message = f"Test du webhook envoyé avec succès (méthode: {webhook_method})"
        except Exception as e:
            message = f"Erreur lors du test du webhook: {str(e)}"
        
        await matrix_client.send_markdown_message(ep.room.room_id, message)
    
    else:
        message = "Commande non reconnue. Utilisation: !webhook set URL [GET/POST] ou !webhook status"
        await matrix_client.send_markdown_message(ep.room.room_id, message)


@register_feature(
    group="webhook",
    onEvent=RoomMessageText,
    command="webhookin",
    help="Configure un webhook entrant. Utilisation: !webhookin create [token] ou !webhookin list",
)
@only_allowed_user
async def configure_incoming_webhook(ep: EventParser, matrix_client: MatrixClient):
    """Configure un webhook pour recevoir des messages de n8n dans ce salon"""
    from webhook_server import register_webhook_room
    
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    
    if not parts:
        message = "Utilisation: !webhookin create [token] - Crée une URL webhook pour recevoir des messages dans ce salon"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    action = parts[0].lower()
    
    if action == "create":
        token = parts[1] if len(parts) > 1 else None
        webhook_url = await register_webhook_room(matrix_client, ep.room.room_id, token)
        message = f"Webhook entrant configuré avec succès pour ce salon.\n\nURL: `{webhook_url}`\n\nUtilisez cette URL dans n8n pour envoyer des messages à ce salon."
        await matrix_client.send_markdown_message(ep.room.room_id, message)
    
    elif action == "list":
        # List all incoming webhooks for this room
        room_webhooks = {token: room_id for token, room_id in env_config.webhook_incoming_rooms.items() if room_id == ep.room.room_id}
        
        if not room_webhooks:
            message = "Aucun webhook entrant configuré pour ce salon."
        else:
            message = "Webhooks entrants configurés pour ce salon:\n\n"
            for token, _ in room_webhooks.items():
                webhook_url = f"http://{env_config.webhook_host}:{env_config.webhook_port}/webhook-test/matrix_webhook?token={token}"
                message += f"- `{webhook_url}`\n"
        
        await matrix_client.send_markdown_message(ep.room.room_id, message)
    
    else:
        message = "Commande non reconnue. Utilisation: !webhookin create [token] - Crée une URL webhook pour recevoir des messages dans ce salon"
        await matrix_client.send_markdown_message(ep.room.room_id, message)


@register_feature(
    group="webhook",
    onEvent=RoomMessageText,
    help=None,
)
@only_allowed_user
async def forward_message(ep: EventParser, matrix_client: MatrixClient):
    """Transmet les messages du salon vers le webhook n8n configuré"""
    if ep.is_command(COMMAND_PREFIX):
        # Ne pas traiter les commandes
        return
    
    config = user_configs.get(ep.sender, Config())
    
    # Récupérer le texte du message
    body = get_cleanup_body(ep.event.body)
    if not body:
        return
    
    # Déterminer l'URL du webhook à utiliser
    webhook_url = None
    webhook_method = "GET"
    
    # Priorité à la configuration par salon si elle existe
    room_webhook_url = getattr(config, 'webhook_url', {}).get(ep.room.room_id)
    if room_webhook_url:
        webhook_url = room_webhook_url
        webhook_method = getattr(config, 'webhook_method', {}).get(ep.room.room_id, "GET")
    # Sinon, utiliser la configuration globale si elle est activée
    elif env_config.global_webhook_auto_forward and env_config.global_webhook_url:
        webhook_url = env_config.global_webhook_url
        webhook_method = env_config.global_webhook_method
    
    # Envoyer le message au webhook si configuré
    if webhook_url:
        try:
            message_data = {
                "event": "message",
                "room_id": ep.room.room_id,
                "sender": ep.sender,
                "message": body
            }
            await send_to_webhook(webhook_url, message_data, method=webhook_method)
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi au webhook: {str(e)}")


async def send_to_webhook(webhook_url, data, method="GET"):
    """Send data to the webhook URL using GET or POST"""
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            # Pour GET, convertir les données en paramètres de requête
            params = {}
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    params[key] = json.dumps(value)
                else:
                    params[key] = str(value)
            
            async with session.get(webhook_url, params=params) as response:
                if response.status >= 400:
                    raise Exception(f"Erreur HTTP {response.status}: {await response.text()}")
                return await response.json() if response.content_type == 'application/json' else await response.text()
        else:
            # Pour POST, envoyer les données en JSON dans le corps
            async with session.post(webhook_url, json=data) as response:
                if response.status >= 400:
                    raise Exception(f"Erreur HTTP {response.status}: {await response.text()}")
                return await response.json() if response.content_type == 'application/json' else await response.text() 