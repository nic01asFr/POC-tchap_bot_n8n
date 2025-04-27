# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import asyncio
import traceback
import aiohttp
import json
from collections import defaultdict
from dataclasses import dataclass
from functools import wraps

from matrix_bot.client import MatrixClient
from matrix_bot.config import logger
from matrix_bot.eventparser import EventNotConcerned, EventParser
from nio import Event, RoomEncryptedFile, RoomMemberEvent, RoomMessageText

from bot_msg import AlbertMsg
from config import COMMAND_PREFIX, Config
from core_llm import (
    flush_collections_with_name,
    get_all_public_collections,
    get_or_create_collection_with_name,
    get_or_not_collection_with_name,
    get_documents,
    generate,
    get_available_models,
    get_available_modes,
    upload_file,
)
from iam import TchapIam
from tchap_utils import (
    get_cleanup_body, 
    get_decrypted_file,
    get_previous_messages, 
    get_thread_messages, 
    isa_reply_to
)

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
        for_geek: bool,
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
            "for_geek": for_geek,
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

    def get_help(self, config: Config, verbose: bool = False) -> str:
        cmds = self._get_cmds(config, verbose)
        model_url = f"https://huggingface.co/{config.albert_model}"
        model_short_name = config.albert_model.split("/")[-1]
        return AlbertMsg.help(model_url, model_short_name, cmds)

    def show_commands(self, config: Config) -> str:
        cmds = self._get_cmds(config)
        return AlbertMsg.commands(cmds)

    def _get_cmds(self, config: Config, verbose: bool = False) -> list[str]:
        cmds = set(
            feature["help"]
            for name, feature in self.function_register.items()
            if name in self.activated_functions
            and feature["help"]
            and (not feature["for_geek"] or verbose)
            and not ("sources" in feature.get("commands") and config.albert_mode == "norag")
        )
        return sorted(list(cmds))


# ================================================================================
# Globals lifespan
# ================================================================================

command_registry = CommandRegistry({}, set())
user_configs: dict[str, Config] = defaultdict(lambda: Config())
tiam = TchapIam(Config())


async def log_not_allowed(msg: str, ep: EventParser, matrix_client: MatrixClient):
    """Send feedback message for unauthorized user"""
    config = user_configs[ep.sender]
    await matrix_client.send_markdown_message(ep.room.room_id, msg, msgtype="m.notice")

    # If user is new to the pending list, send a notification for a new pending user
    if await tiam.add_pending_user(config, ep.sender):
        if config.errors_room_id:
            try:
                await matrix_client.send_markdown_message(
                    config.errors_room_id,
                    f"\u26a0\ufe0f **New Albert Tchap user access request**\n\n{ep.sender}\n\nMatrix server: {config.matrix_home_server}",
                )
            except:
                print("Failed to find error room ?!")


# ================================================================================
# Decorators
# ================================================================================


def register_feature(
    group: str,
    onEvent: Event,
    command: str | None = None,
    aliases: list[str] | None = None,
    prefix: str = COMMAND_PREFIX,
    help: str | None = None,
    for_geek: bool = False,
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
            for_geek=for_geek,
            func=func,
        )
        return func

    return decorator


def only_allowed_user(func):
    """decorator to use with async function using EventParser"""

    @wraps(func)
    async def wrapper(ep: EventParser, matrix_client: MatrixClient):
        ep.do_not_accept_own_message()  # avoid infinite loop
        ep.only_on_direct_message()  # Only in direct room for now (need a spec for "saloon" conversation)

        config = user_configs[ep.sender]
        is_allowed, msg = await tiam.is_user_allowed(config, ep.sender, refresh=True)
        if not is_allowed:
            if not msg or ep.is_command(COMMAND_PREFIX):
                # Only send back the message for the generic albert_answer method
                # ignoring other callbacks.
                raise EventNotConcerned

            await log_not_allowed(msg, ep, matrix_client)
            return

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
    aliases=["help", "aiuto"],
    help=AlbertMsg.shorts["help"],
)
@only_allowed_user
async def help(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]

    commands = ep.get_command()
    verbose = False
    if len(commands) > 1 and commands[1] in ["-v", "--verbose", "--more", "-a", "--all"]:
        verbose = True
    await matrix_client.send_markdown_message(ep.room.room_id, command_registry.get_help(config, verbose))  # fmt: off


@register_feature(
    group="albert",
    # @DEBUG: RoomCreateEvent is not captured ?
    onEvent=RoomMemberEvent,
    help=None,
)
@only_allowed_user
async def albert_welcome(ep: EventParser, matrix_client: MatrixClient):
    """
    Receive the join/invite event and send the welcome/help message
    """
    config = user_configs[ep.sender]

    ep.only_on_join()

    config.update_last_activity()
    await matrix_client.room_typing(ep.room.room_id)
    await asyncio.sleep(
        3
    )  # wait for the room to be ready - otherwise the encryption seems to be not ready
    await matrix_client.send_markdown_message(ep.room.room_id, command_registry.get_help(config))


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="reset",
    help=AlbertMsg.shorts["reset"],
)
@only_allowed_user
async def albert_reset(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    if config.albert_with_history:
        config.update_last_activity()
        config.albert_history_lookup = 0
        reset_message = AlbertMsg.reset
        # reset_message += command_registry.show_commands(config)
        await matrix_client.send_markdown_message(
            ep.room.room_id, reset_message, msgtype="m.notice"
        )

        message = AlbertMsg.flush_start
        await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")  
        await matrix_client.room_typing(ep.room.room_id)
        flush_collections_with_name(config, ep.room.room_id)
        config.albert_collections_by_id = {}
        message = AlbertMsg.flush_end
        await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")  

    else:
        await matrix_client.send_markdown_message(
            ep.room.room_id,
            "Le mode conversation n'est pas activé. tapez !conversation pour l'activer.",
            msgtype="m.notice",
        )


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="conversation",
    help=AlbertMsg.shorts["conversation"],
    for_geek=True,
)
@only_allowed_user
async def albert_conversation(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    config.albert_history_lookup = 0
    if config.albert_with_history:
        config.albert_with_history = False
        message = "Le mode conversation est désactivé."
    else:
        config.update_last_activity()
        config.albert_with_history = True
        message = "Le mode conversation est activé."
    await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="debug",
    help=AlbertMsg.shorts["debug"],
    for_geek=True,
)
@only_allowed_user
async def albert_debug(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    debug_message = AlbertMsg.debug(config)
    await matrix_client.send_markdown_message(ep.room.room_id, debug_message, msgtype="m.notice")


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="model",
    aliases=["models"],
    help=AlbertMsg.shorts["model"],
    for_geek=True,
)
@only_allowed_user
async def albert_model(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    await matrix_client.room_typing(ep.room.room_id)
    command = ep.get_command()
    # Get all available models
    all_models = list(get_available_models(config))
    models_list = "\n\n- " + "\n- ".join(
        map(lambda x: x + (" *" if x == config.albert_model else ""), all_models)
    )
    if len(command) <= 1:
        message = "La commande !model nécessite de donner un modèle parmi :" + models_list
        message += "\n\nExemple: `!model " + all_models[-1] + "`"
    else:
        model = command[1]
        if model not in all_models:
            message = "La commande !model nécessite de donner un modèle parmi :" + models_list
            message += "\n\nExemple: `!model " + all_models[-1] + "`"
        else:
            previous_model = config.albert_model
            config.albert_model = model
            message = f"Le modèle a été modifié : {previous_model} -> {model}"
    await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="mode",
    aliases=["modes"],
    help=AlbertMsg.shorts["mode"],
    for_geek=True,
)
@only_allowed_user
async def albert_mode(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    command = ep.get_command()
    # Get all available mode for the current model
    all_modes = get_available_modes(config)
    mode_list = "\n\n- " + "\n- ".join(
        map(lambda x: x + (" *" if x == config.albert_mode else ""), all_modes)
    )
    if len(command) <= 1:
        message = "La commande !mode nécessite de donner un mode parmi :" + mode_list
        message += "\n\nExemple: `!mode " + all_modes[-1] + "`"
    else:
        mode = command[1]
        if mode not in all_modes:
            message = "La commande !mode nécessite de donner un mode parmi :" + mode_list
            message += "\n\nExemple: `!mode " + all_modes[-1] + "`"
        else:
            old_mode = config.albert_mode
            config.albert_mode = mode
            message = f"Le mode a été modifié : {old_mode} -> {mode}"
        
    await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")

    if mode == "norag":
        message = AlbertMsg.flush_start
        await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")  
        await matrix_client.room_typing(ep.room.room_id)
        flush_collections_with_name(config, ep.room.room_id)
        config.albert_collections_by_id = {}
        message = AlbertMsg.flush_end
        await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")  


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="sources",
    help=AlbertMsg.shorts["sources"],
)
@only_allowed_user
async def albert_sources(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]

    try:
        if config.last_rag_chunks:
            await matrix_client.room_typing(ep.room.room_id)
            sources_msg = ""
            for chunk in config.last_rag_chunks[:max(30, len(config.last_rag_chunks))]:
                sources_msg += f'________________________________________\n'
                sources_msg += f'####{chunk["metadata"]["document_name"]}\n'
                sources_msg += f'{chunk["content"]}\n'
        else:
            sources_msg = "Aucune source trouvée, veuillez me poser une question d'abord."
    except Exception:
        traceback.print_exc()
        await matrix_client.send_markdown_message(ep.room.room_id, AlbertMsg.failed, msgtype="m.notice")  # fmt: off
        return

    await matrix_client.send_markdown_message(ep.room.room_id, sources_msg)


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="collections",
    help=AlbertMsg.shorts["collections"],
)
@only_allowed_user
async def albert_collection(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    await matrix_client.room_typing(ep.room.room_id)
    command = ep.get_command()
    if len(command) <= 1:
        message = f"La commande !collections nécessite de donner list/use/unuse/info puis éventuellement <nom_de_collection>/{config.albert_all_public_command} :"
        message += "\n\nExemple: `!collections use decisions-adlc`"
    elif command[1] != 'list' and len(command) <= 2:
        if command[1] not in ['use', 'unuse']:
            message = f"La commande !collections {command[1]} n'est pas reconnue, seul list/use/unuse sont autorisés"
        else:
            message = f"La commande !collections {command[1]} nécessite de donner en plus COLLECTION_NAME/{config.albert_all_public_command} :"
            message += "\n\nExemple: `!collections use decisions-adlc`"
    else:
        method = command[1]
        if method == 'list':
            collections = config.albert_collections_by_id.values()
            collection_display_names = [c['name'] if c['name'] != ep.room.room_id else config.albert_my_private_collection_name for c in collections]
            collection_ids = [c['id'] for c in collections]
            collection_infos = '\n - ' + '\n - '.join([f"{display_name}" for display_name, collection_id in zip(collection_display_names, collection_ids)])
            if not collections:
                message = "Vous n'avez pas de collections enregistrées pour le moment qui pourraient m'aider à répondre à vos questions."
            else:
                message = (
                    "Les collections :\n"
                    f"{collection_infos}\n\n"
                    "sont prises en compte pour m'aider à répondre à vos questions."
                )
            collections = get_all_public_collections(config)
            message += "\n\nNotez que les collections publiques à votre disposition sont:\n"
            message += '\n - ' + '\n - '.join([f"{c['name']}" for c in collections])
            message += f"\n\nVous pouvez toutes les ajouter d'un coup en utilisant la commande `!collections use {config.albert_all_public_command}`"
        elif method == 'info':
            collection_name = command[2] if command[2] != config.albert_my_private_collection_name else ep.room.room_id
            collection = get_or_not_collection_with_name(config, collection_name)
            if not collection:
                message = f"La collection {collection_name} n'existe pas."
            else:
                document_infos = [f"{d['name']} ({d['id']})" for d in get_documents(config, collection['id'])]
                if not document_infos:
                    message = (
                        f"Collection '{command[2]}' ({collection['id']}) : \n\n"
                        f"Aucun document n'est présent dans cette collection ({collection['id']})."
                    )
                else:
                    document_infos_message = '\n - ' + '\n - '.join(document_infos)
                    message = (
                        f"Collection '{command[2]}' ({collection['id']}) : \n\n"
                        "Voici les documents actuellement présents dans la collection : \n\n"
                        f"{document_infos_message}"
                        "\n\n"
                    )
        elif method == 'use':
            if command[2] == config.albert_all_public_command:
                collections = get_all_public_collections(config)
            else:
                collection = get_or_not_collection_with_name(config, command[2])
                if not collection:
                    message = f"La collection {command[2]} n'existe pas."
                    collections = []
                else:
                    collections = [collection]
            if collections:
                collection_names = ','.join([c['name'] for c in collections])
                for collection in collections:
                    config.albert_collections_by_id[collection["id"]] = collection
                collection_infos = '\n - ' + '\n - '.join([f"{c['name']}" for c in config.albert_collections_by_id.values()])
                message = (
                    f"Les collections {collection_names} sont ajoutées à vos collections.\n\n" if len(collections) > 1 else f"La collection {command[2]} est ajoutée à vos collections.\n\n"
                    "Maintenant, les collections :\n"
                    f"{collection_infos}\n\n"
                    "sont disponibles pour m'aider à répondre à vos questions."
                )
        else:
            collections = config.albert_collections_by_id.values()
            collection_names = ','.join([c['name'] for c in collections])
            config.albert_collections_by_id = {}
            if not collections:
                message = "Il n'y avait pas de collections à retirer."
            else:
                message = f"Les collections {collection_names} sont retirées de vos collections."
    await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")
    
@register_feature(
    group="albert",
    onEvent=RoomEncryptedFile,
    help=None
)
@only_allowed_user
async def albert_document(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]

    try:
        await matrix_client.room_typing(ep.room.room_id)
        if ep.event.mimetype in ['application/json', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            config.update_last_activity()       
            config.albert_mode = "rag"
            collection = get_or_create_collection_with_name(config, ep.room.room_id)
            config.albert_collections_by_id[collection['id']] = collection
            file = await get_decrypted_file(ep)
            upload_file(config, file, collection['id'])
            private_document_infos = [d['name'] for d in get_documents(config, collection['id'])]
            private_document_infos_message = '\n - ' + '\n - '.join(private_document_infos)
            response = (
                "Votre document : \n\n"
                f"\"{file.name}\"\n\n"
                "a été chargé dans votre collection privée.\n\n"
                "Voici les documents actuellement présents dans votre collection privée : \n\n"
                f"{private_document_infos_message}"
                "\n\n"
                "Je tiendrai compte de tous ces documents pour répondre. \n\n"
                "Vous pouvez taper \"!mode norag\" pour vider votre collection privée de tous ces documents."
            )
        else:
            response = (
                f"J'ai détecté que vous avez téléchargé un fichier {ep.event.mimetype}. "
                "Ce fichier n'est pris en charge par Albert. "
                "Veuillez téléverser un fichier PDF, DOCX ou JSON."
            )
        await matrix_client.send_markdown_message(ep.room.room_id, response, msgtype="m.notice")
    
    except Exception as albert_err:
        logger.error(f"{albert_err}")
        traceback.print_exc()
        await matrix_client.send_markdown_message(ep.room.room_id, AlbertMsg.failed, msgtype="m.notice")
        if config.errors_room_id:
            try:
                await matrix_client.send_markdown_message(config.errors_room_id, AlbertMsg.error_debug(albert_err, config))
            except:
                print("Failed to find error room ?!")

@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="webhook",
    help="Configure le webhook n8n pour ce salon. Utilisation: !webhook set URL ou !webhook status pour voir l'URL actuelle",
    for_geek=True,
)
@only_allowed_user
async def set_webhook(ep: EventParser, matrix_client: MatrixClient):
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
    group="albert",
    onEvent=RoomMessageText,
    command="webhookin",
    help="Configure un webhook entrant pour ce salon. Utilisation: !webhookin create pour générer une URL",
    for_geek=True,
)
@only_allowed_user
async def configure_incoming_webhook(ep: EventParser, matrix_client: MatrixClient):
    from webhook_server import register_webhook_room
    
    config = user_configs[ep.sender]
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
                webhook_url = f"http://{env_config.webhook_host}:{env_config.webhook_port}{env_config.webhook_endpoint}?token={token}"
                message += f"- `{webhook_url}`\n"
        
        await matrix_client.send_markdown_message(ep.room.room_id, message)
    
    else:
        message = "Commande non reconnue. Utilisation: !webhookin create [token] - Crée une URL webhook pour recevoir des messages dans ce salon"
        await matrix_client.send_markdown_message(ep.room.room_id, message)

@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    help=None,
)
@only_allowed_user
async def albert_answer(ep: EventParser, matrix_client: MatrixClient):
    """
    Receive a message event which is not a command, send the prompt to Albert API and return the response to the user
    """
    config = user_configs[ep.sender]

    initial_history_lookup = config.albert_history_lookup

    user_query = ep.event.body.strip()
    if ep.is_command(COMMAND_PREFIX):
        raise EventNotConcerned

    if config.albert_with_history and config.is_conversation_obsolete:
        config.albert_history_lookup = 0
        obsolescence_in_minutes = str(config.conversation_obsolescence // 60)
        reset_message = AlbertMsg.reset_notif(obsolescence_in_minutes)
        await matrix_client.send_markdown_message(
            ep.room.room_id, reset_message, msgtype="m.notice"
        )
        flush_collections_with_name(config, ep.room.room_id)
        config.albert_collections_by_id = {}

    config.update_last_activity()
    await matrix_client.room_typing(ep.room.room_id)
    try:
        # Build the messages  history
        # --
        is_reply_to = isa_reply_to(ep.event)
        if is_reply_to:
            # Use the targeted thread history
            # --
            message_events = await get_thread_messages(
                config, ep, max_rewind=config.albert_max_rewind
            )
        else:
            # Use normal history
            # --
            # Add the current user query in the history count
            config.albert_history_lookup += 1
            message_events = await get_previous_messages(
                config,
                ep,
                history_lookup=config.albert_history_lookup,
                max_rewind=config.albert_max_rewind,
            )

        # Map event to list of message {role, content} and cleanup message body
        # @TODO: If bot should answer in multi-user canal, we could catch is own name here.
        messages = [
            {"role": "user", "content": get_cleanup_body(event)}
            if event.source["sender"] == ep.sender
            else {"role": "assistant", "content": get_cleanup_body(event)}
            for event in message_events
        ]

        # Empty chunk (i.e at startup)
        if not messages:
            messages = [{"role": "user", "content": user_query}]

        answer = generate(config, messages)

    except Exception as albert_err:
        logger.error(f"{albert_err}")
        traceback.print_exc()
        # Send an error message to the user
        await matrix_client.send_markdown_message(
            ep.room.room_id, AlbertMsg.failed, msgtype="m.notice"
        )
        # Redirect the error message to the errors room if it exists
        if config.errors_room_id:
            try:
                await matrix_client.send_markdown_message(config.errors_room_id, AlbertMsg.error_debug(albert_err, config))  # fmt: off
            except:
                print("Failed to find error room ?!")

        config.albert_history_lookup = initial_history_lookup
        return

    logger.debug(f"{user_query=}")
    logger.debug(f"{answer=}")

    reply_to = None
    if is_reply_to:
        # "content" ->  "m.mentions": {"user_ids": [ep.sender]},
        # "content" -> "m.relates_to": {"m.in_reply_to": {"event_id": ep.event.event_id}},
        reply_to = ep.event.event_id

    try:  # sometimes the async code fail (when input is big) with random asyncio errors
        await matrix_client.send_markdown_message(ep.room.room_id, answer, reply_to=reply_to)
        await tiam.increment_user_question(ep.sender)
    except Exception as llm_exception:  # it seems to work when we retry
        logger.error(f"asyncio error when sending message {llm_exception=}. retrying")
        await asyncio.sleep(1)
        try:
            # Try once more
            await matrix_client.send_markdown_message(ep.room.room_id, answer, reply_to=reply_to)
            await tiam.increment_user_question(ep.sender)
        except:
            config.albert_history_lookup = initial_history_lookup
            return

    # Add agent answer in the history count
    if not is_reply_to:
        config.albert_history_lookup += 1

    # Extrait du code existant
    body = get_cleanup_body(ep.event.body)
    if not body:
        return
    
    config = user_configs[ep.sender]
    config.update_last_activity()

    # Si une commande reconnue est détectée, on passe
    if ep.is_command(COMMAND_PREFIX) and command_registry.is_valid_command(ep.event.body.strip().split()[0].removeprefix(COMMAND_PREFIX)):
        return
    
    # Envoi du message au webhook si configuré
    webhook_url = getattr(config, 'webhook_url', {}).get(ep.room.room_id)
    if webhook_url:
        try:
            webhook_method = getattr(config, 'webhook_method', {}).get(ep.room.room_id, "GET")
            message_data = {
                "event": "message",
                "room_id": ep.room.room_id,
                "sender": ep.sender,
                "message": body
            }
            await send_to_webhook(webhook_url, message_data, method=webhook_method)
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi au webhook: {str(e)}")
    
    # Continue with the existing albert_answer function
    # ... rest of the existing function ...

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

@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    help=None,
)
async def albert_wrong_command(ep: EventParser, matrix_client: MatrixClient):
    """Special handler to catch invalid command"""
    config = user_configs[ep.sender]

    ep.do_not_accept_own_message()  # avoid infinite loop
    ep.only_on_direct_message()  # Only in direct room for now (need a spec for "saloon" conversation)

    command = ep.event.body.strip().lstrip(COMMAND_PREFIX).split()
    if not ep.is_command(COMMAND_PREFIX):
        # Not a command
        raise EventNotConcerned
    elif command_registry.is_valid_command(command[0]):
        # Valid command
        raise EventNotConcerned

    is_allowed, msg = await tiam.is_user_allowed(config, ep.sender, refresh=True)
    if not is_allowed:
        await log_not_allowed(msg, ep, matrix_client)
        return

    cmds_msg = command_registry.show_commands(config)
    await matrix_client.send_markdown_message(
        ep.room.room_id, AlbertMsg.unknown_command(cmds_msg), msgtype="m.notice"
    )
