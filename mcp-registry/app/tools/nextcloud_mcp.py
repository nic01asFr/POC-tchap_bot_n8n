"""
Module de serveur MCP pour Nextcloud Tools.

Ce module implémente un serveur MCP pour les outils Nextcloud.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

logger = logging.getLogger(__name__)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

app = FastAPI(title="Nextcloud Tools MCP Server", description="Serveur MCP pour les outils Nextcloud")

# Configurer CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration du serveur
SERVER_CONFIG = {
    "id": "nextcloud-tools",
    "name": "Nextcloud Tools MCP",
    "description": "Serveur MCP pour les outils Nextcloud",
    "version": "1.0.0",
    "capabilities": ["file-management", "document-processing"]
}

@app.get("/mcp/nextcloud_tools")
async def get_mcp_info():
    """Renvoie les informations du serveur MCP."""
    return SERVER_CONFIG

@app.get("/mcp/nextcloud_tools/sse")
async def get_sse_endpoint():
    """Endpoint SSE pour la communication en temps réel."""
    return JSONResponse(content={"status": "ok", "message": "SSE endpoint ready"})

async def sse_generator():
    """Générateur pour les événements SSE."""
    # En-tête pour SSE
    yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
    
    # Simuler quelques événements
    for i in range(5):
        await asyncio.sleep(2)
        data = json.dumps({"type": "update", "id": i, "message": f"Update {i}"})
        yield f"event: message\ndata: {data}\n\n"
        
    # Terminer
    yield "event: close\ndata: {\"status\": \"closed\"}\n\n"

@app.get("/mcp/nextcloud_tools/sse/stream")
async def stream_sse():
    """Stream SSE pour les mises à jour en temps réel."""
    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/mcp/nextcloud_tools/execute")
async def execute_request(request: Request):
    """Point d'entrée pour les requêtes."""
    try:
        data = await request.json()
        logger.info(f"Requête reçue: {data}")
        
        # Extraire l'action et les paramètres
        action = data.get("action")
        params = data.get("params", {})
        
        if not action:
            return JSONResponse(
                content={"status": "error", "message": "Action non spécifiée"},
                status_code=400
            )
            
        # Simuler le traitement de différentes actions
        if action == "list_files":
            result = {"files": [{"name": "document.docx", "size": 12345}, {"name": "image.jpg", "size": 67890}]}
        elif action == "get_file_info":
            result = {"name": "document.docx", "size": 12345, "modified": "2025-05-01T12:00:00Z"}
        else:
            return JSONResponse(
                content={"status": "error", "message": f"Action non supportée: {action}"},
                status_code=400
            )
            
        return {"status": "success", "result": result}
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la requête: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=500
        )

def main():
    """Point d'entrée principal."""
    logger.info("Démarrage du serveur MCP Nextcloud Tools...")
    
    # Vérifier si un port est spécifié
    port = int(os.environ.get("PORT", 5678))
    host = os.environ.get("HOST", "0.0.0.0")
    
    # Démarrer le serveur
    uvicorn.run(app, host=host, port=port)
    
if __name__ == "__main__":
    main() 