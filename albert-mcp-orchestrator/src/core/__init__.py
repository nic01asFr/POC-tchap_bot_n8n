"""
Module core pour MCP Orchestrator.

Ce package contient les éléments fondamentaux pour le fonctionnement de l'application :
- Configuration de la journalisation
- Système d'authentification
- Utilitaires essentiels
"""

from .logging_config import configure_logging
from .auth import get_api_key, check_admin_permission

__all__ = [
    'configure_logging',
    'get_api_key',
    'check_admin_permission',
] 