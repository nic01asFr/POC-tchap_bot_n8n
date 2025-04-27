# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

"""
Module qui implémente des commandes Tchap dans le bot.
Ce module fournit des fonctions pour envoyer des messages avec différents effets et formattages
compatibles avec les commandes natives de Tchap.
"""

from matrix_bot.client import MatrixClient
from matrix_bot.config import logger
from matrix_bot.eventparser import EventParser
from nio import RoomMessageText

from config import COMMAND_PREFIX
from webhook_commands import register_feature, only_allowed_user


# ================================================================================
# Commandes de formatage de message
# ================================================================================

@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="spoiler",
    help="Envoie le message flouté",
)
@only_allowed_user
async def spoiler_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message avec effet de floutage (spoiler)"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    if not parts:
        message = "Utilisation: !spoiler <message>"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    message = " ".join(parts)
    html_content = f'<span data-mx-spoiler>{message}</span>'
    
    await matrix_client.send_html_message(ep.room.room_id, html_content)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="shrug",
    help="Ajoute ¯\\_(ツ)_/¯ en préfixe du message",
)
@only_allowed_user
async def shrug_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message avec un shrug en préfixe"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    message = " ".join(parts) if parts else ""
    
    formatted_message = f"¯\\_(ツ)_/¯ {message}"
    await matrix_client.send_text_message(ep.room.room_id, formatted_message)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="tableflip",
    help="Ajoute (╯°□°）╯︵ ┻━┻ en préfixe du message",
)
@only_allowed_user
async def tableflip_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message avec tableflip en préfixe"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    message = " ".join(parts) if parts else ""
    
    formatted_message = f"(╯°□°）╯︵ ┻━┻ {message}"
    await matrix_client.send_text_message(ep.room.room_id, formatted_message)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="unflip",
    help="Ajoute ┬──┬ ノ( ゜-゜ノ) en préfixe du message",
)
@only_allowed_user
async def unflip_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message avec unflip en préfixe"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    message = " ".join(parts) if parts else ""
    
    formatted_message = f"┬──┬ ノ( ゜-゜ノ) {message}"
    await matrix_client.send_text_message(ep.room.room_id, formatted_message)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="lenny",
    help="Ajoute ( ͡° ͜ʖ ͡°) en préfixe du message",
)
@only_allowed_user
async def lenny_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message avec lenny en préfixe"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    message = " ".join(parts) if parts else ""
    
    formatted_message = f"( ͡° ͜ʖ ͡°) {message}"
    await matrix_client.send_text_message(ep.room.room_id, formatted_message)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="plain",
    help="Envoie un message en texte brut, sans l'interpréter en format markdown",
)
@only_allowed_user
async def plain_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message en texte brut"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    if not parts:
        message = "Utilisation: !plain <message>"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    message = " ".join(parts)
    await matrix_client.send_text_message(ep.room.room_id, message)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="html",
    help="Envoie un message en HTML, sans l'interpréter comme du Markdown",
)
@only_allowed_user
async def html_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message en HTML"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    if not parts:
        message = "Utilisation: !html <message HTML>"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    message = " ".join(parts)
    await matrix_client.send_html_message(ep.room.room_id, message)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="me",
    help="Affiche l'action",
)
@only_allowed_user
async def me_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message d'action (emote)"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    if not parts:
        message = "Utilisation: !me <action>"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    message = " ".join(parts)
    # En Matrix, m.emote est un type spécial pour les actions
    await matrix_client.send_text_message(ep.room.room_id, message, msgtype="m.emote")


# ================================================================================
# Commandes d'effets visuels
# ================================================================================

@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="rainbow",
    help="Envoie le message coloré aux couleurs de l'arc-en-ciel",
)
@only_allowed_user
async def rainbow_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message aux couleurs de l'arc-en-ciel"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    if not parts:
        message = "Utilisation: !rainbow <message>"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    text = " ".join(parts)
    # Implémentation simplifiée - on utilise un effet CSS pour l'arc-en-ciel
    rainbow_html = f'<span style="background-image: linear-gradient(to right, red, orange, yellow, green, blue, indigo, violet); -webkit-background-clip: text; color: transparent;">{text}</span>'
    
    await matrix_client.send_html_message(ep.room.room_id, rainbow_html)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="rainbowme",
    help="Envoie la réaction colorée aux couleurs de l'arc-en-ciel",
)
@only_allowed_user
async def rainbowme_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie une action (emote) aux couleurs de l'arc-en-ciel"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    if not parts:
        message = "Utilisation: !rainbowme <message>"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    text = " ".join(parts)
    # Implémentation simplifiée - on combine les effets arc-en-ciel et emote
    rainbow_html = f'<span style="background-image: linear-gradient(to right, red, orange, yellow, green, blue, indigo, violet); -webkit-background-clip: text; color: transparent;">{text}</span>'
    
    await matrix_client.send_html_message(ep.room.room_id, rainbow_html, msgtype="m.emote")


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="confetti",
    help="Envoie le message avec des confettis",
)
@only_allowed_user
async def confetti_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message avec effet de confettis"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    if not parts:
        message = "Utilisation: !confetti <message>"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    message = " ".join(parts)
    
    # Les effets spéciaux comme confettis nécessitent normalement du JavaScript côté client
    # Pour simuler, nous ajoutons simplement des émojis confettis au message
    formatted_message = f"🎊 {message} 🎊"
    await matrix_client.send_text_message(ep.room.room_id, formatted_message)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="fireworks",
    help="Envoie le message donné avec des feux d'artifices",
)
@only_allowed_user
async def fireworks_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message avec effet de feux d'artifice"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    if not parts:
        message = "Utilisation: !fireworks <message>"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    message = " ".join(parts)
    
    # Simulation avec des émojis
    formatted_message = f"🎆 {message} 🎆"
    await matrix_client.send_text_message(ep.room.room_id, formatted_message)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="hearts",
    help="Envoie le message donné avec des cœurs",
)
@only_allowed_user
async def hearts_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message avec effet de cœurs"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    if not parts:
        message = "Utilisation: !hearts <message>"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    message = " ".join(parts)
    
    # Simulation avec des émojis
    formatted_message = f"❤️ {message} ❤️"
    await matrix_client.send_text_message(ep.room.room_id, formatted_message)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="rainfall",
    help="Envoie le message avec de la pluie",
)
@only_allowed_user
async def rainfall_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message avec effet de pluie"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    if not parts:
        message = "Utilisation: !rainfall <message>"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    message = " ".join(parts)
    
    # Simulation avec des émojis
    formatted_message = f"🌧️ {message} 🌧️"
    await matrix_client.send_text_message(ep.room.room_id, formatted_message)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="snowfall",
    help="Envoie le message donné avec une chute de neige",
)
@only_allowed_user
async def snowfall_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message avec effet de neige"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    if not parts:
        message = "Utilisation: !snowfall <message>"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    message = " ".join(parts)
    
    # Simulation avec des émojis
    formatted_message = f"❄️ {message} ❄️"
    await matrix_client.send_text_message(ep.room.room_id, formatted_message)


@register_feature(
    group="tchap",
    onEvent=RoomMessageText,
    command="spaceinvaders",
    help="Envoyer le message avec un effet lié au thème de l'espace",
)
@only_allowed_user
async def spaceinvaders_message(ep: EventParser, matrix_client: MatrixClient):
    """Envoie un message avec effet space invaders"""
    parts = ep.command[1:] if ep.command and len(ep.command) > 1 else []
    if not parts:
        message = "Utilisation: !spaceinvaders <message>"
        await matrix_client.send_markdown_message(ep.room.room_id, message)
        return
    
    message = " ".join(parts)
    
    # Simulation avec des émojis et caractères
    formatted_message = f"👾 {message} 👾"
    await matrix_client.send_text_message(ep.room.room_id, formatted_message) 