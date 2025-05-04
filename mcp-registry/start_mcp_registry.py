#!/usr/bin/env python
"""
Script principal pour démarrer le MCP Registry.

Ce script lance le MCP Registry qui gère les outils MCP et fournit
une API pour la recherche sémantique et l'exécution d'outils.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Configurer le logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("mcp_registry")

# Ajuster le chemin pour importer les modules du package
sys.path.insert(0, str(Path(__file__).parent))

# S'assurer que les variables d'environnement nécessaires sont définies
if not os.environ.get("MCP_APP_PORT"):
    # Définir le port par défaut à 8001 pour éviter les conflits
    os.environ["MCP_APP_PORT"] = "8001"

# Importer après avoir ajusté le chemin et les variables d'environnement
import uvicorn
from app.main import app

def main():
    """
    Fonction principale qui démarre le MCP Registry.
    """
    parser = argparse.ArgumentParser(description="Démarrer le MCP Registry")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_APP_PORT", 8001)),
                      help="Port d'écoute (défaut: 8001)")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                      help="Hôte d'écoute (défaut: 0.0.0.0)")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                      default="INFO", help="Niveau de logging")
    args = parser.parse_args()
    
    # Configurer le niveau de logging
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Afficher les informations de configuration
    logger.info(f"Démarrage du MCP Registry sur {args.host}:{args.port}")
    logger.info(f"Niveau de log: {args.log_level}")
    
    # Vérifier si ALBERT_API_TOKEN est défini
    if not os.environ.get("ALBERT_API_TOKEN"):
        logger.warning("ALBERT_API_TOKEN n'est pas défini. La génération d'embeddings et l'analyse d'intention ne fonctionneront pas correctement.")
    
    if not os.environ.get("ALBERT_API_URL"):
        logger.info("ALBERT_API_URL n'est pas défini, utilisation de l'URL par défaut: https://albert.api.etalab.gouv.fr")
    
    # Démarrer l'application FastAPI
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower()
    )

if __name__ == "__main__":
    main() 