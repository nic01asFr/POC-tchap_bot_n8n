"""
Configuration du système de journalisation pour MCP Orchestrator.

Ce module configure les journaux de l'application avec des formats
adaptés pour le développement et la production.
"""

import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import logging.config

def configure_logging():
    """
    Configure le système de journalisation pour l'application.
    
    - Journaux dans des fichiers avec rotation
    - Format différent selon l'environnement (dev/prod)
    - Journaux système si en production avec systemd
    """
    from ..config import settings
    
    # Créer le répertoire des logs s'il n'existe pas
    log_dir = settings.BASE_DIR / "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Formatter pour le développement (plus détaillé)
    dev_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]'
    )
    
    # Formatter pour la production (plus concis)
    prod_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Choisir le formatter selon l'environnement
    formatter = dev_formatter if settings.ENVIRONMENT == "development" else prod_formatter
    
    # Configurer le gestionnaire de fichier
    file_handler = RotatingFileHandler(
        log_dir / f"mcp_orchestrator_{settings.ENVIRONMENT}.log",
        maxBytes=10485760,  # 10 MB
        backupCount=10
    )
    file_handler.setFormatter(formatter)
    
    # Configurer le gestionnaire de console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Niveau de log basé sur le paramètre DEBUG
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    
    # Configuration de base pour tous les loggers
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Réduire le bruit des bibliothèques tierces
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    
    # Logger pour l'application
    app_logger = logging.getLogger("mcp_orchestrator")
    app_logger.setLevel(log_level)
    
    # Logger pour les outils
    tools_logger = logging.getLogger("mcp_tools")
    tools_logger.setLevel(log_level)
    
    # Log de démarrage
    app_logger.info(f"Configuration de la journalisation pour l'environnement: {settings.ENVIRONMENT}")
    
    return root_logger 