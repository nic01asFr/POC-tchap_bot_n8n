"""
Point d'entrée principal de l'application MCP Registry.
"""

import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import router as api_router
from .routers import mcp_standard
from .core.registry import MCPRegistry
from .config import settings

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp_registry")

# Créer l'application FastAPI
app = FastAPI(
    title=settings.app.name,
    description=settings.app.description,
    version=settings.app.version,
)

# Ajouter le middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclure les routeurs
app.include_router(api_router)
# Ajouter les endpoints MCP standards directement à la racine
app.include_router(mcp_standard.router)

# Instance globale du registre MCP
registry = None

@app.on_event("startup")
async def startup_event():
    """Événement de démarrage de l'application."""
    global registry
    
    logger.info("Démarrage du MCP Registry...")
    
    # Initialiser le registre MCP
    from .api.router import registry as api_registry
    registry = api_registry
    
    # Démarrer le service de découverte
    await registry.start()
    
    logger.info("MCP Registry démarré avec succès")

@app.on_event("shutdown")
async def shutdown_event():
    """Événement d'arrêt de l'application."""
    global registry
    
    if registry:
        logger.info("Arrêt du MCP Registry...")
        await registry.stop()
        logger.info("MCP Registry arrêté avec succès")

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Gestionnaire d'exception HTTP."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Gestionnaire d'exception général."""
    logger.exception(f"Exception non gérée: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Erreur interne du serveur", "detail": str(exc)},
    )

# Route d'accueil
@app.get("/")
async def root():
    """
    Route racine du service.
    """
    return {
        "name": "MCP Registry for Albert-Tchap",
        "version": "1.0.0",
        "description": "Service de registre pour les serveurs Model Context Protocol (MCP)",
        "documentation": "/docs"
    }

# Route de santé
@app.get("/health")
async def health():
    """
    Vérifie l'état de santé du service.
    """
    return {
        "status": "healthy",
        "servers_count": len(registry.servers) if registry else 0,
        "tools_count": len(registry.tools) if registry else 0
    }

if __name__ == "__main__":
    # Lancer l'application avec Uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=True,
    ) 