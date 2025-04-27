"""
Commandes n8n pour Albert-Tchap.

Ce module ajoute les commandes n8n au bot Albert-Tchap.
"""

from matrix_bot.client import MatrixClient
from matrix_bot.config import logger
from matrix_bot.eventparser import EventParser, EventNotConcerned
from nio import RoomMessageText

from bot_msg import AlbertMsg
from config import COMMAND_PREFIX, Config
from commands import register_feature, command_registry, only_allowed_user, user_configs
from n8n.client import N8nClient
from n8n.command import N8nCommandHandler


# Client n8n global partagé
n8n_client = None
# Gestionnaire de commandes n8n
n8n_command_handler = None


def init_n8n(config: Config):
    """Initialise le client n8n si nécessaire."""
    global n8n_client, n8n_command_handler
    
    if not config.n8n_enabled:
        return False
        
    if n8n_client is None and config.n8n_base_url and config.n8n_auth_token:
        n8n_client = N8nClient(config.n8n_base_url, config.n8n_auth_token)
        n8n_command_handler = N8nCommandHandler(n8n_client)
        logger.info("Client n8n initialisé")
        return True
    
    return n8n_client is not None


@register_feature(
    group="n8n",
    onEvent=RoomMessageText,
    command="tools",
    help="Affiche la liste des outils n8n disponibles",
    for_geek=True,
)
@only_allowed_user
async def n8n_tools(ep: EventParser, matrix_client: MatrixClient):
    """Commande pour lister les outils n8n disponibles."""
    config = user_configs[ep.sender]
    
    # Vérifier que n8n est activé
    if not init_n8n(config):
        message = "⚠️ L'intégration n8n n'est pas activée."
        await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")
        return
    
    await matrix_client.room_typing(ep.room.room_id)
    
    # Extraire les arguments de la commande
    command = ep.get_command()
    args = " ".join(command[1:]) if len(command) > 1 else ""
    
    # Appeler le gestionnaire de commandes
    response = await n8n_command_handler.handle_tools_command(args)
    
    await matrix_client.send_markdown_message(ep.room.room_id, response, msgtype="m.notice")


@register_feature(
    group="n8n",
    onEvent=RoomMessageText,
    command="run",
    help="Exécute un outil n8n",
    for_geek=True,
)
@only_allowed_user
async def n8n_run(ep: EventParser, matrix_client: MatrixClient):
    """Commande pour exécuter un outil n8n."""
    config = user_configs[ep.sender]
    
    # Vérifier que n8n est activé
    if not init_n8n(config):
        message = "⚠️ L'intégration n8n n'est pas activée."
        await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")
        return
    
    await matrix_client.room_typing(ep.room.room_id)
    
    # Extraire les arguments de la commande
    command = ep.get_command()
    args = " ".join(command[1:]) if len(command) > 1 else ""
    
    if not args:
        help_text = await n8n_command_handler.get_tools_help()
        await matrix_client.send_markdown_message(ep.room.room_id, help_text, msgtype="m.notice")
        return
    
    # Appeler le gestionnaire de commandes
    response = await n8n_command_handler.handle_run_command(args)
    
    await matrix_client.send_markdown_message(ep.room.room_id, response, msgtype="m.notice")


@register_feature(
    group="n8n",
    onEvent=RoomMessageText,
    help=None,
)
@only_allowed_user
async def n8n_detect_tool_request(ep: EventParser, matrix_client: MatrixClient):
    """Détection contextuelle des intentions d'utilisation d'outil."""
    config = user_configs[ep.sender]
    
    ep.do_not_accept_own_message()  # éviter les boucles infinies
    ep.only_on_direct_message()     # uniquement en salon direct
    
    # Si c'est une commande, on ne fait rien
    if ep.is_command(COMMAND_PREFIX):
        raise EventNotConcerned
    
    # Vérifier que n8n est activé
    if not init_n8n(config):
        return
    
    # Extraire le texte du message
    body = ep.event.body.strip()
    
    # Détecter les intentions d'utilisation d'outil
    tool_detection = await n8n_command_handler.detect_tool_request(body)
    
    if tool_detection and tool_detection.get("detected"):
        tools_list = "\n".join([
            f"- **{t.get('name')}**: {t.get('description')}" 
            for t in tool_detection.get("tools", [])[:3]
        ])
        
        response = (
            f"Il semble que vous vouliez utiliser un outil de la catégorie "
            f"**{tool_detection.get('category')}**.\n\n"
            f"Voici quelques outils disponibles:\n{tools_list}\n\n"
            f"Pour utiliser un outil, tapez `{COMMAND_PREFIX}run <nom_outil> [paramètres]`"
        )
        
        await matrix_client.send_markdown_message(ep.room.room_id, response, msgtype="m.notice")


# Activer les commandes n8n
n8n_features = command_registry.activate_and_retrieve_group("n8n")
logger.info(f"Commandes n8n activées: {len(n8n_features)} commandes")
for feature in n8n_features:
    cmd = feature.get("commands", ["(sans commande)"])[0]
    logger.info(f"  - {cmd}: {feature.get('help', 'Pas de description')}") 