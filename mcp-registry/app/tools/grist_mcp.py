"""
Module de serveur MCP pour Grist.

Ce module implémente un serveur MCP pour interagir avec l'API Grist.
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

app = FastAPI(title="Grist MCP Server", description="Serveur MCP pour l'API Grist")

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
    "id": "grist-mcp",
    "name": "Grist MCP",
    "description": "Serveur MCP pour la gestion de données et tableaux Grist",
    "version": "1.0.0",
    "capabilities": [
        "list_organizations", 
        "list_tables", 
        "get_table_data", 
        "create_record", 
        "update_record", 
        "delete_record"
    ]
}

@app.get("/mcp")
async def get_mcp_info():
    """Renvoie les informations du serveur MCP."""
    return SERVER_CONFIG

@app.post("/execute")
async def execute_request(request: Request):
    """Point d'entrée pour les requêtes JSON-RPC."""
    try:
        data = await request.json()
        logger.info(f"Requête reçue: {data}")
        
        # Extraire la méthode et les paramètres
        method = data.get("method")
        params = data.get("params", {})
        id = data.get("id", 0)
        
        if not method:
            return JSONResponse(
                content={"jsonrpc": "2.0", "error": {"code": -32600, "message": "Méthode non spécifiée"}, "id": id},
                status_code=400
            )
            
        # Simuler le traitement de différentes méthodes
        if method == "list_organizations":
            result = {"organizations": [{"id": "org1", "name": "Organisation 1"}, {"id": "org2", "name": "Organisation 2"}]}
        elif method == "list_tables":
            result = {"tables": [{"id": "table1", "name": "Contacts"}, {"id": "table2", "name": "Projets"}]}
        elif method == "get_table_data":
            result = {"records": [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]}
        else:
            return JSONResponse(
                content={"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Méthode non supportée: {method}"}, "id": id},
                status_code=400
            )
            
        return {"jsonrpc": "2.0", "result": result, "id": id}
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la requête: {str(e)}")
        return JSONResponse(
            content={"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": 0},
            status_code=500
        )

def main():
    """Point d'entrée principal."""
    logger.info("Démarrage du serveur MCP Grist...")
    
    # Vérifier si un port est spécifié
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    
    # Démarrer le serveur
    uvicorn.run(app, host=host, port=port)
    
if __name__ == "__main__":
    main() 