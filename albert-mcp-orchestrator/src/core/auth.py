"""
Système d'authentification pour l'API MCP Orchestrator.

Ce module gère l'authentification par clé API pour sécuriser les endpoints.
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from typing import Optional, Dict, List

# Importation des paramètres depuis le module de configuration
from ..config import settings

# Définition du header pour la clé API
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(
    api_key_header: Optional[str] = Depends(API_KEY_HEADER),
    request: Request = None
) -> str:
    """
    Vérifie la validité de la clé API fournie dans l'en-tête de la requête.
    
    Args:
        api_key_header: Clé API fournie dans l'en-tête X-API-Key
        request: Objet requête FastAPI
        
    Returns:
        La clé API valide
        
    Raises:
        HTTPException: Si la clé API est invalide ou manquante
    """
    # Si nous sommes en mode debug, on peut désactiver la vérification de l'API
    if settings.DEBUG and hasattr(settings, 'BYPASS_AUTH') and settings.BYPASS_AUTH:
        # Log pour informer que l'authentification est contournée (uniquement en dev)
        from loguru import logger
        logger.warning("Authentification contournée en mode DEBUG")
        return "debug_mode_key"
    
    # Vérification de la présence d'une clé API
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API manquante. Veuillez fournir une clé API valide dans l'en-tête X-API-Key",
        )
    
    # Vérification de la validité de la clé API
    valid_api_key = settings.SECRET_KEY
    
    if api_key_header != valid_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide",
        )
        
    return api_key_header

async def check_admin_permission(api_key: str = Depends(get_api_key)) -> bool:
    """
    Vérifie si l'utilisateur authentifié a des droits administrateur.
    
    Args:
        api_key: Clé API validée par get_api_key
        
    Returns:
        True si l'utilisateur a des droits admin, False sinon
        
    Raises:
        HTTPException: Si l'utilisateur n'a pas les droits admin
    """
    # En production, vous pourriez avoir un mécanisme plus complexe pour les rôles
    # Pour l'instant, on considère que toute clé API valide a des droits admin
    # Pour un système plus complexe, on pourrait avoir une liste de clés admin
    
    is_admin = True  # Simplifié pour l'instant
    
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Droits administrateur requis pour cette opération",
        )
    
    return True 