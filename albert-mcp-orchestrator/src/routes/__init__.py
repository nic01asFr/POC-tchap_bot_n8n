"""
Package des routes pour l'API MCP Orchestrator.

Ce package contient tous les points d'entrée API de l'application:
- Routes pour les compositions
- Routes pour les templates
- Routes pour le registre MCP
- Routes pour les outils MCP
"""

# Importer tous les modules de routes
from . import compositions_routes
from . import templates_routes
from . import registry_routes
from . import tools_routes

__all__ = [
    'compositions_routes',
    'templates_routes',
    'registry_routes',
    'tools_routes',
] 