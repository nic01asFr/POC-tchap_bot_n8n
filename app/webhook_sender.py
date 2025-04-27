"""
Module pour l'envoi de webhooks vers n8n.
"""
import logging
import aiohttp
import json
import os
from typing import Dict, Any, Optional
from urllib.parse import urlencode

# Importer notre filtre
from app.webhook_filter import filter_webhook_data

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_webhook(url: str, data: Dict[str, Any], method: str = "GET") -> bool:
    """
    Envoie les données webhooks à n8n en utilisant notre filtre pour réduire la taille.
    
    Args:
        url: URL du webhook n8n
        data: Données à envoyer
        method: Méthode HTTP (GET ou POST)
        
    Returns:
        Booléen indiquant si l'envoi a réussi
    """
    # Appliquer notre filtre pour réduire la taille des données
    filtered_data = filter_webhook_data(data)
    
    try:
        async with aiohttp.ClientSession() as session:
            if method.upper() == "GET":
                # Pour GET, on convertit les données en paramètres de requête
                # C'est plus efficace pour éviter les problèmes de taille de payload
                params = {}
                
                # Ajouter format markdown par défaut s'il n'est pas déjà défini
                if 'format' not in filtered_data:
                    filtered_data['format'] = 'markdown'
                
                for key, value in filtered_data.items():
                    # Conversion simple en chaîne pour tous les types
                    if isinstance(value, (dict, list)):
                        params[key] = json.dumps(value)
                    else:
                        params[key] = str(value)
                
                query_string = urlencode(params)
                full_url = f"{url}?{query_string}"
                
                logger.info(f"Envoi webhook GET vers {url}")
                logger.debug(f"URL complète: {full_url}")
                
                # Limiter la taille de l'URL à 2000 caractères (limite standard des navigateurs)
                if len(full_url) > 2000:
                    logger.warning(f"URL trop longue ({len(full_url)} caractères), troncature à 2000 caractères")
                    full_url = full_url[:1997] + "..."
                
                async with session.get(full_url) as response:
                    success = 200 <= response.status < 300
                    if success:
                        logger.info(f"Webhook envoyé avec succès: {response.status}")
                    else:
                        logger.error(f"Échec d'envoi webhook: {response.status}")
                        text = await response.text()
                        logger.error(f"Réponse: {text[:200]}")
                    return success
            else:
                # Pour POST, on envoie les données en JSON dans le corps
                # Avec notre filtre, le volume devrait être réduit
                logger.info(f"Envoi webhook POST vers {url}")
                
                # Ajouter format markdown par défaut s'il n'est pas déjà défini
                if 'format' not in filtered_data:
                    filtered_data['format'] = 'markdown'
                
                async with session.post(url, json=filtered_data) as response:
                    success = 200 <= response.status < 300
                    if success:
                        logger.info(f"Webhook envoyé avec succès: {response.status}")
                    else:
                        logger.error(f"Échec d'envoi webhook: {response.status}")
                        text = await response.text()
                        logger.error(f"Réponse: {text[:200]}")
                    return success
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du webhook: {str(e)}")
        return False 