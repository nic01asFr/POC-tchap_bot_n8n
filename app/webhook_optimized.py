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
WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", "8080"))
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
MATRIX_HOMESERVER = os.environ.get("MATRIX_HOME_SERVER", "")
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
    """Gère les événements Matrix (webhooks entrants)"""
    try:
        logger.info(f"Traitement d'une requête Matrix: {request.method} {request.path}")
        logger.debug(f"En-têtes de la requête: {dict(request.headers)}")
        
        # Extraire les données de la requête
        data = {}
        request_text = None
        
        if request.method == "GET":
            data = dict(request.query)
            logger.info(f"Requête GET reçue avec {len(data)} paramètres")
        else:
            # Essayer plusieurs formats possibles
            try:
                request_text = await request.text()
                logger.debug(f"Corps de la requête brut: {request_text[:500]}{'...' if len(request_text) > 500 else ''}")
                
                try:
                    # Essayer d'abord comme JSON
                    data = await request.json()
                    logger.info("Requête traitée comme JSON")
                except json.JSONDecodeError as e:
                    logger.warning(f"Échec du parsing JSON: {str(e)}")
                    
                    # Essayer comme form data
                    try:
                        form_data = await request.post()
                        data = dict(form_data)
                        logger.info("Requête traitée comme form data")
                    except Exception as form_err:
                        logger.warning(f"Échec du parsing form data: {str(form_err)}")
                        
                        # Dernier recours: traiter comme texte brut
                        if request_text:
                            try:
                                # Essayer de parser le texte comme JSON
                                data = json.loads(request_text)
                                logger.info("Requête texte brut traitée comme JSON")
                            except json.JSONDecodeError:
                                # Créer un dictionnaire avec le texte brut
                                data = {"raw_text": request_text}
                                logger.info("Requête traitée comme texte brut")
            except Exception as general_err:
                logger.error(f"Erreur générale lors de l'extraction des données: {str(general_err)}")
                data = {"error": "Impossible d'extraire les données de la requête"}
        
        logger.info(f"Événement Matrix reçu avec {len(data)} champs")
        
        # Vérifier si les données sont vides
        if not data:
            logger.warning("Aucune donnée extraite de la requête")
            return web.json_response({"success": False, "error": "No data received"})
            
        # Afficher le type de données reçues
        logger.debug(f"Type de données reçues: {type(data)}")
        logger.debug(f"Clés présentes dans les données: {list(data.keys())}")
        
        try:
            # Afficher les données complètes reçues (en mode debug)
            logger.debug(f"Données complètes reçues: {json.dumps(data, indent=2, default=str)}")
        except Exception as e:
            logger.warning(f"Impossible de sérialiser les données en JSON: {str(e)}")
        
        # Extraire et logger les informations importantes
        event_type = data.get("event", "message")
        room_id = data.get("room_id", "")
        sender = data.get("sender", "")
        message = data.get("message", "")
        
        logger.info(f"Message reçu dans le salon {room_id or 'inconnu'} de {sender or 'inconnu'}")
        logger.info(f"Type d'événement: {event_type}")
        logger.info(f"Contenu du message: {message[:100]}{'...' if len(message) > 100 else ''}")
        
        # Journaliser d'autres métadonnées si disponibles
        if "timestamp" in data:
            logger.debug(f"Horodatage du message: {data['timestamp']}")
        if "event_id" in data:
            logger.debug(f"ID de l'événement: {data['event_id']}")
        
        # Vérifier si une configuration spécifique existe pour cette salle
        if room_id and room_id in WEBHOOK_ROOM_CONFIG:
            config = WEBHOOK_ROOM_CONFIG[room_id]
            if isinstance(config, dict):
                target_url = config.get("url", "")
                method = config.get("method", "GET")
            else:
                # Format simplifié (juste l'URL)
                target_url = config
                method = "GET"
                
            if target_url:
                logger.info(f"Envoi de l'événement à l'URL spécifique pour la salle {room_id}: {target_url}")
                logger.debug(f"Méthode utilisée: {method}")
                success = await send_webhook(target_url, data, method)
                logger.info(f"Résultat de l'envoi au webhook spécifique: {'succès' if success else 'échec'}")
                return web.json_response({"success": success})
        elif room_id:
            logger.info(f"Aucune configuration spécifique trouvée pour la salle {room_id}")
        else:
            logger.warning("Aucun identifiant de salon trouvé dans les données")
        
        # Si pas de config spécifique, utiliser le webhook global
        if GLOBAL_WEBHOOK_AUTO_FORWARD and GLOBAL_WEBHOOK_URL:
            logger.info(f"Envoi de l'événement au webhook global: {GLOBAL_WEBHOOK_URL}")
            logger.debug(f"Méthode utilisée pour le webhook global: {GLOBAL_WEBHOOK_METHOD}")
            success = await send_webhook(GLOBAL_WEBHOOK_URL, data, GLOBAL_WEBHOOK_METHOD)
            logger.info(f"Résultat de l'envoi au webhook global: {'succès' if success else 'échec'}")
            return web.json_response({"success": success})
        
        logger.warning("Aucun webhook configuré pour ce message, il ne sera pas transmis")
        return web.json_response({"success": False, "error": "No webhook configured"})
    
    except Exception as e:
        logger.error(f"Erreur lors du traitement de l'événement Matrix: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
        return web.json_response({"success": False, "error": str(e)})

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

async def process_matrix_message(room_id, event_id, sender, message_text, msg_type="m.room.message", reply_to=None, thread_root=None):
    """
    Traite un message Matrix et l'envoie au webhook n8n avec des informations enrichies
    
    Args:
        room_id: ID du salon Matrix
        event_id: ID de l'événement Matrix
        sender: Expéditeur du message
        message_text: Texte du message
        msg_type: Type de message Matrix
        reply_to: ID de l'événement auquel ce message répond
        thread_root: ID de l'événement racine du fil de discussion
    """
    global global_access_token
    
    logger.info(f"Traitement d'un message Matrix du salon {room_id} de {sender}, event_id: {event_id}")
    
    # Identifier le token associé à ce salon pour la réponse
    token = None
    for t, rid in WEBHOOK_INCOMING_ROOMS_CONFIG.items():
        if rid == room_id:
            token = t
            break
    
    # Vérifier que l'event_id est valide
    if not event_id:
        logger.warning("Aucun event_id valide fourni pour ce message")
        event_id = f"unknown_{int(asyncio.get_event_loop().time())}"
    
    # Déterminer le type d'événement réel (pas seulement l'ID)
    event_type = "m.room.message"  # Par défaut
    
    # On initialise avec des valeurs par défaut
    event_context = {
        "room_name": "",
        "sender_display_name": "",
        "parent_message": "",
        "is_direct_chat": False
    }
    
    # Si l'API Matrix est activée et qu'on a stocké le token d'accès, on peut enrichir les données
    if MATRIX_API_ENABLED and global_access_token and (STORE_ACCESS_TOKEN or reply_to):
        try:
            logger.info("Récupération du contexte enrichi pour le message")
            event_context = await fetch_matrix_event_context(global_access_token, event_id, room_id, reply_to)
            logger.debug(f"Contexte récupéré: {json.dumps(event_context, indent=2)}")
        except Exception as e:
            logger.warning(f"Erreur lors de la récupération du contexte enrichi: {str(e)}")
    
    # Préparer les données à envoyer à n8n de manière enrichie
    data = {
        "event": event_type,
        "room_id": room_id,
        "event_id": event_id,
        "original_event_id": event_id,  # Ajout explicite pour que n8n puisse facilement récupérer cet ID
        "sender": sender,
        "message": message_text,
        "chatInput": message_text,  # Ajout pour compatibilité avec n8n existant
        "message_type": msg_type,
        "timestamp": str(asyncio.get_event_loop().time()),
        "format": "markdown",  # Ajouter markdown comme format par défaut
        
        # Informations enrichies pour la structure hiérarchique
        "room_name": event_context["room_name"],
        "is_direct_chat": event_context["is_direct_chat"],
        "sender_display_name": event_context["sender_display_name"],
        "parent_message": event_context["parent_message"],
        "event_type": event_type,
        
        # Ajouter la liste des workflows disponibles pour l'agent
        "available_workflows": AVAILABLE_WORKFLOWS
    }
    
    # Ajouter des informations sur les fils de discussion
    if thread_root:
        data["is_threaded"] = True
    else:
        data["is_threaded"] = False
    
    # Ajouter les informations de relation si présentes
    if reply_to:
        data["reply_to"] = reply_to
    
    if thread_root:
        data["thread_root"] = thread_root
    
    if token:
        data["response_token"] = token
    
    # Afficher les données brutes pour le débogage
    logger.debug(f"Données avant filtrage: {json.dumps(data, indent=2)}")
    
    # Envoyer au webhook spécifique pour ce salon s'il existe
    success_any = False
    if room_id in WEBHOOK_ROOM_CONFIG:
        config = WEBHOOK_ROOM_CONFIG[room_id]
        if isinstance(config, dict):
            target_url = config.get("url", "")
            method = config.get("method", "POST")  # Utiliser POST par défaut
        else:
            # Format simplifié (juste l'URL)
            target_url = config
            method = "POST"  # Utiliser POST par défaut
            
        if target_url:
            # Vérifier si nous avons plusieurs URLs séparées par des virgules
            if "," in target_url:
                target_urls = [url.strip() for url in target_url.split(",")]
                logger.info(f"Détection de {len(target_urls)} URLs pour le salon {room_id}")
                
                for url in target_urls:
                    logger.info(f"Envoi du message à l'URL spécifique pour la salle {room_id}: {url}")
                    success = await send_webhook(url, data, method)
                    logger.info(f"Résultat de l'envoi au webhook {url}: {'succès' if success else 'échec'}")
                    success_any = success_any or success
                
                return success_any
            else:
                logger.info(f"Envoi du message à l'URL spécifique pour la salle {room_id}: {target_url}")
                success = await send_webhook(target_url, data, method)
                logger.info(f"Résultat de l'envoi au webhook spécifique: {'succès' if success else 'échec'}")
                return success
    
    # Sinon, utiliser le webhook global
    if GLOBAL_WEBHOOK_AUTO_FORWARD and GLOBAL_WEBHOOK_URL:
        # Vérifier si nous avons plusieurs URLs séparées par des virgules
        if "," in GLOBAL_WEBHOOK_URL:
            target_urls = [url.strip() for url in GLOBAL_WEBHOOK_URL.split(",")]
            logger.info(f"Détection de {len(target_urls)} URLs pour le webhook global")
            
            for url in target_urls:
                logger.info(f"Envoi du message au webhook global: {url}")
                success = await send_webhook(url, data, GLOBAL_WEBHOOK_METHOD)
                logger.info(f"Résultat de l'envoi au webhook {url}: {'succès' if success else 'échec'}")
                success_any = success_any or success
            
            return success_any
        else:
            logger.info(f"Envoi du message au webhook global: {GLOBAL_WEBHOOK_URL}")
            success = await send_webhook(GLOBAL_WEBHOOK_URL, data, GLOBAL_WEBHOOK_METHOD)
            logger.info(f"Résultat de l'envoi au webhook global: {'succès' if success else 'échec'}")
            return success
    
    logger.warning("Aucun webhook configuré pour ce message, il ne sera pas transmis")
    return False

async def setup_matrix_listener():
    """Configure un écouteur pour les messages Matrix et les renvoie vers n8n"""
    global global_access_token
    
    if not MATRIX_HOMESERVER or not MATRIX_USERNAME or not MATRIX_PASSWORD:
        logger.warning("Configuration Matrix incomplète, impossible de configurer l'écouteur de messages")
        return False
    
    try:
        # 1. S'authentifier d'abord pour obtenir un token
        async with aiohttp.ClientSession() as session:
            login_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/login"
            login_data = {
                "type": "m.login.password",
                "user": MATRIX_USERNAME,
                "password": MATRIX_PASSWORD
            }
            
            logger.info(f"Tentative de connexion à {MATRIX_HOMESERVER} pour configurer l'écouteur")
            async with session.post(login_url, json=login_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Échec de connexion à Matrix pour l'écouteur: {response.status} - {error_text}")
                    return False
                
                login_response = await response.json()
                access_token = login_response.get("access_token")
                user_id = login_response.get("user_id")
                
                if not access_token:
                    logger.error("Pas de token d'accès dans la réponse Matrix")
                    return False
                
                # Stocker le token d'accès pour l'enrichissement des données
                if STORE_ACCESS_TOKEN:
                    global_access_token = access_token
                    logger.info("Token d'accès Matrix enregistré pour l'enrichissement des données")
                
                logger.info(f"Connexion à Matrix réussie pour l'écouteur (user_id: {user_id})")
        
        # Stocker les IDs des messages déjà traités pour éviter les doublons
        processed_events = set()
        
        # Stocker le timestamps de démarrage pour ignorer les anciens messages
        start_timestamp = asyncio.get_event_loop().time()
        logger.info(f"Timestamp de démarrage: {start_timestamp}")
        
        # 2. Configurer l'écouteur en utilisant le polling sync
        async def sync_loop(access_token, bot_user_id):
            nonlocal start_timestamp
            next_batch = None  # Commencer sans "since" pour obtenir uniquement les nouveaux messages
            first_sync = True
            
            # Faire un premier sync pour marquer où on commence (sans traiter les messages)
            sync_url = f"{MATRIX_HOMESERVER}/_matrix/client/r0/sync"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            try:
                async with aiohttp.ClientSession() as init_session:
                    async with init_session.get(sync_url, headers=headers) as sync_response:
                        if sync_response.status == 200:
                            sync_data = await sync_response.json()
                            next_batch = sync_data.get("next_batch")
                            logger.info(f"Synchronisation initiale réussie, token: {next_batch}")
                            
                            # Stocker tous les événements existants comme déjà traités
                            rooms = sync_data.get("rooms", {}).get("join", {})
                            for room_id, room_data in rooms.items():
                                timeline = room_data.get("timeline", {})
                                events = timeline.get("events", [])
                                for event in events:
                                    event_id = event.get("event_id")
                                    if event_id:
                                        processed_events.add(event_id)
                                        logger.debug(f"Événement initial marqué comme traité: {event_id}")
                            
                            logger.info(f"Nombre d'événements initiaux ignorés: {len(processed_events)}")
                        else:
                            logger.error(f"Erreur lors de la synchronisation initiale: {sync_response.status}")
            except Exception as e:
                logger.error(f"Erreur lors de la synchronisation initiale: {e}")
            
            logger.info("Démarrage de l'écouteur de messages (ignorant les messages antérieurs)")
            
            # Attendre un court délai pour s'assurer que les messages de bienvenue sont traités
            await asyncio.sleep(5)
            
            while True:
                try:
                    # Créer une nouvelle session pour chaque itération
                    async with aiohttp.ClientSession() as session:
                        # Construire l'URL de sync
                        params = {"timeout": 30000}
                        if next_batch:
                            params["since"] = next_batch
                        
                        headers = {"Authorization": f"Bearer {access_token}"}
                        
                        async with session.get(sync_url, params=params, headers=headers) as sync_response:
                            if sync_response.status != 200:
                                logger.error(f"Erreur lors du sync: {sync_response.status}")
                                await asyncio.sleep(5)  # Attente avant de réessayer
                                continue
                            
                            sync_data = await sync_response.json()
                            next_batch = sync_data.get("next_batch")
                            
                            # Traiter les événements de salle
                            rooms = sync_data.get("rooms", {}).get("join", {})
                            for room_id, room_data in rooms.items():
                                timeline = room_data.get("timeline", {})
                                events = timeline.get("events", [])
                                
                                for event in events:
                                    # Ignorer les messages déjà traités
                                    event_id = event.get("event_id")
                                    if event_id in processed_events:
                                        continue
                                    
                                    # Ajouter l'événement aux événements traités
                                    processed_events.add(event_id)
                                    
                                    # Vérifier l'horodatage de l'événement s'il est disponible
                                    event_ts = event.get("origin_server_ts", 0)
                                    if event_ts and event_ts/1000 < start_timestamp:
                                        logger.debug(f"Ignorer événement antérieur au démarrage: {event_id}")
                                        continue
                                    
                                    # Ignorer les messages de bienvenue du bot pendant la première synchronisation
                                    if first_sync and event.get("type") == "m.room.message":
                                        content = event.get("content", {})
                                        message = content.get("body", "")
                                        if "Je suis en ligne et prêt à vous aider" in message:
                                            logger.info(f"Ignorer message de bienvenue: {event_id}")
                                            continue
                                    
                                    # Maintenir la taille de l'ensemble des événements traités (limiter la mémoire)
                                    if len(processed_events) > 1000:
                                        # Garder uniquement les 500 derniers événements
                                        processed_events_list = list(processed_events)
                                        processed_events.clear()
                                        processed_events.update(processed_events_list[-500:])
                                    
                                    # Ne traiter que les messages texte
                                    if event.get("type") == "m.room.message" and event.get("content", {}).get("msgtype") == "m.text":
                                        sender = event.get("sender", "")
                                        
                                        # Ignorer les messages envoyés par le bot lui-même
                                        if sender == bot_user_id:
                                            logger.debug(f"Ignorer message du bot lui-même: {event_id}")
                                            continue
                                        
                                        content = event.get("content", {})
                                        message = content.get("body", "")
                                        
                                        # Extraire les informations de relation (réponse à, fil de discussion)
                                        relates_to = content.get("m.relates_to", {})
                                        reply_to = relates_to.get("m.in_reply_to", {}).get("event_id")
                                        thread_root = None
                                        
                                        if "rel_type" in relates_to and relates_to.get("rel_type") == "m.thread":
                                            thread_root = relates_to.get("event_id")
                                        
                                        if message and event_id:
                                            # Transmettre le message à n8n via le webhook
                                            await process_matrix_message(
                                                room_id, 
                                                event_id, 
                                                sender, 
                                                message, 
                                                reply_to=reply_to, 
                                                thread_root=thread_root
                                            )
                            
                            # Marquer que la première synchronisation est terminée
                            if first_sync:
                                first_sync = False
                                logger.info("Première synchronisation terminée")
                
                except Exception as e:
                    logger.error(f"Erreur dans la boucle de sync: {str(e)}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(5)  # Attente avant de réessayer
        
        # Démarrer la boucle de sync dans une tâche asyncio avec le token
        asyncio.create_task(sync_loop(global_access_token, user_id))
        logger.info("Écouteur Matrix configuré et démarré")
        return True
                
    except Exception as e:
        logger.error(f"Erreur lors de la configuration de l'écouteur Matrix: {str(e)}")
        import traceback
        logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
        return False

async def start_webhook_server():
    """Démarre le serveur webhook"""
    app = web.Application(client_max_size=1024**2*10)  # 10 MB max
    
    # Log pour toutes les requêtes reçues
    @web.middleware
    async def logging_middleware(request, handler):
        logger.info(f"Requête reçue: {request.method} {request.path}")
        try:
            return await handler(request)
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la requête: {str(e)}")
            import traceback
            logger.error(f"Détails de l'erreur: {traceback.format_exc()}")
            raise
    
    # Appliquer le middleware à toutes les requêtes
    app.middlewares.append(logging_middleware)
    
    # Endpoint de test pour vérifier que le serveur fonctionne
    test_endpoint = "/test"
    app.router.add_route("*", test_endpoint, handle_test_endpoint)
    
    # Endpoint Matrix (Tchap → n8n)
    app.router.add_route("*", WEBHOOK_ENDPOINT, handle_matrix_event)
    
    # Endpoint supplémentaire pour n8n
    additional_endpoint = "/webhook-test/matrix_webhook"
    app.router.add_route("*", additional_endpoint, handle_matrix_event)
    
    # Endpoint entrant (n8n → Tchap)
    inbound_route = f"{WEBHOOK_ENDPOINT}/inbound"
    app.router.add_route("*", inbound_route, handle_n8n_webhook)
    
    # Endpoint de test n8n
    test_route = "/webhook-test/matrix_webhook"
    app.router.add_route("*", test_route, handle_n8n_webhook)
    
    # Envoyer un message de bienvenue
    await send_welcome_message_to_rooms()
    
    # Configurer l'écouteur Matrix pour transmettre les messages à n8n
    listener_setup = await setup_matrix_listener()
    if listener_setup:
        logger.info("Écouteur Matrix activé pour transmettre les messages à n8n")
    else:
        logger.warning("Impossible de configurer l'écouteur Matrix, les messages ne seront pas transmis automatiquement")
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT)
    
    logger.info(f"Webhook server started on http://{WEBHOOK_HOST}:{WEBHOOK_PORT}{WEBHOOK_ENDPOINT}")
    logger.info(f"Test endpoint: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}{test_endpoint}")
    logger.info(f"Additional webhook endpoint: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}{additional_endpoint}")
    
    # Log des webhooks entrants configurés
    if WEBHOOK_INCOMING_ROOMS_CONFIG:
        logger.info(f"Configured incoming webhooks: {len(WEBHOOK_INCOMING_ROOMS_CONFIG)}")
        for token, room_id in WEBHOOK_INCOMING_ROOMS_CONFIG.items():
            logger.info(f"  - Token '{token}' -> Room {room_id}")
    
    await site.start()
    
    # Garder le serveur en exécution
    while True:
        await asyncio.sleep(3600)  # 1 heure

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
    
    try:
        asyncio.run(start_webhook_server())
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