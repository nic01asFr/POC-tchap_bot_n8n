"""
Module d'intégration n8n pour Albert-Tchap.

Ce module permet à Albert-Tchap de découvrir et d'interagir avec les capacités
exposées par une instance n8n via MCP et Webhook.
"""

import asyncio  # Nécessaire pour les timeouts
from .client import N8nClient
from .command import N8nCommandHandler

__all__ = ["N8nClient", "N8nCommandHandler"] 