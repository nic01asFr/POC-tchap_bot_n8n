"""
Module pour filtrer et réduire la taille des données webhook avant envoi à n8n.
"""
import json
import os
import logging
from typing import Dict, Any, Optional

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paramètres depuis les variables d'environnement
MAX_MESSAGE_LENGTH = int(os.environ.get("WEBHOOK_MAX_MESSAGE_LENGTH", 1000))
SIMPLIFY_PAYLOAD = os.environ.get("WEBHOOK_SIMPLIFY_PAYLOAD", "True").lower() == "true"
FILTER_METADATA = os.environ.get("WEBHOOK_FILTER_METADATA", "True").lower() == "true"
INCLUDE_HIERARCHICAL_DATA = os.environ.get("WEBHOOK_INCLUDE_HIERARCHICAL_DATA", "True").lower() == "true"

# Nouveau paramètre pour contrôler le niveau de simplification
# minimal: garde seulement les données minimales requises
# standard: garde les données enrichies mais sans la structure hiérarchique
# full: garde toutes les données enrichies avec la structure hiérarchique
SIMPLIFICATION_LEVEL = os.environ.get("WEBHOOK_SIMPLIFICATION_LEVEL", "standard")

def create_structured_data(data):
    """
    Crée une structure hiérarchique des données pour une meilleure organisation.
    
    Args:
        data: Données filtrées
        
    Returns:
        Structure hiérarchique des données
    """
    return {
        "event": {
            "id": data.get("event_id", ""),
            "type": data.get("event", "matrix_message"),
            "timestamp": data.get("timestamp", "")
        },
        "room": {
            "id": data.get("room_id", ""),
            "name": data.get("room_name", ""),
            "isDirectChat": data.get("is_direct_chat", False)
        },
        "sender": {
            "id": data.get("sender", ""),
            "displayName": data.get("sender_display_name", "")
        },
        "message": {
            "content": data.get("message", ""),
            "type": data.get("message_type", "m.text")
        },
        "context": {
            "isThreaded": data.get("is_threaded", False),
            "threadRoot": data.get("thread_root", ""),
            "replyTo": data.get("reply_to", ""),
            "parentMessage": data.get("parent_message", "")
        }
    }

def filter_webhook_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filtre et enrichit les données Matrix avant de les envoyer à n8n.
    
    Args:
        data: Données Matrix d'origine
        
    Returns:
        Données filtrées, enrichies et structurées
    """
    # Si la simplification est désactivée, renvoyer toutes les données
    if not SIMPLIFY_PAYLOAD:
        # Ajouter chatInput pour la compatibilité
        if "message" in data and "chatInput" not in data:
            data["chatInput"] = data["message"]
        
        # Ajouter la structure hiérarchique si configurée
        if INCLUDE_HIERARCHICAL_DATA:
            data["structured"] = create_structured_data(data)
            
        return data
        
    logger.info("Filtering and enriching webhook data before sending to n8n")
    
    # Format adapté spécifiquement pour l'agent IA
    # Structure les données exactement comme demandé par l'utilisateur
    if is_agent_ia_destination(data):
        # Créer la structure avec sessionId au premier niveau pour la mémoire n8n
        sessionId = f"{data.get('room_id', '')}{data.get('sender', '')}"
        message = data.get("message", "")
        
        # Tronquer le message si nécessaire
        if len(message) > MAX_MESSAGE_LENGTH:
            message = message[:MAX_MESSAGE_LENGTH] + "... (message tronqué)"
            logger.info(f"Message tronqué de {len(data.get('message', ''))} à {MAX_MESSAGE_LENGTH} caractères")
        
        # Structure simplifiée avec sessionId et chatInput au premier niveau
        filtered_data = {
            "chatInput": message,
            "sessionId": sessionId,
            # Les informations de contexte ne sont pas nécessaires en retour
            # car elles sont conservées localement par le webhook
            "event_id": data.get("event_id", ""),
            "original_event_id": data.get("original_event_id", data.get("event_id", "")),
            "format": "markdown"
        }
        
        logger.info("Données formatées pour usage direct par l'agent IA")
        return filtered_data
    
    # Liste élargie des champs essentiels selon le niveau de simplification
    if SIMPLIFICATION_LEVEL == "minimal":
        # Version minimale - seulement les champs critiques
        essential_fields = [
            "event", "room_id", "sender", "message", "event_id", "original_event_id",
            "reply_to", "thread_root", "response_token"
        ]
    else:
        # Version standard ou complète - tous les champs enrichis
        essential_fields = [
            "event", "room_id", "sender", "message", "event_id", "original_event_id",
            "reply_to", "thread_root", "response_token", "message_type", 
            "room_name", "is_direct_chat", "is_threaded", "sender_display_name", 
            "parent_message", "event_type", "timestamp"
        ]
    
    # Créer un nouveau payload avec uniquement les données essentielles
    filtered_data = {}
    
    # Ajouter tous les champs essentiels s'ils existent
    for field in essential_fields:
        if field in data and data[field] is not None:
            filtered_data[field] = data[field]
    
    # S'assurer que les champs obligatoires sont présents avec des valeurs par défaut
    if "event" not in filtered_data:
        filtered_data["event"] = "matrix_message"
    if "room_id" not in filtered_data:
        filtered_data["room_id"] = ""
    if "sender" not in filtered_data:
        filtered_data["sender"] = ""
    if "message" not in filtered_data:
        filtered_data["message"] = ""
    
    # S'assurer que event_id est toujours présent (crucial pour la fonctionnalité de réponse)
    if "event_id" not in filtered_data and "event_id" in data:
        filtered_data["event_id"] = data["event_id"]
    elif "event_id" not in filtered_data and "original_event_id" in data:
        filtered_data["event_id"] = data["original_event_id"]
    
    # Ajouter le champ chatInput pour compatibilité avec n8n (toujours incluire)
    filtered_data["chatInput"] = filtered_data.get("message", "")
    
    # Extraire et tronquer le message si nécessaire
    message = filtered_data.get("message", "")
    if message and len(message) > MAX_MESSAGE_LENGTH:
        filtered_data["message"] = message[:MAX_MESSAGE_LENGTH] + "... (message tronqué)"
        filtered_data["chatInput"] = filtered_data["message"]
        logger.info(f"Message tronqué de {len(message)} à {MAX_MESSAGE_LENGTH} caractères")
    
    # Si on veut conserver certaines métadonnées utiles
    if not FILTER_METADATA and "timestamp" in data and "timestamp" not in filtered_data:
        filtered_data["timestamp"] = data["timestamp"]
    
    # Ajouter la structure hiérarchique pour une meilleure organisation des données
    if INCLUDE_HIERARCHICAL_DATA and SIMPLIFICATION_LEVEL == "full":
        filtered_data["structured"] = create_structured_data(filtered_data)
    
    # S'assurer que format est toujours présent avec markdown par défaut
    if "format" not in filtered_data:
        filtered_data["format"] = "markdown"
    
    # Log détaillé des données pour le débogage
    logger.debug(f"Données originales: {json.dumps({k: v for k, v in data.items() if k in essential_fields}, indent=2)}")
    logger.debug(f"Données filtrées: {json.dumps(filtered_data, indent=2)}")
    
    # Vérifier que event_id est bien conservé
    if "event_id" in data and "event_id" not in filtered_data:
        logger.warning(f"ATTENTION: event_id est présent dans les données d'origine mais absent des données filtrées!")
    
    # Journaliser la modification de taille
    original_size = len(json.dumps(data))
    filtered_size = len(json.dumps(filtered_data))
    reduction = (1 - filtered_size / original_size) * 100 if original_size > 0 else 0
    
    logger.info(f"Taille des données modifiée de {original_size} à {filtered_size} octets ({reduction:.1f}%)")
    
    return filtered_data

def is_agent_ia_destination(data: Dict[str, Any]) -> bool:
    """
    Détecte si la destination est un agent IA en vérifiant:
    1. Si le webhook URL contient 'matrix_webhook' ou 'tool_agent'
    2. Si le room_id correspond à une salle pour laquelle on a configuré un webhook d'agent IA
    
    Args:
        data: Données Matrix d'origine
        
    Returns:
        True si la destination est probablement un agent IA
    """
    # Vérifier si le message est une commande !tools, qui doit être traitée par n8n_commands
    message = data.get("message", "").strip()
    if message == "!tools" or message.startswith("!tools "):
        logger.info("Commande !tools détectée, ne sera pas envoyée à l'agent IA")
        return False
    
    # Vérifier si l'URL cible contient des indicateurs d'agent IA
    target_url = os.environ.get("GLOBAL_WEBHOOK_URL", "")
    room_id = data.get("room_id", "")
    
    # Vérifier dans la configuration de salle
    room_config_str = os.environ.get("WEBHOOK_ROOM_CONFIG", "{}")
    try:
        room_config = json.loads(room_config_str)
        if room_id and room_id in room_config:
            config = room_config[room_id]
            if isinstance(config, dict) and "url" in config:
                target_url = config["url"]
            elif isinstance(config, str):
                target_url = config
    except json.JSONDecodeError:
        logger.error("Erreur lors du décodage de WEBHOOK_ROOM_CONFIG")
    
    # Détecter si c'est un webhook pour agent IA
    is_agent_webhook = False
    if target_url and ("matrix_webhook" in target_url or "tool_agent" in target_url):
        is_agent_webhook = True
        logger.info("Destination détectée comme étant un agent IA")
    
    return is_agent_webhook 