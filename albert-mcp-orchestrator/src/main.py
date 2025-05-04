"""
Point d'entrée principal de l'application MCP Orchestrator.

Ce module initialise l'application FastAPI et configure les routes,
les middlewares et les dépendances.
"""

import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .core.logging_config import configure_logging
from .core.auth import get_api_key
from .registry.mcp_registry import MCPRegistry
from .registry.mcp_integration import register_tools_with_albert

# Import simplifié des routes pour éviter les erreurs d'importation circulaire
from .routes import compositions_routes, templates_routes, registry_routes, tools_routes

# Configuration du logger
configure_logging()
logger = logging.getLogger(__name__)

# Création de l'application
app = FastAPI(
    title=settings.APP_NAME,
    description="Orchestrateur de compositions MCP pour Albert Tchapbot",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À ajuster en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Création des dossiers nécessaires
def initialize_directories():
    """Crée les répertoires nécessaires pour l'application s'ils n'existent pas."""
    directories = [
        settings.COMPOSITIONS_DIR,
        settings.VALIDATED_COMPOSITIONS_DIR,
        settings.LEARNING_COMPOSITIONS_DIR,
        settings.TEMPLATES_COMPOSITIONS_DIR,
        settings.PRODUCTION_COMPOSITIONS_DIR,
        settings.ARCHIVED_COMPOSITIONS_DIR,
        settings.METRICS_DIR,
        settings.TEMP_DIR
    ]
    
    for directory in directories:
        if not directory.exists():
            logger.info(f"Création du répertoire: {directory}")
            directory.mkdir(parents=True, exist_ok=True)

@app.on_event("startup")
async def startup_event():
    """Exécuté au démarrage de l'application."""
    logger.info(f"Démarrage de {settings.APP_NAME} v{settings.APP_VERSION} en mode {settings.ENVIRONMENT}")
    
    # Initialisation des répertoires
    initialize_directories()
    
    # Initialisation du registre MCP
    try:
        MCPRegistry.initialize()
        logger.info("Registre MCP initialisé avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation du registre MCP: {str(e)}")
        logger.warning("L'application démarre en mode dégradé sans connexion au registre MCP")
    
    # Enregistrement des outils auprès d'Albert
    try:
        # Vérifier que le registre a été initialisé avec succès
        if MCPRegistry._initialized:
            tools_manifest = MCPRegistry.get_instance().get_tools_manifest()
            success = await register_tools_with_albert(tools_manifest)
            if success:
                logger.info("Enregistrement des outils auprès d'Albert réussi")
            else:
                logger.warning("Échec de l'enregistrement des outils auprès d'Albert")
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement des outils auprès d'Albert: {str(e)}")
        logger.warning("Fonctionnalités d'outils MCP non disponibles")

# Ajout des routes
app.include_router(compositions_routes.router)
app.include_router(templates_routes.router)
app.include_router(registry_routes.router)
app.include_router(tools_routes.router)

# Route racine
@app.get("/")
async def root():
    """Endpoint racine de l'API."""
    return {
        "message": f"Bienvenue sur l'API {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "status": "operational"
    }

# Route de vérification de la clé API
@app.get("/auth-check", dependencies=[Depends(get_api_key)])
async def auth_check():
    """Vérifie que l'authentification fonctionne."""
    return {"authenticated": True}

# Configuration des fichiers statiques (si nécessaire)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Point d'entrée pour l'exécution directe
if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    ) 