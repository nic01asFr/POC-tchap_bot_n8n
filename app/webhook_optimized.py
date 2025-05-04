"""
Version optimisée du serveur webhook pour éviter les problèmes de taille de payload avec n8n.
"""
import os
import logging
import asyncio
import json
import aiohttp
import threading
import dotenv
import markdown
from aiohttp import web
from urllib.parse import urlencode
from typing import Dict, Any, List, Optional, Tuple, Union
import time
import traceback
import hashlib

# Charger les variables d'environnement du fichier .env
dotenv.load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# Configuration des logs
log_level = int(os.environ.get("LOG_LEVEL", "10"))
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler()  # Assure l'affichage sur la console
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(log_level)  # S'assurer que ce logger spécifique utilise bien le niveau configuré

# Configuration du webhook
WEBHOOK_HOST = os.environ.get("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", 8090))
WEBHOOK_ENDPOINT = os.environ.get("WEBHOOK_ENDPOINT", "/webhook")
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")

# Configuration des webhooks sortants (Tchap → n8n)
GLOBAL_WEBHOOK_URL = os.environ.get("GLOBAL_WEBHOOK_URL", "")
GLOBAL_WEBHOOK_METHOD = os.environ.get("GLOBAL_WEBHOOK_METHOD", "POST")  # Utiliser POST par défaut au lieu de GET
GLOBAL_WEBHOOK_AUTO_FORWARD = os.environ.get("GLOBAL_WEBHOOK_AUTO_FORWARD", "True").lower() == "true"

# Configuration des workflows disponibles pour l'agent
try:
    AVAILABLE_WORKFLOWS = json.loads(os.environ.get("AVAILABLE_WORKFLOWS", "{}"))
    logger.info(f"Workflows disponibles configurés: {len(AVAILABLE_WORKFLOWS)}")
except json.JSONDecodeError:
    logger.error("Erreur dans le format JSON de AVAILABLE_WORKFLOWS, utilisation d'un dictionnaire vide")
    AVAILABLE_WORKFLOWS = {}

# Configuration de l'optimisation des webhooks
WEBHOOK_SIMPLIFY_PAYLOAD = os.environ.get("WEBHOOK_SIMPLIFY_PAYLOAD", "True").lower() == "true"
WEBHOOK_MAX_MESSAGE_LENGTH = int(os.environ.get("WEBHOOK_MAX_MESSAGE_LENGTH", "1000"))
WEBHOOK_FILTER_METADATA = os.environ.get("WEBHOOK_FILTER_METADATA", "True").lower() == "true"

# Configuration des webhooks par salon
try:
    WEBHOOK_ROOM_CONFIG = json.loads(os.environ.get("WEBHOOK_ROOM_CONFIG", "{}"))
except json.JSONDecodeError:
    logger.error("Erreur dans le format JSON de WEBHOOK_ROOM_CONFIG, utilisation d'un dictionnaire vide")
    WEBHOOK_ROOM_CONFIG = {}

# Configuration des webhooks entrants (n8n → Tchap)
try:
    WEBHOOK_INCOMING_ROOMS_CONFIG = json.loads(os.environ.get("WEBHOOK_INCOMING_ROOMS_CONFIG", "{}"))
except json.JSONDecodeError:
    logger.error("Erreur dans le format JSON de WEBHOOK_INCOMING_ROOMS_CONFIG, utilisation d'un dictionnaire vide")
    WEBHOOK_INCOMING_ROOMS_CONFIG = {}

# Configuration pour l'accès à l'API Matrix
MATRIX_HOMESERVER = os.environ.get("MATRIX_HOMESERVER", "")
MATRIX_USERNAME = os.environ.get("MATRIX_BOT_USERNAME", "")
MATRIX_PASSWORD = os.environ.get("MATRIX_BOT_PASSWORD", "")

# Log des variables Matrix (sans le mot de passe)
logger.info(f"Configuration Matrix - Serveur: {MATRIX_HOMESERVER}")
logger.info(f"Configuration Matrix - Utilisateur: {MATRIX_USERNAME}")
logger.info(f"Configuration Matrix - Mot de passe défini: {'Oui' if MATRIX_PASSWORD else 'Non'}")

# Nouvelles options pour l'enrichissement des données
MATRIX_API_ENABLED = os.environ.get("MATRIX_API_ENABLED", "True").lower() == "true"
STORE_ACCESS_TOKEN = os.environ.get("STORE_ACCESS_TOKEN", "True").lower() == "true"

# Variable globale pour stocker le token d'accès Matrix
global_access_token = None

# Variables pour la gestion des rooms
WEBHOOK_ROOM_IDS = []
WEBHOOK_ROOM_MAP = {}
WEBHOOK_INCOMING_ROOMS_CONFIG = {}

# Variables pour Matrix
matrix_access_token = None
matrix_username = None  # Variable pour stocker le nom d'utilisateur au format normalisé
last_sync_token = None

# Variable pour le transfert automatique
FORWARD_AUTOMATICALLY = os.environ.get("FORWARD_AUTOMATICALLY", "true").lower() == "true"

# Variables pour le stockage d'état
processed_events = set()  # Pour stocker les événements déjà traités
processed_message_hashes = set()  # Pour stocker les hashes des messages déjà traités

def is_room_configured(room_id):
    """Vérifie si une salle est configurée pour le forwarding des messages"""
    if not room_id:
        return False
        
    # Vérifier si la salle est dans la configuration des webhooks
    if room_id in WEBHOOK_ROOM_CONFIG:
        return True
        
    # Vérifier si un webhook global est configuré et si le transfert automatique est activé
    if GLOBAL_WEBHOOK_URL and GLOBAL_WEBHOOK_AUTO_FORWARD:
        return True
        
    return False

async def send_message_to_matrix(room_id, message_text, reply_to=None, thread_root=None, format_type=None):
    """
    Envoie un message à un salon Matrix/Tchap
    
    Args:
        room_id: ID du salon Matrix
        message_text: Texte du message à envoyer
        reply_to: ID de l'événement auquel répondre
        thread_root: ID de l'événement racine du fil de discussion
        format_type: Format du message (None ou "markdown")
    
    Returns:
        ID de l'événement créé ou None si échec
    """
    logger.info(f"Envoi d'un message à Matrix dans le salon {room_id}")
    
    if not MATRIX_HOMESERVER or not MATRIX_USERNAME or not MATRIX_PASSWORD:
        logger.warning("Configuration Matrix incomplète, impossible d'envoyer le message")
        return None
    
    try:
        async with aiohttp.ClientSession() as session:
            # 1. S'authentifier et obtenir un token
            login_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/login"
            login_data = {
                "type": "m.login.password",
                "user": MATRIX_USERNAME,
                "password": MATRIX_PASSWORD
            }
            
            logger.info(f"Tentative de connexion à {MATRIX_HOMESERVER}")
            async with session.post(login_url, json=login_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Échec de connexion à Matrix: {response.status} - {error_text}")
                    return None
                
                login_response = await response.json()
                access_token = login_response.get("access_token")
                if not access_token:
                    logger.error("Pas de token d'accès dans la réponse Matrix")
                    return None
                
                logger.info("Connexion à Matrix réussie")
                
                # 2. Envoyer le message au salon
                message_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/rooms/{room_id}/send/m.room.message"
                headers = {"Authorization": f"Bearer {access_token}"}
                
                # Préparer le contenu du message selon le format demandé
                if format_type == "markdown":
                    html_content = markdown.markdown(message_text, extensions=["fenced_code", "nl2br"])
                    
                    message_data = {
                        "msgtype": "m.text",
                        "body": message_text,
                        "format": "org.matrix.custom.html",
                        "formatted_body": html_content
                    }
                else:
                    message_data = {
                        "msgtype": "m.text",
                        "body": message_text
                    }
                
                # Ajouter les relations si présentes
                if reply_to or thread_root:
                    message_data["m.relates_to"] = {}
                    
                    if reply_to:
                        message_data["m.relates_to"]["m.in_reply_to"] = {"event_id": reply_to}
                    
                    if thread_root:
                        message_data["m.relates_to"]["rel_type"] = "m.thread"
                        message_data["m.relates_to"]["event_id"] = thread_root
                        
                        if reply_to and thread_root != reply_to:
                            message_data["m.relates_to"]["is_falling_back"] = True
                
                async with session.post(message_url, headers=headers, json=message_data) as msg_response:
                    if msg_response.status == 200:
                        response_data = await msg_response.json()
                        event_id = response_data.get("event_id")
                        logger.info(f"Message envoyé avec succès dans le salon {room_id}, event_id: {event_id}")
                        return event_id
                    else:
                        error_text = await msg_response.text()
                        logger.error(f"Échec d'envoi du message: {msg_response.status} - {error_text}")
                        return None
    
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du message à Matrix: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
        return None

def filter_webhook_data(data):
    """
    Filtre les données avant de les envoyer à n8n pour réduire la taille.
    Cette fonction permet d'optimiser les données transmises au webhook n8n.
    """
    # Vérifier si on a déjà traité ce message (déduplication)
    event_id = data.get("event_id", "")
    if event_id:
        # Limiter le nombre de tentatives d'envoi par message
        if hasattr(filter_webhook_data, "processed_events") and event_id in filter_webhook_data.processed_events:
            filter_webhook_data.processed_events[event_id] += 1
            if filter_webhook_data.processed_events[event_id] > 3:  # Maximum 3 tentatives
                logger.warning(f"Message {event_id} déjà traité 3 fois, abandon pour éviter une boucle")
                return None
            logger.info(f"Tentative {filter_webhook_data.processed_events[event_id]} pour le message {event_id}")
        else:
            if not hasattr(filter_webhook_data, "processed_events"):
                filter_webhook_data.processed_events = {}
            filter_webhook_data.processed_events[event_id] = 1
    
    if not WEBHOOK_SIMPLIFY_PAYLOAD:
        # Si la simplification est désactivée, renvoyer toutes les données
        return data
    
    logger.info("Filtering webhook data before sending to n8n")
    
    # Vérifier si l'URL cible concerne un agent IA
    target_url = GLOBAL_WEBHOOK_URL
    room_id = data.get("room_id", "")
    if room_id and room_id in WEBHOOK_ROOM_CONFIG:
        config = WEBHOOK_ROOM_CONFIG[room_id]
        if isinstance(config, dict):
            target_url = config.get("url", "")
        else:
            target_url = config
    
    # Si l'URL contient 'matrix_webhook' ou 'tool_agent', c'est probablement pour un agent IA
    is_agent_webhook = False
    if target_url and ("matrix_webhook" in target_url or "tool_agent" in target_url):
        is_agent_webhook = True
        logger.info("Détection d'un endpoint pour agent IA, préparation des données pour usage direct")
        
        # Récupérer le message (le plus important pour l'agent)
        message_text = data.get("message", "")
        
        # Générer un sessionId basé sur room_id et sender
        sessionId = f"{data.get('room_id', '')}{data.get('sender', '')}"
        
        filtered_data = {
            # Champs prioritaires pour l'agent IA
            "chatInput": message_text,  # Juste le message, pas un objet imbriqué
            "sessionId": sessionId,  # SessionId placé à la racine pour l'accès via $json.sessionId
            "message": message_text,
            "room_id": data.get("room_id", ""),
            "sender": data.get("sender", ""),
            "event_id": data.get("event_id", ""),
            "original_event_id": data.get("original_event_id", data.get("event_id", "")),
            
            # Champs de base
            "event": data.get("event", "m.room.message"),
            "message_type": data.get("message_type", "m.text"),
            
            # Contexte enrichi
            "room_name": data.get("room_name", ""),
            "is_direct_chat": data.get("is_direct_chat", False),
            "is_threaded": data.get("is_threaded", False),
            "sender_display_name": data.get("sender_display_name", ""),
            "parent_message": data.get("parent_message", ""),
            "timestamp": data.get("timestamp", ""),
            
            # Relations
            "reply_to": data.get("reply_to", ""),
            "thread_root": data.get("thread_root", "")
        }
        
        # Ajouter la liste des workflows disponibles (important pour l'agent)
        if "available_workflows" in data:
            filtered_data["available_workflows"] = data["available_workflows"]
        else:
            filtered_data["available_workflows"] = AVAILABLE_WORKFLOWS
        
        # Ajouter toute donnée supplémentaire qui pourrait être utile
        for key, value in data.items():
            if key not in filtered_data and value is not None:
                filtered_data[key] = value
                
        # Journaliser la préparation des données
        logger.info("Données formatées pour usage direct par l'agent IA")
        return filtered_data
    
    # Sinon, application du filtre standard
    filtered_data = {
        "event": data.get("event", "message"),
        "room_id": data.get("room_id", ""),
        "sender": data.get("sender", ""),
        "message": "",
        "event_id": data.get("event_id", ""),  # Ajouter event_id explicitement
        "original_event_id": data.get("original_event_id", data.get("event_id", "")),  # Conserver l'ID de l'événement original
    }
    
    # Extraire et tronquer le message si nécessaire
    message = data.get("message", "")
    if message and len(message) > WEBHOOK_MAX_MESSAGE_LENGTH:
        filtered_data["message"] = message[:WEBHOOK_MAX_MESSAGE_LENGTH] + "... (message tronqué)"
        logger.info(f"Message tronqué de {len(message)} à {WEBHOOK_MAX_MESSAGE_LENGTH} caractères")
    else:
        filtered_data["message"] = message
    
    # Ajouter le champ chatInput pour compatibilité avec n8n
    filtered_data["chatInput"] = filtered_data.get("message", "")
    
    # Ajouter un sessionId pour compatibilité avec l'agent
    if "room_id" in filtered_data and "sender" in filtered_data:
        filtered_data["sessionId"] = f"{filtered_data['room_id']}{filtered_data['sender']}"
        
    # Si on veut conserver certaines métadonnées utiles
    if not WEBHOOK_FILTER_METADATA:
        filtered_data["timestamp"] = data.get("timestamp")
        # event_id est déjà ajouté plus haut
    
    # Journaliser la réduction de taille
    original_size = len(json.dumps(data))
    filtered_size = len(json.dumps(filtered_data))
    reduction = (1 - filtered_size / original_size) * 100 if original_size > 0 else 0
    
    logger.info(f"Taille des données réduite de {original_size} à {filtered_size} octets ({reduction:.1f}%)")
    
    return filtered_data

async def send_webhook(url, data, method="POST"):
    """
    Envoie les données webhooks à n8n en utilisant notre filtre pour réduire la taille.
    Par défaut, utilise la méthode POST pour garantir que tous les paramètres sont correctement transmis.
    """
    # Éviter les duplications d'envoi
    event_id = data.get("event_id", "")
    if event_id:
        # Utiliser un attribut statique pour suivre les tentatives d'envoi
        if not hasattr(send_webhook, "sent_events"):
            send_webhook.sent_events = {}
            
        # Vérifier si on a déjà envoyé cet événement à cette URL
        event_url_key = f"{event_id}:{url}"
        if event_url_key in send_webhook.sent_events:
            send_webhook.sent_events[event_url_key] += 1
            # Limiter à 2 tentatives par URL (pour permettre les réessais en cas d'échec)
            if send_webhook.sent_events[event_url_key] > 2:
                logger.warning(f"Message {event_id} déjà envoyé 2 fois à {url}, abandon pour éviter une boucle")
                return False
            logger.info(f"Nouvelle tentative ({send_webhook.sent_events[event_url_key]}) d'envoi de {event_id} à {url}")
        else:
            send_webhook.sent_events[event_url_key] = 1
            
    logger.info(f"Préparation envoi webhook ({method}) vers {url}")
    
    # Détecter le type de webhook pour adapter le format
    is_agent_webhook = False
    if "matrix_webhook" in url:
        logger.info("Endpoint pour agent IA (matrix_webhook) détecté, préparation pour transmission directe")
        method = "GET"  # Pour les agents IA, toujours utiliser GET car ils attendent des query params
        is_agent_webhook = True
    elif "tool_agent" in url:
        logger.info("Endpoint pour agent IA (tool_agent) détecté, préparation pour transmission directe")
        method = "GET"  # Pour les agents IA, toujours utiliser GET car ils attendent des query params
        is_agent_webhook = True
    
    # Appliquer notre filtre pour réduire la taille des données
    # Le filtre détectera automatiquement s'il s'agit d'un agent IA et adaptera le format
    filtered_data = filter_webhook_data(data)
    
    # Vérifier que les informations essentielles sont bien présentes
    logger.debug(f"Données après filtrage: {json.dumps(filtered_data, indent=2)}")
    
    # S'assurer que event_id est présent pour le debug
    if "event_id" in data and "event_id" not in filtered_data and "messageContext" not in filtered_data:
        logger.warning(f"ATTENTION: event_id est présent dans les données d'origine mais absent des données filtrées!")
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None)) as session:
            if method.upper() == "GET":
                # Pour GET, on convertit les données en paramètres de requête
                
                # Structure optimisée pour l'agent IA n8n
                if is_agent_webhook:
                    # Format simple, tout est transmis directement à la racine
                    # L'agent IA attend chatInput et sessionId comme arguments principaux
                    params = {
                        "chatInput": filtered_data.get("chatInput", filtered_data.get("message", "")),
                        "sessionId": filtered_data.get("sessionId", ""),
                        "room_id": filtered_data.get("room_id", ""),
                        "event_id": filtered_data.get("event_id", ""),
                        "sender": filtered_data.get("sender", ""),
                        "original_event_id": filtered_data.get("original_event_id", ""),
                        "format": "markdown"  # Toujours définir markdown comme format par défaut
                    }
                    
                    # Ajouter les workflows disponibles pour l'agent tool_agent
                    if "tool_agent" in url and "available_workflows" in filtered_data:
                        params["available_workflows"] = json.dumps(filtered_data["available_workflows"])
                    
                    # Ajouter toutes les autres données comme paramètres simples
                    for key, value in filtered_data.items():
                        if key not in params and value is not None:
                            params[key] = str(value) if not isinstance(value, (dict, list)) else json.dumps(value)
                    
                    logger.info("Format simplifié créé pour compatibilité avec l'agent IA et ses outils")
                else:
                    # Comportement normal pour les autres webhooks
                    params = {}
                    for key, value in filtered_data.items():
                        if isinstance(value, (dict, list)):
                            params[key] = json.dumps(value)
                        else:
                            params[key] = str(value)
                
                query_string = urlencode(params)
                full_url = f"{url}?{query_string}"
                
                logger.info(f"Envoi webhook GET vers {url}")
                logger.debug(f"Paramètres envoyés: {json.dumps(params, indent=2)}")
                logger.debug(f"URL complète: {full_url[:500]}{'...' if len(full_url) > 500 else ''}")
                
                # Limiter la taille de l'URL à 2000 caractères max
                if len(full_url) > 2000:
                    logger.warning(f"URL trop longue ({len(full_url)} caractères), passage en POST")
                    # Si l'URL est trop longue, utiliser POST à la place
                    return await send_webhook(url, data, "POST")
                
                try:
                    logger.debug("Envoi de la requête GET...")
                    start_time = asyncio.get_event_loop().time()
                    
                    async with session.get(full_url) as response:
                        elapsed_time = asyncio.get_event_loop().time() - start_time
                        logger.info(f"Réponse reçue en {elapsed_time:.2f}s avec code: {response.status}")
                        
                        success = 200 <= response.status < 300
                        if success:
                            logger.info(f"Webhook envoyé avec succès: {response.status}")
                            try:
                                response_text = await response.text()
                                logger.debug(f"Réponse du serveur: {response_text[:500]}{'...' if len(response_text) > 500 else ''}")
                                
                                # Traiter la réponse n8n qui contient un message à envoyer au salon
                                try:
                                    response_json = json.loads(response_text)
                                    
                                    # Traiter la réponse
                                    if isinstance(response_json, dict):
                                        room_id = response_json.get("room_id")
                                        message = response_json.get("output") or response_json.get("message")
                                        format_type = response_json.get("format", "markdown").lower()  # Markdown par défaut
                                        reply_to = response_json.get("reply_to")
                                        thread_root = response_json.get("thread_root")
                                    else:
                                        logger.warning(f"Format de réponse non reconnu: {type(response_json)}")
                                        return success
                                    
                                    # Si room_id n'est pas fourni dans la réponse, utiliser celui des données d'origine
                                    if not room_id and "room_id" in data:
                                        room_id = data.get("room_id")
                                        logger.info(f"Utilisation du room_id des données d'origine: {room_id}")
                                    
                                    # Vérifier si on a les informations minimales pour envoyer un message
                                    if not message:
                                        logger.warning("Information insuffisante pour envoyer un message: manque message")
                                        return success
                                    
                                    if not room_id:
                                        logger.warning("Information insuffisante pour envoyer un message: manque room_id")
                                        return success
                                    
                                    # Utiliser l'ID du message original comme reply_to par défaut si pas spécifié
                                    if not reply_to:
                                        # Chercher d'abord dans la demande originale
                                        original_event_id = filtered_data.get("original_event_id")
                                        if original_event_id:
                                            reply_to = original_event_id
                                            logger.info(f"Utilisation automatique de l'ID de l'événement original comme reply_to: {reply_to}")
                                        elif "event_id" in filtered_data:
                                            reply_to = filtered_data["event_id"]
                                    
                                    # Conserver le fil de discussion s'il existe
                                    if not thread_root and "thread_root" in filtered_data:
                                        thread_root = filtered_data["thread_root"]
                                    
                                    logger.info(f"Réponse du n8n détectée, envoi du message au salon {room_id}")
                                    if format_type:
                                        logger.info(f"Format détecté dans la réponse: {format_type}")
                                    
                                    # Envoyer le message au salon Matrix
                                    event_id = await send_message_to_matrix(room_id, message, reply_to, thread_root, format_type)
                                    if event_id:
                                        logger.info(f"Message envoyé avec ID: {event_id}")
                                except json.JSONDecodeError:
                                    logger.debug("La réponse n'est pas au format JSON")
                                except Exception as e:
                                    logger.error(f"Erreur lors du traitement de la réponse n8n: {str(e)}")
                            except Exception as e:
                                logger.warning(f"Impossible de lire la réponse: {str(e)}")
                        else:
                            logger.error(f"Échec d'envoi webhook: {response.status}")
                            text = await response.text()
                            logger.error(f"Réponse: {text[:500]}{'...' if len(text) > 500 else ''}")
                        return success
                except aiohttp.ClientError as e:
                    logger.error(f"Erreur client lors de l'envoi de la requête GET: {str(e)}")
                    return False
            else:
                # Pour POST, on envoie les données en JSON dans le corps
                logger.info(f"Envoi webhook POST vers {url}")
                logger.debug(f"Données JSON envoyées: {json.dumps(filtered_data, indent=2)}")
                
                try:
                    logger.debug("Envoi de la requête POST...")
                    start_time = asyncio.get_event_loop().time()
                    
                    async with session.post(url, json=filtered_data) as response:
                        elapsed_time = asyncio.get_event_loop().time() - start_time
                        logger.info(f"Réponse reçue en {elapsed_time:.2f}s avec code: {response.status}")
                        
                        success = 200 <= response.status < 300
                        if success:
                            logger.info(f"Webhook envoyé avec succès: {response.status}")
                            try:
                                response_text = await response.text()
                                logger.debug(f"Réponse du serveur: {response_text[:500]}{'...' if len(response_text) > 500 else ''}")
                                
                                # Traiter la réponse n8n qui contient un message à envoyer au salon
                                try:
                                    response_json = json.loads(response_text)
                                    
                                    # Traiter la réponse
                                    if isinstance(response_json, dict):
                                        room_id = response_json.get("room_id")
                                        message = response_json.get("output") or response_json.get("message")
                                        format_type = response_json.get("format", "markdown").lower()  # Markdown par défaut
                                        reply_to = response_json.get("reply_to")
                                        thread_root = response_json.get("thread_root")
                                    else:
                                        logger.warning(f"Format de réponse non reconnu: {type(response_json)}")
                                        return success
                                    
                                    # Si room_id n'est pas fourni dans la réponse, utiliser celui des données d'origine
                                    if not room_id and "room_id" in data:
                                        room_id = data.get("room_id")
                                        logger.info(f"Utilisation du room_id des données d'origine: {room_id}")
                                    
                                    # Vérifier si on a les informations minimales pour envoyer un message
                                    if not message:
                                        logger.warning("Information insuffisante pour envoyer un message: manque message")
                                        return success
                                    
                                    if not room_id:
                                        logger.warning("Information insuffisante pour envoyer un message: manque room_id")
                                        return success
                                    
                                    # Utiliser l'ID du message original comme reply_to par défaut si pas spécifié
                                    if not reply_to:
                                        # Chercher d'abord dans la demande originale
                                        original_event_id = filtered_data.get("original_event_id")
                                        if original_event_id:
                                            reply_to = original_event_id
                                            logger.info(f"Utilisation automatique de l'ID de l'événement original comme reply_to: {reply_to}")
                                        elif "event_id" in filtered_data:
                                            reply_to = filtered_data["event_id"]
                                    
                                    # Conserver le fil de discussion s'il existe
                                    if not thread_root and "thread_root" in filtered_data:
                                        thread_root = filtered_data["thread_root"]
                                    
                                    logger.info(f"Réponse du n8n détectée, envoi du message au salon {room_id}")
                                    if format_type:
                                        logger.info(f"Format détecté dans la réponse: {format_type}")
                                    
                                    # Envoyer le message au salon Matrix
                                    event_id = await send_message_to_matrix(room_id, message, reply_to, thread_root, format_type)
                                    if event_id:
                                        logger.info(f"Message envoyé avec ID: {event_id}")
                                except json.JSONDecodeError:
                                    logger.debug("La réponse n'est pas au format JSON")
                                except Exception as e:
                                    logger.error(f"Erreur lors du traitement de la réponse n8n: {str(e)}")
                            except Exception as e:
                                logger.warning(f"Impossible de lire la réponse: {str(e)}")
                        else:
                            logger.error(f"Échec d'envoi webhook: {response.status}")
                            text = await response.text()
                            logger.error(f"Réponse: {text[:500]}{'...' if len(text) > 500 else ''}")
                        return success
                except aiohttp.ClientError as e:
                    logger.error(f"Erreur client lors de l'envoi de la requête POST: {str(e)}")
                    return False
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du webhook: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
        return False

async def handle_matrix_event(request):
    """Gère les événements provenant de Matrix"""
    try:
        # Récupérer les données JSON
        data = await request.json()
        
        # Débogage des événements entrants
        event_type = data.get("type", "unknown")
        sender = data.get("sender", "unknown")
        event_id = data.get("event_id", "unknown")
        room_id = data.get("room_id", "unknown")
        
        logger.debug(f"Événement Matrix reçu - type: {event_type}, sender: {sender}, room: {room_id}, event_id: {event_id}")
        
        # Si ce n'est pas un message de salle, ignorer
        if event_type != "m.room.message":
            logger.debug(f"Événement ignoré (type non géré): {event_type}")
            return web.json_response({"status": "ignored", "reason": "not a room message"})
        
        # Vérifier si l'ID de la salle est configuré pour recevoir des messages
        if not is_room_configured(room_id):
            logger.debug(f"Message ignoré: salle {room_id} non configurée pour les webhooks")
            return web.json_response({"status": "ignored", "reason": "room not configured"})
        
        # IMPORTANT: Vérifier si c'est un message du bot lui-même
        # Si le sender est le bot lui-même, ne pas traiter pour éviter les boucles
        expected_bot_id = f"@{MATRIX_USERNAME}:{MATRIX_HOMESERVER.split('//')[1]}"
        if sender == expected_bot_id:
            logger.info(f"Message envoyé par le bot lui-même ({sender}), ignoré pour éviter une boucle.")
            return web.json_response({"status": "ignored", "reason": "sent by bot"})
        
        # Vérifier si l'event_id a déjà été traité
        if event_id in processed_events:
            logger.info(f"Événement déjà traité (event_id: {event_id}), ignoré")
            return web.json_response({"status": "ignored", "reason": "duplicate event"})
        
        # Ajouter l'event_id aux événements traités
        processed_events.add(event_id)
        
        # Limiter la taille du set pour éviter une fuite mémoire
        if len(processed_events) > 1000:
            # Garder seulement les 500 plus récents
            events_list = list(processed_events)
            processed_events.clear()
            processed_events.update(set(events_list[-500:]))
            logger.debug(f"Nettoyage des événements traités, {len(events_list) - 500} supprimés")
        
        # Extraire le contenu du message
        content = data.get("content", {})
        message_type = content.get("msgtype", "")
        body = content.get("body", "")
        
        # Vérifier si le contenu du message a déjà été traité (détection de boucle par contenu)
        if body:
            # Créer un hash MD5 du contenu du message
            content_hash = hashlib.md5(body.encode('utf-8')).hexdigest()
            
            # Vérifier si le hash existe déjà dans les messages traités
            if content_hash in processed_message_hashes:
                logger.info(f"Contenu du message déjà traité (hash: {content_hash}), ignoré pour éviter une boucle")
                return web.json_response({"status": "ignored", "reason": "duplicate content"})
            
            # Ajouter le hash aux contenus traités
            processed_message_hashes.add(content_hash)
            
            # Limiter la taille du set pour éviter une fuite mémoire
            if len(processed_message_hashes) > 1000:
                # Garder seulement les 500 plus récents
                hashes_list = list(processed_message_hashes)
                processed_message_hashes.clear()
                processed_message_hashes.update(set(hashes_list[-500:]))
                logger.debug(f"Nettoyage des hashes de messages, {len(hashes_list) - 500} supprimés")

        # Ne traiter que les messages texte
        if message_type != "m.text":
            logger.debug(f"Message ignoré (type non géré): {message_type}")
            return web.json_response({"status": "ignored", "reason": "not a text message"})
        
        # Si c'est une commande spéciale, la traiter directement
        if body.strip() == "!webhook":
            room_webhook = get_webhook_url_for_room(room_id)
            response_msg = f"URL du webhook pour cette salle: {room_webhook}"
            await send_message_to_matrix(room_id, response_msg)
            return web.json_response({"status": "success", "command": "webhook"})
        
        # Traitement de la commande !tools si nécessaire
        if body and (body.strip() == "!tools" or body.startswith("!tools ")):
            logger.info(f"Commande !tools détectée, transmission à /webhook/tool_agent")
            
            # Rediriger la requête vers /webhook/tool_agent
            try:
                # Construire l'URL pour l'endpoint tool_agent
                base_url = f"http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/webhook/tool_agent"
                
                # Préparer les données pour la requête à /webhook/tool_agent
                tool_agent_data = data.copy()
                
                logger.info(f"Transmission de la commande !tools à {base_url}")
                
                # Faire une requête interne à /webhook/tool_agent
                async with aiohttp.ClientSession() as session:
                    async with session.post(base_url, json=tool_agent_data) as response:
                        status = response.status
                        content = await response.text()
                        
                        logger.info(f"Réponse de tool_agent: {status}")
                        
                        if status == 200:
                            try:
                                json_response = json.loads(content)
                                output_text = json_response.get('output', '')
                                
                                # Envoyer directement la réponse à Matrix
                                if output_text:
                                    await send_message_to_matrix(room_id, output_text, reply_to=event_id, format_type="markdown")
                                    logger.info(f"Réponse à !tools envoyée avec succès à Matrix")
                                else:
                                    logger.warning(f"Réponse vide de /webhook/tool_agent")
                            except Exception as e:
                                logger.error(f"Erreur lors du traitement de la réponse: {str(e)}")
                        else:
                            logger.error(f"Erreur de /webhook/tool_agent: {status} - {content}")
                
                return web.json_response({"status": "success", "message": "Commande !tools transmise à tool_agent"})
                
            except Exception as e:
                logger.error(f"Erreur lors de la transmission de la commande !tools: {str(e)}")
                logger.error(traceback.format_exc())
                return web.json_response({"error": str(e)}, status=500)
                
        # Valider le token si configuré
        token = data.get("token", "")
        if WEBHOOK_TOKEN and token != WEBHOOK_TOKEN:
            logger.warning(f"Token webhook invalide: {token}")
            return web.json_response({"error": "Token invalide"}, status=401)
        
        # Récupérer l'ID de la salle
        room_id = data.get("room_id", "")
        if not room_id:
            logger.warning("room_id manquant dans les données du webhook")
            return web.json_response({"error": "room_id manquant"}, status=400)
        
        # Récupérer le contenu du message
        if not body:
            logger.warning("Message manquant dans les données du webhook")
            return web.json_response({"error": "Message manquant"}, status=400)
        
        # Autres données optionnelles
        format_type = data.get("format", "markdown")
        reply_to = data.get("reply_to", None)
        
        # Transmettre à n8n si automatiquement configuré
        if GLOBAL_WEBHOOK_AUTO_FORWARD and room_id in WEBHOOK_ROOM_CONFIG:
            await handle_matrix_message(data)
        
        # Envoyer le message à Matrix
        event_id = await send_message_to_matrix(room_id, body, reply_to=reply_to, format_type=format_type)
        if event_id:
            # Ajouter le nouvel event_id à la liste des messages traités
            processed_events.add(event_id)
            logger.info(f"Nouveau message envoyé avec ID {event_id}, ajouté aux messages traités")
        
        return web.json_response({"success": True})
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement du webhook: {str(e)}")
        logger.error(traceback.format_exc())
        return web.json_response({"error": str(e)}, status=500)

async def handle_n8n_webhook(request):
    """Gère les webhooks venant de n8n (webhooks entrants)"""
    try:
        # Extraire le token de la requête
        token = request.query.get("token", "")
        if not token:
            logger.error("Token manquant dans la requête")
            return web.json_response({"success": False, "error": "Token missing"})
        
        # Vérifier si le token est valide
        if token not in WEBHOOK_INCOMING_ROOMS_CONFIG:
            logger.error(f"Token invalide: {token}")
            return web.json_response({"success": False, "error": "Invalid token"})
        
        # Récupérer l'ID de la salle
        room_id = WEBHOOK_INCOMING_ROOMS_CONFIG[token]
        
        # Extraire le message et options de relation
        if request.method == "GET":
            message = request.query.get("message", "")
            reply_to = request.query.get("reply_to", "")
            thread_root = request.query.get("thread_root", "")
            format_type = request.query.get("format", "markdown").lower()
        else:
            data = await request.json()
            message = data.get("message", "")
            reply_to = data.get("reply_to", "")
            thread_root = data.get("thread_root", "")
            format_type = data.get("format", "markdown").lower()
        
        if not message:
            logger.error("Message manquant dans la requête")
            return web.json_response({"success": False, "error": "Message missing"})
        
        logger.info(f"Message de n8n reçu pour la salle {room_id}: {message[:100]}...")
        if reply_to:
            logger.info(f"En réponse au message: {reply_to}")
        if thread_root:
            logger.info(f"Dans le fil de discussion: {thread_root}")
        if format_type == "markdown":
            logger.info("Format Markdown demandé")
            
        # Option directe: utiliser notre fonction d'envoi au lieu d'appeler l'API directement
        event_id = await send_message_to_matrix(room_id, message, reply_to, thread_root, format_type)
        
        if event_id:
            logger.info(f"Message envoyé avec succès, event_id: {event_id}")
            return web.json_response({"success": True, "event_id": event_id})
        else:
            logger.error("Échec de l'envoi du message via send_message_to_matrix")
            return web.json_response({"success": False, "error": "Failed to send message"})
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement du webhook n8n: {str(e)}")
        return web.json_response({"success": False, "error": str(e)})

async def handle_test_endpoint(request):
    """Endpoint de test simple pour vérifier que le serveur fonctionne"""
    logger.info("Requête reçue sur l'endpoint de test")
    return web.json_response({
        "status": "ok",
        "message": "Le serveur webhook fonctionne correctement",
        "timestamp": str(asyncio.get_event_loop().time()),
        "request_info": {
            "method": request.method,
            "path": request.path,
            "query_params": len(request.query),
            "headers": len(request.headers)
        }
    })

async def send_welcome_message_to_rooms():
    """Envoie un message de bienvenue dans les salons configurés et un ping au webhook n8n"""
    logger.info("Envoi d'un message de bienvenue dans les salons configurés")
    
    # Liste des salons configurés
    rooms = []
    for token, room_id in WEBHOOK_INCOMING_ROOMS_CONFIG.items():
        if room_id not in rooms:
            rooms.append(room_id)
    
    # 1. PING VERS LE WEBHOOK n8n
    # -------------------------------
    if GLOBAL_WEBHOOK_URL:
        logger.info(f"Envoi d'un ping au webhook global: {GLOBAL_WEBHOOK_URL}")
        ping_data = {
            "event": "webhook_startup",
            "message": "🤖 Le serveur webhook est en ligne et fonctionnel",
            "timestamp": str(asyncio.get_event_loop().time()),
            "rooms_configured": rooms
        }
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                method = GLOBAL_WEBHOOK_METHOD.upper()
                
                if method == "GET":
                    # Pour GET, convertir les données en paramètres de requête
                    params = {}
                    for key, value in ping_data.items():
                        if isinstance(value, (dict, list)):
                            params[key] = json.dumps(value)
                        else:
                            params[key] = str(value)
                    
                    query_string = urlencode(params)
                    full_url = f"{GLOBAL_WEBHOOK_URL}?{query_string}"
                    
                    logger.info("Envoi du ping via GET")
                    async with session.get(full_url) as response:
                        if 200 <= response.status < 300:
                            logger.info(f"Ping envoyé avec succès: {response.status}")
                        else:
                            logger.error(f"Échec d'envoi du ping: {response.status}")
                            try:
                                error_text = await response.text()
                                logger.error(f"Détails de l'erreur: {error_text[:200]}")
                            except:
                                pass
                else:
                    # Pour POST, envoyer les données en JSON
                    logger.info("Envoi du ping via POST")
                    async with session.post(GLOBAL_WEBHOOK_URL, json=ping_data) as response:
                        if 200 <= response.status < 300:
                            logger.info(f"Ping envoyé avec succès: {response.status}")
                        else:
                            logger.error(f"Échec d'envoi du ping: {response.status}")
                            try:
                                error_text = await response.text()
                                logger.error(f"Détails de l'erreur: {error_text[:200]}")
                            except:
                                pass
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du ping à n8n: {str(e)}")
    else:
        logger.warning("Aucun webhook global configuré pour l'envoi du ping")
    
    # 2. MESSAGE VERS MATRIX
    # -------------------------------
    # Vérifier si on peut se connecter à l'API Matrix
    if not MATRIX_HOMESERVER or not MATRIX_USERNAME or not MATRIX_PASSWORD:
        logger.warning("Impossible d'envoyer un message réel: configuration Matrix incomplète")
        for room_id in rooms:
            logger.info(f"🤖 Message simulé: Je suis en ligne et prêt à vous aider ! (salon: {room_id})")
        return
    
    # Essayer différents formats d'identifiants Matrix
    username_formats = [
        MATRIX_USERNAME,  # Format original (email)
        MATRIX_USERNAME.split('@')[0],  # Partie locale avant @
        f"@{MATRIX_USERNAME}:dev01.tchap.incubateur.net",  # Format MXID complet
        MATRIX_USERNAME.replace('@', '%40')  # Email avec @ encodé
    ]
    
    success = False
    
    for username_format in username_formats:
        logger.info(f"Essai avec le format d'identifiant: {username_format}")
        
        # Se connecter à l'API Matrix
        try:
            async with aiohttp.ClientSession() as session:
                # 1. S'authentifier et obtenir un token
                login_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/login"
                login_data = {
                    "type": "m.login.password",
                    "user": username_format,
                    "password": MATRIX_PASSWORD
                }
                
                logger.info(f"Tentative de connexion à {MATRIX_HOMESERVER}")
                async with session.post(login_url, json=login_data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Échec de connexion à Matrix avec format {username_format}: {response.status} - {error_text}")
                        continue  # Essayer le format suivant
                    
                    login_response = await response.json()
                    access_token = login_response.get("access_token")
                    if not access_token:
                        logger.error("Pas de token d'accès dans la réponse Matrix")
                        continue  # Essayer le format suivant
                    
                    logger.info(f"Connexion à Matrix réussie avec format {username_format}")
                    success = True
                    
                    # 2. Envoyer un message dans chaque salon
                    for room_id in rooms:
                        logger.info(f"Envoi d'un message dans le salon {room_id}")
                        
                        message_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/rooms/{room_id}/send/m.room.message"
                        headers = {"Authorization": f"Bearer {access_token}"}
                        message_data = {
                            "msgtype": "m.notice",
                            "body": "🤖 Je suis en ligne et prêt à vous aider !"
                        }
                        
                        async with session.post(message_url, headers=headers, json=message_data) as msg_response:
                            if msg_response.status == 200:
                                logger.info(f"Message envoyé avec succès dans le salon {room_id}")
                            else:
                                error_text = await msg_response.text()
                                logger.error(f"Échec d'envoi du message: {msg_response.status} - {error_text}")
                    
                    # Si nous avons réussi avec ce format, pas besoin d'essayer les autres
                    break
        
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi des messages de bienvenue avec format {username_format}: {str(e)}")
            import traceback
            logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
    
    if not success:
        logger.error("Échec de connexion avec tous les formats d'identifiants testés")

def determine_webhook_urls(room_id: str) -> List[str]:
    """
    Détermine les URLs des webhooks à appeler pour une salle donnée.
    
    Args:
        room_id: ID de la salle
        
    Returns:
        Liste des URLs des webhooks à appeler
    """
    urls = []
    
    # Vérifier si une configuration spécifique existe pour cette salle
    if room_id in WEBHOOK_ROOM_CONFIG:
        config = WEBHOOK_ROOM_CONFIG[room_id]
        if isinstance(config, dict):
            target_url = config.get("url", "")
        else:
            # Format simplifié (juste l'URL)
            target_url = config
            
        if target_url:
            # Gérer les URLs multiples séparées par des virgules
            if "," in target_url:
                for url in target_url.split(","):
                    clean_url = url.strip()
                    if clean_url and clean_url not in urls:  # Éviter les doublons
                        urls.append(clean_url)
            else:
                clean_url = target_url.strip()
                if clean_url and clean_url not in urls:  # Éviter les doublons
                    urls.append(clean_url)
    
    # Si pas de config spécifique, utiliser le webhook global
    if not urls and GLOBAL_WEBHOOK_URL:
        urls.append(GLOBAL_WEBHOOK_URL)
        
    return urls

async def handle_matrix_message(data: Dict[str, Any]) -> bool:
    """
    Traite un message Matrix et l'envoie au service approprié (MCP si n8n est désactivé)
    
    Args:
        data: Données du message
    
    Returns:
        bool: True si le message a été envoyé avec succès, False sinon
    """
    # Vérifier si N8N est activé 
    n8n_enabled = os.environ.get("N8N_ENABLED", "").lower() == "true"
    mcp_enabled = os.environ.get("MCP_REGISTRY_URL", "") != ""

    # Obtenir l'ID du salon
    room_id = data.get("room_id", "")
    
    # Ignorer les messages du bot lui-même pour éviter les boucles
    sender = data.get("sender", "")
    if matrix_username and sender == matrix_username:
        logger.debug(f"Ignorer message du bot lui-même: {data.get('event_id', '')}")
        return False
    
    # Log pour debug
    logger.debug(f"Réception d'un message de {sender} dans le salon {room_id}")

    # Si n8n est désactivé et MCP est activé, utiliser MCP
    if not n8n_enabled and mcp_enabled:
        logger.debug("n8n est désactivé, utilisation de MCP à la place")
        return await handle_message_via_mcp(data)
    # Si n8n est toujours activé, utiliser le webhook traditionnel
    elif n8n_enabled:
        # Déterminer les URLs de webhook pour ce salon
        webhook_urls = determine_webhook_urls(room_id)
        
        if not webhook_urls:
            # Aucun webhook configuré pour ce salon et pas de webhook global ou transfert auto désactivé
            logger.debug(f"Aucun webhook configuré pour le salon {room_id}")
            return False
            
        # Filtrer les données avant de les envoyer (simplifier le payload)
        filtered_data = filter_webhook_data(data)
        if not filtered_data:
            logger.debug(f"Message filtré, non envoyé: {data.get('event_id', '')}")
            return False
        
        # Envoyer le message à chaque webhook configuré
        success = False
        for url in webhook_urls:
            try:
                logger.info(f"Envoi du message au webhook pour le salon {room_id}")
                result = await send_webhook(url, filtered_data, method=GLOBAL_WEBHOOK_METHOD)
                if result:
                    success = True
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi au webhook {url}: {str(e)}")
        
        return success
    else:
        logger.info("n8n et MCP sont tous deux désactivés, le message ne sera pas transmis")
        return False

async def handle_message_via_mcp(data: Dict[str, Any]) -> bool:
    """
    Envoie un message à MCP au lieu de n8n
    
    Args:
        data: Données du message
    
    Returns:
        bool: True si le message a été envoyé avec succès, False sinon
    """
    try:
        # Configuration MCP
        mcp_registry_url = os.environ.get("MCP_REGISTRY_URL", "")
        mcp_auth_token = os.environ.get("MCP_AUTH_TOKEN", "")
        
        if not mcp_registry_url:
            logger.error("URL du registre MCP non configurée")
            return False
        
        # Préparer les données pour MCP
        mcp_data = {
            "message": data.get("message", "") or data.get("content", {}).get("body", ""),
            "sender": data.get("sender", ""),
            "room_id": data.get("room_id", ""),
            "event_id": data.get("event_id", ""),
            "timestamp": data.get("timestamp", str(time.time())),
            "is_reply": bool(data.get("reply_to", "")),
            "reply_to": data.get("reply_to", ""),
            "is_threaded": data.get("is_threaded", False),
            "thread_root": data.get("thread_root", ""),
            "source": "matrix"
        }
        
        # Tester si le message est une commande, et si oui, la traiter localement 
        # plutôt que d'essayer de l'envoyer à MCP qui n'est peut-être pas configuré
        message = mcp_data.get("message", "")
        if message and message.startswith("!"):
            logger.info(f"Message détecté comme commande: {message[:20]}... - à traiter localement")
            return False  # Laisser le système de commandes intégré traiter cette commande
        
        # Envoyer à MCP
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {mcp_auth_token}" if mcp_auth_token else ""
            }
            
            logger.info(f"Envoi du message à MCP pour le salon {data.get('room_id', '')}")
            
            # Liste des endpoints à essayer
            endpoints = [
                "/webhooks/matrix",
                "/api/webhooks/matrix", 
                "/api/messages",
                "/v1/messages", 
                "/webhooks/messages",
                "/api/v1/matrix"
            ]
            
            # Essayer chaque endpoint
            for endpoint in endpoints:
                url = f"{mcp_registry_url.rstrip('/')}{endpoint}"
                
                try:
                    async with session.post(url, json=mcp_data, headers=headers) as response:
                        if response.status == 200 or response.status == 202:
                            response_data = await response.json()
                            logger.info(f"Message envoyé avec succès à MCP via {endpoint}: {response_data.get('id', '')}")
                            
                            # Mémoriser l'endpoint qui a fonctionné pour optimiser les futurs appels
                            if hasattr(handle_message_via_mcp, "working_endpoint"):
                                handle_message_via_mcp.working_endpoint = endpoint
                            else:
                                setattr(handle_message_via_mcp, "working_endpoint", endpoint)
                                
                            return True
                        elif response.status == 404:
                            error_text = await response.text()
                            logger.warning(f"Endpoint {endpoint} non trouvé: {response.status} - {error_text[:100]}...")
                            # Continuer avec le prochain endpoint
                        else:
                            error_text = await response.text()
                            logger.error(f"Échec d'envoi du message à MCP via {endpoint}: {response.status} - {error_text[:100]}...")
                            # Si on reçoit une erreur autre que 404, c'est probablement une erreur d'authentification
                            # ou une erreur de format, donc inutile d'essayer les autres endpoints
                            if response.status != 404:
                                return False
                except Exception as e:
                    logger.error(f"Erreur lors de la connexion à l'endpoint {endpoint}: {str(e)}")
                    continue
            
            # Si on arrive ici, c'est qu'aucun endpoint n'a fonctionné
            logger.warning("Aucun endpoint MCP n'est disponible. MCP est peut-être mal configuré ou non démarré.")
            logger.info("Le message n'a pas pu être transmis à MCP. Assurez-vous que le service MCP est correctement configuré et actif.")
            return False
                
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du message à MCP: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
        return False

async def process_matrix_sync(events, bot_user_id):
    """Traite les événements de synchronisation Matrix et les transmet à n8n ou Albert"""
    global pending_events
    
    # Parcourir tous les nouveaux événements
    for event in events:
        if event.get("type") != "m.room.message":
            continue
        
        sender = event.get("sender", "")
        if sender == bot_user_id:
            logger.debug(f"Ignorer message du bot lui-même: {event.get('event_id', 'ID inconnu')}")
            continue
        
        room_id = event.get("room_id", "")
        
        # Vérifier si c'est une commande
        content = event.get("content", {})
        body = content.get("body", "")
        if body and body.startswith("!"):
            logger.debug(f"Commande détectée, ne sera pas transmise: {body.split()[0]}")
            continue
        
        # Préparer les données pour la transmission
        data = {
            "event_id": event.get("event_id", ""),
            "sender": sender,
            "room_id": room_id,
            "message": body,
            "content": content,
            "timestamp": event.get("origin_server_ts", int(time.time() * 1000)),
            "event_type": event.get("type", "")
        }
        
        # Ajouter les informations du fil de discussion si disponibles
        if "m.relates_to" in content:
            relates_to = content["m.relates_to"]
            if "m.in_reply_to" in relates_to:
                data["reply_to"] = relates_to["m.in_reply_to"].get("event_id", "")
            if relates_to.get("rel_type") == "m.thread":
                data["is_threaded"] = True
                data["thread_root"] = relates_to.get("event_id", "")
        
        # Enrichir avec les métadonnées Matrix si configuré
        try:
            # Traitement des messages selon la configuration
            n8n_enabled = os.environ.get("N8N_ENABLED", "").lower() == "true"
            
            # Journalisation des informations de messages
            logger.debug(f"Réception d'un message de {sender} dans le salon {room_id}")
            
            # Traitement selon la configuration
            if n8n_enabled:
                logger.debug("Traitement du message via n8n")
                # Transmission à n8n si activé
                success = await handle_matrix_message(data)
                if not success:
                    # Stocker l'événement pour réessayer plus tard
                    pending_events.append(data)
            else:
                logger.debug("Traitement du message via Albert/MCP")
                # Tous les messages sont traités par Albert, qui peut mobiliser MCP si nécessaire
                await handle_message_via_albert(data)
                
        except Exception as e:
            logger.error(f"Erreur lors du traitement du message: {str(e)}")
            import traceback
            logger.error(f"Détails de l'erreur: {traceback.format_exc()}")

async def handle_message_via_albert(data: Dict[str, Any]) -> bool:
    """
    Traite un message via l'API Albert en utilisant le MCP comme intermédiaire d'analyse d'intention.
    
    Le flux est le suivant:
    1. Un message est reçu de Matrix/Tchap
    2. Le MCP analyse l'intention du message
    3. L'API Albert génère une réponse appropriée
    4. La réponse est envoyée via Matrix/Tchap
    
    Args:
        data: Données du message provenant de Matrix/Tchap
    
    Returns:
        bool: True si le message a été traité avec succès, False sinon
    """
    try:
        # Configuration MCP et Albert API
        mcp_registry_url = os.environ.get("MCP_REGISTRY_URL", "")
        mcp_auth_token = os.environ.get("MCP_AUTH_TOKEN", "")
        albert_api_url = os.environ.get("ALBERT_API_URL", "https://albert.api.etalab.gouv.fr")
        albert_api_token = os.environ.get("ALBERT_API_TOKEN", mcp_auth_token)  # Utiliser le même token si ALBERT_API_TOKEN n'est pas défini
        albert_model = os.environ.get("ALBERT_MODEL", "mixtral-8x7b-instruct-v0.1")  # Modèle par défaut
        
        if not mcp_registry_url:
            logger.warning("URL du registre MCP non configurée, impossible d'analyser l'intention des messages")
            return False
        
        # Message à traiter
        message_content = data.get("message", "") or data.get("content", {}).get("body", "")
        sender = data.get("sender", "")
        room_id = data.get("room_id", "")
        event_id = data.get("event_id", "")
        
        logger.info(f"Traitement du message de {sender} dans le salon {room_id}: {message_content[:50]}...")
        
        # 1. Analyse d'intention via MCP
        mcp_intent_data = {
            "message": message_content,
            "sender": sender,
            "room_id": room_id,
            "event_id": event_id,
            "source": "matrix",
            "analyze_only": True  # Indique que nous voulons seulement l'analyse d'intention
        }
        
        mcp_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {mcp_auth_token}" if mcp_auth_token else ""
        }
        
        # Tenter l'analyse d'intention via MCP
        mcp_intent_result = {}
        async with aiohttp.ClientSession() as session:
            # Essayer différents endpoints potentiels pour l'analyse d'intention
            mcp_endpoints = [
                "/api/analyze",
                "/intent/analyze",
                "/api/intent"
            ]
            
            for endpoint in mcp_endpoints:
                intent_url = f"{mcp_registry_url.rstrip('/')}{endpoint}"
                try:
                    async with session.post(intent_url, json=mcp_intent_data, headers=mcp_headers) as response:
                        if response.status == 200:
                            mcp_intent_result = await response.json()
                            logger.info(f"Analyse d'intention réussie via {endpoint}")
                            break
                        elif response.status != 404:  # Si erreur autre que 404, ne pas continuer
                            error_text = await response.text()
                            logger.error(f"Échec d'analyse d'intention via {endpoint}: {response.status} - {error_text[:100]}...")
                            break
                except Exception as e:
                    logger.error(f"Erreur lors de la connexion à {endpoint}: {str(e)}")
            
        # 2. Générer une réponse via l'API Albert
        # Préparer le contexte basé sur l'analyse d'intention de MCP
        requires_tool = mcp_intent_result.get("requires_tool", False)
        tool_name = mcp_intent_result.get("tool_name", "")
        tool_args = mcp_intent_result.get("tool_args", {})
        
        # Si un outil est requis, l'exécuter via MCP
        tool_result = None
        if requires_tool and tool_name:
            logger.info(f"Exécution de l'outil '{tool_name}' requis par l'analyse d'intention")
            mcp_tool_data = {
                "tool_name": tool_name,
                "tool_args": tool_args,
                "message_context": mcp_intent_data
            }
            
            tool_url = f"{mcp_registry_url.rstrip('/')}/api/tools/execute"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(tool_url, json=mcp_tool_data, headers=mcp_headers) as response:
                        if response.status == 200:
                            tool_result = await response.json()
                            logger.info(f"Exécution de l'outil '{tool_name}' réussie")
                        else:
                            error_text = await response.text()
                            logger.error(f"Échec d'exécution de l'outil '{tool_name}': {response.status} - {error_text[:100]}...")
            except Exception as e:
                logger.error(f"Erreur lors de l'exécution de l'outil '{tool_name}': {str(e)}")
        
        # 3. Appel à l'API Albert avec le contexte complet
        # Messages préparés pour l'API Albert
        messages = [
            {"role": "user", "content": message_content}
        ]
        
        # Ajouter les résultats de l'analyse d'intention et/ou de l'outil si disponibles
        context = []
        if mcp_intent_result:
            context.append(f"Analyse d'intention: {json.dumps(mcp_intent_result, ensure_ascii=False)}")
        if tool_result:
            context.append(f"Résultat de l'outil '{tool_name}': {json.dumps(tool_result, ensure_ascii=False)}")
        
        if context:
            messages.insert(0, {
                "role": "system", 
                "content": "Voici le contexte pour t'aider à répondre: " + " ".join(context)
            })
        
        # Préparation de la requête pour l'API Albert
        albert_data = {
            "model": albert_model,  # Champ obligatoire selon l'API
            "messages": messages,
            "stream": False
        }
        
        albert_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {albert_api_token}" if albert_api_token else ""
        }
        
        # Appel à l'API Albert
        async with aiohttp.ClientSession() as session:
            albert_url = f"{albert_api_url}/chat/completions"  # URL correcte sans /v1/
            
            try:
                logger.info(f"Appel à l'API Albert: {albert_url}")
                async with session.post(albert_url, json=albert_data, headers=albert_headers) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        
                        # Extraire la réponse d'Albert
                        assistant_message = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        if assistant_message:
                            # 4. Envoyer la réponse à Matrix/Tchap
                            logger.info(f"Envoi de la réponse d'Albert au salon {room_id}")
                            await send_message_to_matrix(
                                room_id,
                                assistant_message,
                                reply_to=event_id
                            )
                            return True
                        else:
                            logger.error("Réponse vide de l'API Albert")
                            return False
                    else:
                        error_text = await response.text()
                        logger.error(f"Échec de l'appel à l'API Albert: {response.status} - {error_text[:100]}...")
                        
                        # Si l'API Albert échoue avec une erreur 422, essayer avec un autre modèle
                        if response.status == 422:
                            # Essayer avec d'autres modèles disponibles dans Albert
                            logger.info("Tentative avec un autre modèle Albert")
                            for fallback_model in ["mistral-7b-instruct-v0.2", "gpt-3.5-turbo"]:
                                albert_data["model"] = fallback_model
                                try:
                                    async with session.post(albert_url, json=albert_data, headers=albert_headers) as fallback_response:
                                        if fallback_response.status == 200:
                                            fallback_data = await fallback_response.json()
                                            fallback_message = fallback_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                                            
                                            if fallback_message:
                                                logger.info(f"Réponse générée avec succès via le modèle {fallback_model}")
                                                await send_message_to_matrix(
                                                    room_id,
                                                    fallback_message,
                                                    reply_to=event_id
                                                )
                                                return True
                                        else:
                                            fallback_error = await fallback_response.text()
                                            logger.error(f"Échec avec le modèle {fallback_model}: {fallback_response.status} - {fallback_error[:100]}...")
                                except Exception as e:
                                    logger.error(f"Erreur lors de l'appel avec le modèle {fallback_model}: {str(e)}")
                        
                        # Si tous les appels à Albert échouent, envoyer une réponse par défaut
                        default_message = "Je suis désolé, je n'ai pas pu traiter votre demande pour le moment. Notre service est en cours de maintenance. Veuillez réessayer ultérieurement."
                        logger.info(f"Envoi d'une réponse par défaut au salon {room_id}")
                        await send_message_to_matrix(
                            room_id,
                            default_message,
                            reply_to=event_id
                        )
                        return True
            except Exception as e:
                logger.error(f"Erreur lors de l'appel à l'API Albert: {str(e)}")
                import traceback
                logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
                
                # En cas d'erreur, envoyer une réponse par défaut
                default_message = "Je suis désolé, je n'ai pas pu traiter votre demande pour le moment. Notre service est en cours de maintenance. Veuillez réessayer ultérieurement."
                logger.info(f"Envoi d'une réponse par défaut au salon {room_id}")
                await send_message_to_matrix(
                    room_id,
                    default_message,
                    reply_to=event_id
                )
                return True
                
    except Exception as e:
        logger.error(f"Erreur lors du traitement du message via Albert: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
        
        try:
            # En cas d'erreur, envoyer une réponse par défaut
            default_message = "Je suis désolé, je n'ai pas pu traiter votre demande en raison d'une erreur technique. Notre équipe a été notifiée du problème."
            logger.info(f"Envoi d'une réponse par défaut au salon {data.get('room_id', '')}")
            await send_message_to_matrix(
                data.get("room_id", ""),
                default_message,
                reply_to=data.get("event_id", "")
            )
            return True
        except Exception as send_error:
            logger.error(f"Échec de l'envoi du message par défaut: {str(send_error)}")
            return False

async def handle_message_via_mcp_fallback(data: Dict[str, Any]) -> bool:
    """
    Méthode de repli pour traiter un message via MCP si l'API Albert échoue.
    
    Args:
        data: Données du message
    
    Returns:
        bool: True si le message a été traité avec succès, False sinon
    """
    try:
        # Configuration MCP
        mcp_registry_url = os.environ.get("MCP_REGISTRY_URL", "")
        mcp_auth_token = os.environ.get("MCP_AUTH_TOKEN", "")
        
        if not mcp_registry_url:
            logger.error("URL du registre MCP non configurée")
            return False
        
        # Préparer les données pour MCP
        mcp_data = {
            "message": data.get("message", "") or data.get("content", {}).get("body", ""),
            "sender": data.get("sender", ""),
            "room_id": data.get("room_id", ""),
            "event_id": data.get("event_id", ""),
            "timestamp": data.get("timestamp", str(time.time())),
            "is_reply": bool(data.get("reply_to", "")),
            "reply_to": data.get("reply_to", ""),
            "is_threaded": data.get("is_threaded", False),
            "thread_root": data.get("thread_root", ""),
            "source": "matrix"
        }
        
        # Envoyer à MCP
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {mcp_auth_token}" if mcp_auth_token else ""
            }
            
            logger.info(f"Tentative de repli: Envoi du message à MCP pour le salon {data.get('room_id', '')}")
            
            # Liste des endpoints à essayer
            endpoints = [
                "/api/conversation",
                "/api/messages", 
                "/conversation",
                "/webhooks/matrix"
            ]
            
            # Essayer chaque endpoint
            for endpoint in endpoints:
                url = f"{mcp_registry_url.rstrip('/')}{endpoint}"
                
                try:
                    async with session.post(url, json=mcp_data, headers=headers) as response:
                        if response.status == 200 or response.status == 202:
                            response_data = await response.json()
                            logger.info(f"Message traité avec succès par MCP via {endpoint}: {response_data.get('id', '')}")
                            return True
                        elif response.status == 404:
                            logger.warning(f"Endpoint {endpoint} non trouvé: {response.status}")
                            # Continuer avec le prochain endpoint
                        else:
                            error_text = await response.text()
                            logger.error(f"Échec du traitement du message par MCP via {endpoint}: {response.status} - {error_text[:100]}...")
                            if response.status != 404:
                                return False
                except Exception as e:
                    logger.error(f"Erreur lors de la connexion à l'endpoint {endpoint}: {str(e)}")
                    continue
            
            # Si on arrive ici, c'est qu'aucun endpoint n'a fonctionné
            logger.warning("Aucun endpoint MCP n'est disponible pour le repli.")
            return False
                
    except Exception as e:
        logger.error(f"Erreur lors du repli vers MCP: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
        return False

async def setup_matrix_listener():
    """Configure l'écouteur Matrix pour transmettre les messages à n8n"""
    global matrix_access_token, last_sync_token, matrix_username
    
    if not MATRIX_HOMESERVER or not MATRIX_USERNAME or not MATRIX_PASSWORD:
        logger.warning("Configuration Matrix incomplète, l'écouteur ne sera pas activé")
        return False
    
    # Formats d'identifiants possibles
    username_formats = [
        MATRIX_USERNAME,
        f"@{MATRIX_USERNAME}",
        f"@{MATRIX_USERNAME}:{MATRIX_HOMESERVER.split('//')[1]}"
    ]
    
    success = False
    
    # Essayer différents formats d'identifiant
    for username_format in username_formats:
        logger.info(f"Essai avec le format d'identifiant: {username_format}")
        
        # Se connecter à l'API Matrix
        try:
            async with aiohttp.ClientSession() as session:
                # 1. S'authentifier et obtenir un token
                login_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/login"
                login_data = {
                    "type": "m.login.password",
                    "user": username_format,
                    "password": MATRIX_PASSWORD
                }
                
                logger.info(f"Tentative de connexion à {MATRIX_HOMESERVER}")
                async with session.post(login_url, json=login_data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Échec de connexion à Matrix avec format {username_format}: {response.status} - {error_text}")
                        continue  # Essayer le format suivant
                    
                    login_response = await response.json()
                    access_token = login_response.get("access_token")
                    if not access_token:
                        logger.error("Pas de token d'accès dans la réponse Matrix")
                        continue  # Essayer le format suivant
                    
                    logger.info(f"Connexion à Matrix réussie avec format {username_format}")
                    success = True
                    
                    # Stocker le token pour une utilisation ultérieure
                    if STORE_ACCESS_TOKEN:
                        matrix_access_token = access_token
                        logger.info("Token d'accès Matrix enregistré pour l'enrichissement des données")
                    
                    # 2. Initialiser l'écouteur Matrix pour transmettre les messages
                    bot_user_id = login_response.get("user_id")
                    
                    # Stocker l'identifiant utilisateur normalisé
                    matrix_username = bot_user_id
                    logger.info(f"Nom d'utilisateur Matrix normalisé: {matrix_username}")
                    
                    logger.info(f"Connexion à Matrix réussie pour l'écouteur (user_id: {bot_user_id})")
                    
                    # Initialiser tous les salons auxquels le bot est connecté
                    await initialize_all_rooms(access_token)
                    
                    # Configurer l'écouteur de synchronisation Matrix
                    timestamp = time.monotonic()
                    logger.info(f"Timestamp de démarrage: {timestamp}")
                    
                    # Lancer l'écouteur de synchronisation dans un thread séparé
                    sync_task = asyncio.create_task(sync_loop(access_token, bot_user_id))
                    
                    # Stocker la tâche pour éviter qu'elle ne soit annulée lors du garbage collection
                    if not hasattr(setup_matrix_listener, "tasks"):
                        setup_matrix_listener.tasks = []
                    setup_matrix_listener.tasks.append(sync_task)
                    
                    logger.info("Écouteur Matrix configuré et démarré")
                    logger.info("Écouteur Matrix activé pour transmettre les messages à n8n")
                    
                    # Ne pas essayer les autres formats si la connexion a réussi
                    return True
        except Exception as e:
            logger.error(f"Erreur lors de la configuration de l'écouteur Matrix: {str(e)}")
            import traceback
            logger.error(f"Détails de l'erreur pour {username_format}: {traceback.format_exc()}")
            continue  # Essayer le format suivant
    
    if not success:
        logger.error("Tous les formats d'identifiant ont échoué, l'écouteur Matrix ne sera pas activé")
    
    return success

async def initialize_room(room_id, access_token):
    """
    Initialise le bot dans un salon spécifique en récupérant les informations pertinentes
    
    Args:
        room_id: ID du salon Matrix
        access_token: Token d'accès Matrix
    
    Returns:
        dict: Informations sur le salon ou None en cas d'erreur
    """
    logger.info(f"Initialisation du bot dans le salon {room_id}")
    
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Récupérer les informations de base du salon
            room_state_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/rooms/{room_id}/state"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            async with session.get(room_state_url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Échec de récupération de l'état du salon {room_id}: {response.status} - {error_text}")
                    return None
                
                room_state = await response.json()
                
                # 2. Récupérer les membres du salon
                members_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/rooms/{room_id}/joined_members"
                
                async with session.get(members_url, headers=headers) as members_response:
                    if members_response.status != 200:
                        error_text = await members_response.text()
                        logger.error(f"Échec de récupération des membres du salon {room_id}: {members_response.status} - {error_text}")
                        return None
                    
                    members_data = await members_response.json()
                    joined_members = members_data.get("joined", {})
                    
                    # Déterminer si c'est un DM ou un salon de groupe
                    is_direct_message = len(joined_members) == 2
                    
                    # 3. Récupérer le nom du salon
                    room_name = None
                    for event in room_state:
                        if event.get("type") == "m.room.name":
                            room_name = event.get("content", {}).get("name")
                            break
                    
                    # Si pas de nom et DM, utiliser le nom de l'autre utilisateur
                    if not room_name and is_direct_message:
                        # Trouver l'autre utilisateur (pas le bot)
                        bot_id = list(filter(lambda x: x.endswith(MATRIX_USERNAME), joined_members.keys()))
                        other_users = [user_id for user_id in joined_members.keys() if user_id not in bot_id]
                        
                        if other_users:
                            other_user = other_users[0]
                            other_user_data = joined_members.get(other_user, {})
                            room_name = other_user_data.get("display_name", "Utilisateur inconnu")
                    
                    room_info = {
                        "room_id": room_id,
                        "name": room_name or "Salon sans nom",
                        "is_direct_message": is_direct_message,
                        "members": joined_members,
                        "member_count": len(joined_members),
                        "initialized": True,
                        "initialization_time": time.time()
                    }
                    
                    logger.info(f"Salon {room_id} initialisé avec succès: {room_name} - DM: {is_direct_message} - Membres: {len(joined_members)}")
                    
                    # Stocker ces informations pour une utilisation ultérieure
                    global WEBHOOK_ROOM_MAP
                    WEBHOOK_ROOM_MAP[room_id] = room_info
                    
                    return room_info
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation du salon {room_id}: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
        return None

async def initialize_all_rooms(access_token):
    """
    Initialise le bot dans tous les salons auxquels il est connecté
    
    Args:
        access_token: Token d'accès Matrix
    
    Returns:
        int: Nombre de salons initialisés avec succès
    """
    logger.info("Initialisation du bot dans tous les salons")
    
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Récupérer la liste des salons auxquels le bot est connecté
            joined_rooms_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/joined_rooms"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            async with session.get(joined_rooms_url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Échec de récupération des salons: {response.status} - {error_text}")
                    return 0
                
                joined_rooms_data = await response.json()
                joined_rooms = joined_rooms_data.get("joined_rooms", [])
                
                logger.info(f"Le bot est connecté à {len(joined_rooms)} salons")
                
                # 2. Initialiser chaque salon
                initialized_count = 0
                for room_id in joined_rooms:
                    room_info = await initialize_room(room_id, access_token)
                    if room_info:
                        initialized_count += 1
                
                logger.info(f"{initialized_count}/{len(joined_rooms)} salons initialisés avec succès")
                return initialized_count
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation des salons: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
        return 0

# Fonction pour gérer les événements de synchronisation Matrix  
async def sync_loop(access_token, bot_user_id):
    """
    Boucle de synchronisation Matrix pour récupérer les nouveaux messages
    
    Args:
        access_token: Token d'accès Matrix
        bot_user_id: ID utilisateur du bot
    """
    global last_sync_token
    
    try:
        # Initialiser le token de synchronisation s'il n'existe pas
        sync_token = last_sync_token
        
        while True:
            try:
                # URL pour la synchronisation Matrix
                sync_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/sync"
                params = {
                    "timeout": 30000  # 30 secondes
                }
                
                # Ajouter le token de synchronisation si disponible
                if sync_token:
                    params["since"] = sync_token
                    
                # En-têtes avec le token d'authentification
                headers = {"Authorization": f"Bearer {access_token}"}
                
                # Effectuer la requête de synchronisation
                async with aiohttp.ClientSession() as session:
                    async with session.get(sync_url, params=params, headers=headers) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Échec de synchronisation Matrix: {response.status} - {error_text}")
                            await asyncio.sleep(5)  # Attendre avant de réessayer
                            continue
                            
                        json_response = await response.json()
                        
                        # Récupérer le nouveau token de synchronisation
                        if "next_batch" in json_response:
                            sync_token = json_response["next_batch"]
                            last_sync_token = sync_token
                            
                        # Vérifier s'il y a des nouveaux messages
                        if "rooms" in json_response:
                            # Traiter les invitations
                            if "invite" in json_response["rooms"]:
                                await process_invitations(json_response["rooms"]["invite"], access_token, bot_user_id)
                                
                            # Traiter les salons rejoints
                            if "join" in json_response["rooms"]:
                                for room_id, room_data in json_response["rooms"]["join"].items():
                                    # Vérifier s'il y a de nouveaux messages
                                    if "timeline" in room_data and "events" in room_data["timeline"]:
                                        events = room_data["timeline"]["events"]
                                        # Ajouter l'ID de salon à chaque événement
                                        for event in events:
                                            event["room_id"] = room_id
                                        
                                        # Traiter les événements
                                        await process_matrix_sync(events, bot_user_id)
            
            except aiohttp.ClientError as e:
                logger.error(f"Erreur de connexion Matrix: {str(e)}")
                await asyncio.sleep(10)  # Attendre avant de réessayer
                
            except Exception as e:
                logger.error(f"Erreur dans la boucle de synchronisation: {str(e)}")
                import traceback
                logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
                await asyncio.sleep(10)  # Attendre avant de réessayer
                
            # Courte pause entre les requêtes pour éviter de surcharger le serveur
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        logger.info("Boucle de synchronisation annulée")
    except Exception as e:
        logger.error(f"Erreur fatale dans la boucle de synchronisation: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")

async def process_invitations(invite_rooms, access_token, bot_user_id):
    """
    Traite les invitations à des salons Matrix
    
    Args:
        invite_rooms: Dictionnaire des salons avec invitations
        access_token: Token d'accès Matrix
        bot_user_id: ID utilisateur du bot
    """
    for room_id, invite_data in invite_rooms.items():
        logger.info(f"Invitation détectée pour le salon {room_id}")
        
        # Vérifier si l'invitation est pour nous
        events = invite_data.get("invite_state", {}).get("events", [])
        for event in events:
            if event.get("type") == "m.room.member" and event.get("state_key") == bot_user_id:
                sender = event.get("sender", "Unknown")
                logger.info(f"Invitation de {sender} pour le salon {room_id}")
                
                # Accepter l'invitation
                await accept_invitation(room_id, access_token)
                break

async def accept_invitation(room_id, access_token):
    """
    Accepte une invitation à un salon Matrix
    
    Args:
        room_id: ID du salon Matrix
        access_token: Token d'accès Matrix
    """
    try:
        async with aiohttp.ClientSession() as session:
            # URL pour rejoindre un salon
            join_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/rooms/{room_id}/join"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            logger.info(f"Tentative de rejoindre le salon {room_id}")
            async with session.post(join_url, headers=headers, json={}) as response:
                if response.status == 200:
                    logger.info(f"Salon {room_id} rejoint avec succès")
                    
                    # Initialiser le salon après l'avoir rejoint
                    await initialize_room(room_id, access_token)
                    
                    # Envoyer un message de bienvenue
                    welcome_message = "Bonjour ! Je suis Albert, le bot assistant pour Tchap. Utilisez `!aide` pour voir la liste des commandes disponibles."
                    await send_message_to_matrix(room_id, welcome_message, format_type="markdown")
                    
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Échec de l'acceptation de l'invitation pour le salon {room_id}: {response.status} - {error_text}")
                    return False
    except Exception as e:
        logger.error(f"Erreur lors de l'acceptation de l'invitation pour le salon {room_id}: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
        return False

async def start_webhook_server():
    """Démarre le serveur webhook"""
    # Middleware pour logger toutes les requêtes
    @web.middleware
    async def logging_middleware(request, handler):
        """Middleware pour enregistrer toutes les requêtes et gérer les erreurs"""
        logger.info(f"Requête reçue: {request.method} {request.path}")
        try:
            return await handler(request)
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la requête: {str(e)}")
            import traceback
            logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
            raise
            
    # Vérifier si N8N est activé ou si MCP est configuré
    n8n_enabled = os.environ.get("N8N_ENABLED", "").lower() == "true"
    mcp_registry_url = os.environ.get("MCP_REGISTRY_URL", "")
    
    if not n8n_enabled and not mcp_registry_url:
        logger.warning("n8n est désactivé et MCP n'est pas configuré. Les messages ne seront pas transmis.")
    elif not n8n_enabled:
        logger.info("n8n est désactivé. Les messages seront transmis via MCP.")
    else:
        logger.info("n8n est activé. Les messages seront transmis via webhook.")
        
    # Créer l'application web aiohttp
    app = web.Application(middlewares=[logging_middleware])
    
    # Ajouter les routes
    app.add_routes([
        web.post(WEBHOOK_ENDPOINT, handle_matrix_event),
        web.get('/test', handle_test_endpoint),
        web.post('/webhook-test/matrix_webhook', handle_n8n_webhook)
    ])
    
    # Configurer et démarrer l'écouteur Matrix
    if MATRIX_API_ENABLED:
        try:
            success = await setup_matrix_listener()
            if not success:
                logger.warning("Échec de configuration de l'écouteur Matrix, les messages ne seront pas transmis automatiquement")
            else:
                logger.info("Écouteur Matrix configuré avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de la configuration de l'écouteur Matrix: {str(e)}")
            logger.error(traceback.format_exc())
            logger.warning("L'écouteur Matrix n'a pas pu être démarré, mais le serveur webhook continuera de fonctionner")
    
    # Démarrer le serveur web
    logger.info(f"Webhook server started on http://{WEBHOOK_HOST}:{WEBHOOK_PORT}{WEBHOOK_ENDPOINT}")
    logger.info(f"Test endpoint: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/test")
    logger.info(f"Additional webhook endpoint: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/webhook-test/matrix_webhook")
    
    # Retourner l'application pour qu'elle puisse être lancée par run_app
    return app

async def fetch_matrix_event_context(access_token, event_id=None, room_id=None, reply_to=None):
    """
    Récupère des informations contextuelles sur un événement Matrix
    
    Args:
        access_token: Token d'accès Matrix
        event_id: ID de l'événement pour lequel récupérer le contexte
        room_id: ID du salon
        reply_to: ID de l'événement auquel ce message répond
        
    Returns:
        Un dictionnaire contenant les informations contextuelles
    """
    context = {
        "room_name": "",
        "sender_display_name": "",
        "parent_message": "",
        "is_direct_chat": False
    }
    
    # Ne pas essayer de récupérer des informations si le token n'est pas disponible
    if not access_token:
        logger.warning("Impossible de récupérer le contexte - token Matrix manquant")
        return context
        
    try:
        if not MATRIX_HOMESERVER:
            logger.warning("Impossible de récupérer le contexte - homeserver Matrix manquant")
            return context
            
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # 1. Récupérer les informations sur le salon si room_id est disponible
            if room_id:
                room_state_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/rooms/{room_id}/state"
                try:
                    async with session.get(room_state_url, headers=headers) as response:
                        if response.status == 200:
                            state_events = await response.json()
                            
                            # Chercher l'événement m.room.name pour le nom du salon
                            for event in state_events:
                                if event.get("type") == "m.room.name":
                                    context["room_name"] = event.get("content", {}).get("name", "")
                                    break
                            
                            # Vérifier si c'est un chat direct
                            for event in state_events:
                                if event.get("type") == "m.room.member":
                                    # Un salon avec seulement deux membres est probablement un chat direct
                                    # Cette heuristique pourrait être améliorée
                                    pass
                        else:
                            logger.warning(f"Impossible de récupérer l'état du salon: {response.status}")
                except Exception as e:
                    logger.warning(f"Erreur lors de la récupération de l'état du salon: {str(e)}")
            
            # 2. Récupérer le contenu du message parent si reply_to est disponible
            if reply_to and room_id:
                event_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/rooms/{room_id}/event/{reply_to}"
                try:
                    async with session.get(event_url, headers=headers) as response:
                        if response.status == 200:
                            parent_event = await response.json()
                            if parent_event.get("type") == "m.room.message":
                                context["parent_message"] = parent_event.get("content", {}).get("body", "")
                                
                                # Récupérer aussi l'expéditeur du message parent
                                parent_sender = parent_event.get("sender", "")
                                if parent_sender:
                                    # On pourrait aller chercher le nom d'affichage
                                    pass
                        else:
                            logger.warning(f"Impossible de récupérer l'événement parent: {response.status}")
                except Exception as e:
                    logger.warning(f"Erreur lors de la récupération de l'événement parent: {str(e)}")
            
    except Exception as e:
        logger.error(f"Erreur générale lors de la récupération du contexte: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
    
    return context

def main():
    """Point d'entrée principal"""
    # Afficher les informations de diagnostic
    logger.info("=== DÉMARRAGE DU SERVEUR WEBHOOK OPTIMISÉ ===")
    logger.info(f"Niveau de log configuré: {logging.getLevelName(logger.getEffectiveLevel())}")
    logger.info(f"Configuration du webhook: {WEBHOOK_HOST}:{WEBHOOK_PORT}{WEBHOOK_ENDPOINT}")
    
    # Vérifier que les logs de différents niveaux fonctionnent
    logger.debug("Ceci est un message de niveau DEBUG")
    logger.info("Ceci est un message de niveau INFO")
    logger.warning("Ceci est un message de niveau WARNING")
    
    # Afficher les configurations importantes
    logger.info(f"Webhook global: {GLOBAL_WEBHOOK_URL if GLOBAL_WEBHOOK_URL else 'Non configuré'}")
    logger.info(f"Transfert automatique: {'Activé' if GLOBAL_WEBHOOK_AUTO_FORWARD else 'Désactivé'}")
    logger.info(f"Nombre de salons configurés: {len(WEBHOOK_ROOM_CONFIG)}")
    logger.info(f"Simplification du payload: {'Activée' if WEBHOOK_SIMPLIFY_PAYLOAD else 'Désactivée'}")
    
    logger.info("Starting in webhook-only mode with optimized payload...")
    logger.info("Starting webhook server...")
    
    async def run_server():
        app = await start_webhook_server()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT)
        
        await site.start()
        logger.info(f"Serveur démarré sur http://{WEBHOOK_HOST}:{WEBHOOK_PORT}")
        
        # Maintenir le serveur en vie indéfiniment
        while True:
            await asyncio.sleep(3600)  # Attendre une heure
    
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Webhook server stopped by user")
    except Exception as e:
        logger.error(f"Error starting webhook server: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
        return 1
    
    return 0

if __name__ == "__main__":
    main() 