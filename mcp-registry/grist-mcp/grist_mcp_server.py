#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serveur MCP pour Grist.

Ce serveur expose les fonctionnalités de Grist via le protocole MCP.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("grist_mcp_server")

# Configuration API Grist
GRIST_API_KEY = os.getenv("GRIST_API_KEY")
GRIST_API_URL = os.getenv("GRIST_API_URL", "https://grist.numerique.gouv.fr/api")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8083"))

if not GRIST_API_KEY:
    logger.error("GRIST_API_KEY non définie. Veuillez définir cette variable d'environnement.")
    sys.exit(1)

app = FastAPI(
    title="Grist MCP Server",
    description="Serveur MCP pour Grist",
    version="1.0.0"
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Client HTTP
client = httpx.AsyncClient(
    headers={"Authorization": f"Bearer {GRIST_API_KEY}"}
)

# Modèles de données
class GristOrg(BaseModel):
    id: int
    name: str
    domain: Optional[str] = None

class GristWorkspace(BaseModel):
    id: int
    name: str
    org_id: int

class GristDocument(BaseModel):
    id: str
    name: str
    workspace_id: int

class GristTable(BaseModel):
    id: str
    name: str

class GristRecord(BaseModel):
    id: int
    fields: Dict[str, Any]

class AddRecordRequest(BaseModel):
    doc_id: str = Field(..., description="ID du document Grist")
    table_id: str = Field(..., description="ID de la table Grist")
    fields: Dict[str, Any] = Field(..., description="Champs de l'enregistrement à ajouter")

class UpdateRecordRequest(BaseModel):
    doc_id: str = Field(..., description="ID du document Grist")
    table_id: str = Field(..., description="ID de la table Grist")
    record_id: int = Field(..., description="ID de l'enregistrement à mettre à jour")
    fields: Dict[str, Any] = Field(..., description="Champs de l'enregistrement à mettre à jour")

class DeleteRecordRequest(BaseModel):
    doc_id: str = Field(..., description="ID du document Grist")
    table_id: str = Field(..., description="ID de la table Grist")
    record_id: int = Field(..., description="ID de l'enregistrement à supprimer")

class QueryRequest(BaseModel):
    doc_id: str = Field(..., description="ID du document Grist")
    query: str = Field(..., description="Requête SQL à exécuter")

# Endpoints MCP standards
@app.get("/mcp/info")
async def mcp_info():
    """
    Endpoint standard du protocole MCP qui fournit des informations sur ce serveur.
    """
    return {
        "name": "Grist MCP Server",
        "version": "1.0.0",
        "provider": "Grist",
        "protocolVersion": "1.0",
        "supportedFeatures": ["tools"],
        "description": "Serveur MCP pour l'intégration avec Grist"
    }

@app.get("/mcp/")
async def mcp_root():
    """
    Endpoint racine MCP pour la découverte.
    """
    return {
        "status": "online",
        "message": "Grist MCP Server is running",
        "services": ["tools"]
    }

@app.post("/mcp")
async def mcp_request(request: Request):
    """
    Endpoint principal pour les requêtes MCP.
    """
    try:
        config = request.query_params.get("config", "{}")
        config_dict = json.loads(config)
        body = await request.json()
        
        logger.info(f"MCP Request received: {body}")
        
        # Traiter les différents types de requêtes MCP
        if body.get("type") == "tools.list":
            return {
                "tools": await list_tools_mcp()
            }
        elif body.get("type") == "tools.execute":
            tool_name = body.get("name")
            params = body.get("params", {})
            result = await execute_tool_mcp(tool_name, params)
            return {
                "result": result
            }
        else:
            return {
                "error": "Unsupported MCP request type",
                "type": body.get("type")
            }
    except Exception as e:
        logger.error(f"Error processing MCP request: {str(e)}")
        return {
            "error": str(e)
        }

# Endpoint pour lister les outils (pour compatibilité avec l'ancienne API)
@app.get("/tools")
async def list_tools():
    """Liste tous les outils MCP disponibles."""
    return await list_tools_mcp()

# Nouvelle fonction pour lister les outils au format MCP
async def list_tools_mcp():
    """Liste tous les outils au format MCP."""
    return [
        {
            "name": "list_orgs",
            "description": "Liste toutes les organisations Grist",
            "parameters": []
        },
        {
            "name": "list_workspaces",
            "description": "Liste tous les espaces de travail d'une organisation",
            "parameters": [
                {
                    "name": "org_id",
                    "type": "integer",
                    "description": "ID de l'organisation",
                    "required": True
                }
            ]
        },
        {
            "name": "list_docs",
            "description": "Liste tous les documents d'un espace de travail",
            "parameters": [
                {
                    "name": "org_id",
                    "type": "integer",
                    "description": "ID de l'organisation",
                    "required": True
                },
                {
                    "name": "workspace_id",
                    "type": "integer",
                    "description": "ID de l'espace de travail",
                    "required": True
                }
            ]
        },
        {
            "name": "list_tables",
            "description": "Liste toutes les tables d'un document",
            "parameters": [
                {
                    "name": "doc_id",
                    "type": "string",
                    "description": "ID du document",
                    "required": True
                }
            ]
        },
        {
            "name": "list_records",
            "description": "Liste les enregistrements d'une table",
            "parameters": [
                {
                    "name": "doc_id",
                    "type": "string",
                    "description": "ID du document",
                    "required": True
                },
                {
                    "name": "table_id",
                    "type": "string",
                    "description": "ID de la table",
                    "required": True
                },
                {
                    "name": "limit",
                    "type": "integer",
                    "description": "Nombre maximum d'enregistrements à retourner",
                    "required": False
                }
            ]
        },
        {
            "name": "add_record",
            "description": "Ajoute un enregistrement à une table",
            "parameters": [
                {
                    "name": "doc_id",
                    "type": "string",
                    "description": "ID du document",
                    "required": True
                },
                {
                    "name": "table_id",
                    "type": "string",
                    "description": "ID de la table",
                    "required": True
                },
                {
                    "name": "fields",
                    "type": "object",
                    "description": "Champs de l'enregistrement à ajouter",
                    "required": True
                }
            ]
        },
        {
            "name": "update_record",
            "description": "Met à jour un enregistrement dans une table",
            "parameters": [
                {
                    "name": "doc_id",
                    "type": "string",
                    "description": "ID du document",
                    "required": True
                },
                {
                    "name": "table_id",
                    "type": "string",
                    "description": "ID de la table",
                    "required": True
                },
                {
                    "name": "record_id",
                    "type": "integer",
                    "description": "ID de l'enregistrement à mettre à jour",
                    "required": True
                },
                {
                    "name": "fields",
                    "type": "object",
                    "description": "Champs de l'enregistrement à mettre à jour",
                    "required": True
                }
            ]
        },
        {
            "name": "delete_record",
            "description": "Supprime un enregistrement d'une table",
            "parameters": [
                {
                    "name": "doc_id",
                    "type": "string",
                    "description": "ID du document",
                    "required": True
                },
                {
                    "name": "table_id",
                    "type": "string",
                    "description": "ID de la table",
                    "required": True
                },
                {
                    "name": "record_id",
                    "type": "integer",
                    "description": "ID de l'enregistrement à supprimer",
                    "required": True
                }
            ]
        },
        {
            "name": "execute_query",
            "description": "Exécute une requête SQL sur un document",
            "parameters": [
                {
                    "name": "doc_id",
                    "type": "string",
                    "description": "ID du document",
                    "required": True
                },
                {
                    "name": "query",
                    "type": "string",
                    "description": "Requête SQL à exécuter",
                    "required": True
                }
            ]
        }
    ]

# Fonction pour exécuter un outil au format MCP
async def execute_tool_mcp(tool_name: str, params: Dict[str, Any]):
    """Exécute un outil MCP avec les paramètres fournis."""
    logger.info(f"Executing tool {tool_name} with params {params}")
    
    if tool_name == "list_orgs":
        return await list_orgs()
    elif tool_name == "list_workspaces":
        return await list_workspaces(params.get("org_id"))
    elif tool_name == "list_docs":
        return await list_docs(params.get("org_id"), params.get("workspace_id"))
    elif tool_name == "list_tables":
        return await list_tables(params.get("doc_id"))
    elif tool_name == "list_records":
        return await list_records(params.get("doc_id"), params.get("table_id"), params.get("limit", 10))
    elif tool_name == "add_record":
        return await add_record(params.get("doc_id"), params.get("table_id"), params.get("fields"))
    elif tool_name == "update_record":
        return await update_record(params.get("doc_id"), params.get("table_id"), params.get("record_id"), params.get("fields"))
    elif tool_name == "delete_record":
        return await delete_record(params.get("doc_id"), params.get("table_id"), params.get("record_id"))
    elif tool_name == "execute_query":
        return await execute_query(params.get("doc_id"), params.get("query"))
    else:
        raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")

# Endpoint pour exécuter un outil (pour compatibilité avec l'ancienne API)
@app.post("/execute")
async def execute_tool(request: Dict[str, Any]):
    tool_name = request.get("tool")
    params = request.get("params", {})
    
    if not tool_name:
        raise HTTPException(status_code=400, detail="Le nom de l'outil est requis")
    
    try:
        return await execute_tool_mcp(tool_name, params)
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de l'outil {tool_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint /info (pour compatibilité avec l'ancienne API)
@app.get("/info")
async def get_info():
    """Obtient des informations sur le serveur."""
    return {
        "name": "Grist MCP Server",
        "version": "1.0.0",
        "description": "Serveur MCP pour Grist"
    }

# Implémentation des outils
async def list_orgs():
    """Liste toutes les organisations Grist."""
    try:
        response = await client.get(f"{GRIST_API_URL}/orgs")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des organisations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def list_workspaces(org_id):
    """Liste tous les espaces de travail d'une organisation."""
    try:
        response = await client.get(f"{GRIST_API_URL}/orgs/{org_id}/workspaces")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des espaces de travail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def list_docs(org_id, workspace_id):
    """Liste tous les documents d'un espace de travail."""
    try:
        response = await client.get(f"{GRIST_API_URL}/orgs/{org_id}/workspaces/{workspace_id}/docs")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def list_tables(doc_id):
    """Liste toutes les tables d'un document."""
    try:
        response = await client.get(f"{GRIST_API_URL}/docs/{doc_id}/tables")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des tables: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def list_records(doc_id, table_id, limit=10):
    """Liste les enregistrements d'une table."""
    try:
        params = {}
        if limit:
            params["limit"] = limit
            
        response = await client.get(f"{GRIST_API_URL}/docs/{doc_id}/tables/{table_id}/records", params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des enregistrements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def add_record(doc_id, table_id, fields):
    """Ajoute un enregistrement à une table."""
    try:
        response = await client.post(
            f"{GRIST_API_URL}/docs/{doc_id}/tables/{table_id}/records",
            json={"records": [{"fields": fields}]}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout d'un enregistrement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def update_record(doc_id, table_id, record_id, fields):
    """Met à jour un enregistrement dans une table."""
    try:
        response = await client.patch(
            f"{GRIST_API_URL}/docs/{doc_id}/tables/{table_id}/records/{record_id}",
            json={"fields": fields}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour d'un enregistrement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def delete_record(doc_id, table_id, record_id):
    """Supprime un enregistrement d'une table."""
    try:
        response = await client.delete(
            f"{GRIST_API_URL}/docs/{doc_id}/tables/{table_id}/records/{record_id}"
        )
        response.raise_for_status()
        return {"status": "success", "message": f"Enregistrement {record_id} supprimé"}
    except Exception as e:
        logger.error(f"Erreur lors de la suppression d'un enregistrement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def execute_query(doc_id, query):
    """Exécute une requête SQL sur un document."""
    try:
        response = await client.post(
            f"{GRIST_API_URL}/docs/{doc_id}/sql",
            json={"sql": query}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution d'une requête SQL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Point d'entrée
if __name__ == "__main__":
    import uvicorn
    logger.info(f"Démarrage du serveur Grist MCP sur {MCP_HOST}:{MCP_PORT}")
    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT) 