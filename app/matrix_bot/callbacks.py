# SPDX-FileCopyrightText: 2021 - 2022 Isaac Beverly <https://github.com/imbev>
# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
#
# SPDX-License-Identifier: MIT
import traceback
from functools import wraps

from nio import (
    Event,
    InviteMemberEvent,
    MatrixRoom,
    MegolmEvent,
    RoomMessageText,
    ToDeviceEvent,
    UnknownEvent,
)

from bot_msg import AlbertMsg

from .client import MatrixClient
from .config import bot_lib_config, logger
from .eventparser import (
    EventNotConcerned,
    EventParser,
    MessageEventParser,
)
from ..webhook_optimized import initialize_room


def properly_fail(matrix_client, error_msg=AlbertMsg.failed):
    """use this decorator so that your async callback never crash,
    log the error and return a message to the room"""

    def decorator(func):
        @wraps(func)
        async def wrapper(room, event):
            try:
                return await func(room, event)
            except Exception as unexpected_exception:
                await matrix_client.send_text_message(room.room_id, error_msg, msgtype="m.notice")
                logger.warning(f"command failed with exception: {unexpected_exception}")
                traceback.print_exc()
            finally:
                await matrix_client.room_typing(room.room_id, typing_state=False)

        return wrapper

    return decorator


def ignore_when_not_concerned(func):
    """decorator to use with async function using EventParser"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except EventNotConcerned:
            return

    return wrapper


class Callbacks:
    """A class for handling callbacks."""

    def __init__(self, matrix_client: MatrixClient):
        self.matrix_client = matrix_client
        self.startup: list = []
        self.client_callback: list = []

    def register_on_custom_event(self, func, onEvent: Event, feature: dict):
        @properly_fail(self.matrix_client)
        @ignore_when_not_concerned
        async def wrapped_func(room, event):
            if not isinstance(event, onEvent):
                raise EventNotConcerned

            if onEvent == RoomMessageText:
                ep = MessageEventParser(
                    room=room, event=event, matrix_client=self.matrix_client, log_usage=True
                )
                if feature.get("commands"):
                    ep.parse_command(feature["commands"], prefix=feature["prefix"])
            else:
                ep = EventParser(
                    room=room, event=event, matrix_client=self.matrix_client, log_usage=True
                )

            await func(ep=ep, matrix_client=self.matrix_client)
        self.client_callback.append((wrapped_func, onEvent))

    def register_on_reaction_event(self, func):
        @properly_fail(self.matrix_client)
        @ignore_when_not_concerned
        async def wrapped_func(room: MatrixRoom, event: Event):
            if event.type == "m.reaction":
                await func(room, event, event.source["content"]["m.relates_to"]["key"])

        self.client_callback.append((wrapped_func, UnknownEvent))

    def register_on_startup(self, func):
        self.startup.append(func)

    async def setup_callbacks(self):
        """Add callbacks to async_client"""
        if bot_lib_config.join_on_invite:
            self.matrix_client.add_event_callback(self.invite_callback, InviteMemberEvent)

        self.matrix_client.add_event_callback(self.decryption_failure, MegolmEvent)
        for function, event in self.client_callback:
            if issubclass(event, ToDeviceEvent):
                self.matrix_client.add_to_device_callback(function, event)
            else:
                self.matrix_client.add_event_callback(function, event)

    async def invite_callback(self, room: MatrixRoom, event: InviteMemberEvent):
        """Callback for handling invites."""
        if not event.membership == "invite":
            return

        # Vérifier que l'invitation est bien adressée au bot
        if event.state_key != self.matrix_client.user_id:
            logger.debug(f"Invitation ignorée car non adressée au bot: {event.state_key} != {self.matrix_client.user_id}")
            return
        
        logger.info(f"Invitation reçue pour le salon {room.room_id} de la part de {event.sender}")
        try:
            # Afficher plus d'informations sur l'invitation
            room_name = room.name or "Salon sans nom"
            logger.info(f"Tentative de rejoindre le salon: {room_name} ({room.room_id})")
            
            # Essayer de rejoindre le salon
            join_response = await self.matrix_client.join(room.room_id)
            
            if hasattr(join_response, "room_id"):
                logger.info(f"Salon rejoint avec succès: {room.room_id}")
                
                # Initialiser le salon après l'avoir rejoint
                # Récupérer le token d'accès du client Matrix
                access_token = self.matrix_client.access_token
                if access_token:
                    # Initialiser le salon avec les informations de base
                    await initialize_room(room.room_id, access_token)
                    logger.info(f"Salon {room.room_id} initialisé après invitation")
                    
                    # Envoyer un message de bienvenue
                    welcome_message = "Bonjour ! Je suis Albert, le bot assistant pour Tchap. Utilisez `!aide` pour voir la liste des commandes disponibles."
                    try:
                        await self.matrix_client.send_markdown_message(room.room_id, welcome_message)
                        logger.info(f"Message de bienvenue envoyé dans le salon {room.room_id}")
                    except Exception as msg_error:
                        logger.error(f"Erreur lors de l'envoi du message de bienvenue: {str(msg_error)}")
                else:
                    logger.warning(f"Impossible d'initialiser le salon {room.room_id} : pas de token d'accès")
            else:
                error_msg = getattr(join_response, "message", "Raison inconnue")
                logger.error(f"Échec lors de la tentative de rejoindre le salon {room.room_id}: {error_msg}")
        except Exception as join_room_exception:
            logger.error(f"Erreur lors de la tentative de rejoindre le salon {room.room_id}: {str(join_room_exception)}")
            import traceback
            logger.error(f"Détails de l'erreur: {traceback.format_exc()}")

    async def decryption_failure(self, room: MatrixRoom, event: MegolmEvent):
        """Callback for handling decryption errors."""
        if not isinstance(event, MegolmEvent):
            return

        logger.error(
            f"Failed to decrypt message: {event.event_id} from {event.sender} in {room.room_id}. "
            "If this error persists despite verification, reset the crypto session by deleting "
            f"{self.matrix_client.matrix_config.store_path} "
            f"and {self.matrix_client.auth.credentials.session_stored_file_path}. "
            "You will have to verify any verified devices anew."
        )
        await self.matrix_client.send_text_message(
            room.room_id,
            "Failed to decrypt your message. Make sure encryption is enabled in my config and "
            "either enable sending messages to unverified devices or verify me if possible.",
            msgtype="m.notice",
        )
