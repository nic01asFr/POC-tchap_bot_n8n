#!/usr/bin/env python3
"""
Grist MCP Server - Provides MCP tools for interacting with Grist API

This server implements the Model Context Protocol (MCP) for Grist,
enabling language models to interact with Grist spreadsheets.
"""

import json
import os
import logging
import sys
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, AnyHttpUrl
from dotenv import load_dotenv

# Version
__version__ = "0.1.0"

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level, logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("grist_mcp")

# Variable globale pour le client Grist
grist_client = None

# Load environment variables from .env file
load_dotenv("grist_mcp.env")

# Mask sensitive information
def mask_api_key(api_key: str) -> str:
    """Mask the API key for logging purposes"""
    if len(api_key) > 10:
        return f"{api_key[:5]}...{api_key[-5:]}"
    return "[SET]"

# Create the FastAPI app
app = FastAPI(
    title="Grist MCP Server",
    description="Serveur MCP pour Grist",
    version=__version__
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration from environment
GRIST_API_KEY = os.getenv("GRIST_API_KEY")
GRIST_API_URL = os.getenv("GRIST_API_URL", "https://grist.numerique.gouv.fr/api")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8083"))

# Configuration
class GristConfig(BaseModel):
    """Configuration for Grist API client"""
    api_key: str = Field(..., description="Grist API Key")
    api_url: AnyHttpUrl = Field(default="https://grist.numerique.gouv.fr/api")

# Models
class GristOrg(BaseModel):
    """Grist organization model"""
    id: int
    name: str
    domain: Optional[str] = None

class GristWorkspace(BaseModel):
    """Grist workspace model"""
    id: int
    name: str

class GristDocument(BaseModel):
    """Grist document model"""
    id: str
    name: str
    
class GristTable(BaseModel):
    """Grist table model"""
    id: str
    
class GristColumn(BaseModel):
    """Grist column model"""
    id: str
    fields: Dict[str, Any]

class GristRecord(BaseModel):
    """Grist record model"""
    id: int
    fields: Dict[str, Any]

# Client
class GristClient:
    """Client for the Grist API"""
    
    def __init__(self, api_key: str, api_url: str):
        self.api_key = api_key
        self.api_url = api_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        logger.debug(f"GristClient initialized with API URL: {api_url}")
        logger.debug(f"API key: {mask_api_key(api_key)}")
    
    async def _request(self, 
                      method: str, 
                      endpoint: str, 
                      json_data: Optional[Dict[str, Any]] = None,
                      params: Optional[Dict[str, Any]] = None) -> Any:
        """Make a request to the Grist API"""
        # Fix URL construction: ensure endpoint starts with / and base URL doesn't end with /
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        api_url = self.api_url.rstrip('/')
        url = api_url + endpoint
        
        logger.debug(f"Making {method} request to {url}")
        if params:
            logger.debug(f"Params: {params}")
        if json_data:
            logger.debug(f"JSON data: {json.dumps(json_data)[:200]}...")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:  # Set a reasonable timeout
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=json_data,
                    params=params
                )
                
                logger.debug(f"Response status: {response.status_code}")
                
                # Handle error responses
                if response.status_code >= 400:
                    error_text = response.text
                    logger.error(f"Error response ({response.status_code}): {error_text[:500]}")
                    response.raise_for_status()  # Raise HTTP error if any
                
                # Parse response JSON
                response_json = response.json()
                logger.debug(f"Response data: {json.dumps(response_json)[:200]}...")
                return response_json
                
        except httpx.TimeoutException:
            logger.error(f"Request to {url} timed out")
            raise Exception("Request timed out")
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {str(e)}")
            raise Exception(f"Request error: {str(e)}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP status error for {url}: {str(e)}")
            raise Exception(f"HTTP status error: {str(e)}")
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON response from {url}")
            raise Exception("Invalid JSON response")
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {str(e)}")
            raise Exception(f"Unexpected error: {str(e)}")
    
    async def list_orgs(self) -> List[GristOrg]:
        """List all Grist organizations"""
        try:
            data = await self._request("GET", "/orgs")
            return data
        except Exception as e:
            logger.error(f"Failed to list organizations: {str(e)}")
            raise

    async def list_workspaces(self, org_id: Union[int, str]) -> List[GristWorkspace]:
        """List workspaces for an organization"""
        try:
            data = await self._request("GET", f"/orgs/{org_id}/workspaces")
            return data
        except Exception as e:
            logger.error(f"Failed to list workspaces for org {org_id}: {str(e)}")
            raise

    async def list_documents(self, workspace_id: int) -> List[GristDocument]:
        """List documents for a workspace"""
        try:
            # Current API endpoint format may vary
            data = await self._request("GET", f"/workspaces/{workspace_id}/docs")
            return data
        except Exception as e:
            logger.error(f"Failed to list documents for workspace {workspace_id}: {str(e)}")
            raise

    async def list_tables(self, doc_id: str) -> List[GristTable]:
        """List tables for a document"""
        try:
            data = await self._request("GET", f"/docs/{doc_id}/tables")
            return data
        except Exception as e:
            logger.error(f"Failed to list tables for document {doc_id}: {str(e)}")
            raise

    async def list_columns(self, doc_id: str, table_id: str) -> List[GristColumn]:
        """List columns for a table"""
        try:
            data = await self._request("GET", f"/docs/{doc_id}/tables/{table_id}/columns")
            return data
        except Exception as e:
            logger.error(f"Failed to list columns for table {table_id} in document {doc_id}: {str(e)}")
            raise

    async def list_records(self, doc_id: str, table_id: str, 
                        sort: Optional[str] = None,
                        limit: Optional[int] = None) -> List[GristRecord]:
        """List records for a table"""
        try:
            params = {}
            if sort:
                params["sort"] = sort
            if limit:
                params["limit"] = limit
                
            data = await self._request("GET", f"/docs/{doc_id}/tables/{table_id}/records", params=params)
            return data
        except Exception as e:
            logger.error(f"Failed to list records for table {table_id} in document {doc_id}: {str(e)}")
            raise

    async def add_records(self, doc_id: str, table_id: str, 
                       records: List[Dict[str, Any]]) -> List[int]:
        """Add records to a table"""
        try:
            # Format records as expected by the API
            formatted_records = []
            for record in records:
                formatted_records.append({"fields": record})
                
            data = await self._request(
                "POST", 
                f"/docs/{doc_id}/tables/{table_id}/records", 
                json_data={"records": formatted_records}
            )
            
            # Extract and return record IDs
            record_ids = []
            if "records" in data:
                record_ids = [record.get("id") for record in data["records"]]
            return record_ids
        except Exception as e:
            logger.error(f"Failed to add records to table {table_id} in document {doc_id}: {str(e)}")
            raise

    async def update_records(self, doc_id: str, table_id: str, 
                          records: List[Dict[str, Any]]) -> List[int]:
        """Update records in a table
        
        Each record must have an 'id' field and a 'fields' dict with the fields to update
        Example:
        [
            {"id": 1, "fields": {"name": "New Name"}},
            {"id": 2, "fields": {"status": "Active"}}
        ]
        """
        try:
            # Format records as expected by the API
            formatted_records = []
            record_ids = []
            
            for record in records:
                if "id" not in record:
                    logger.error(f"Record missing 'id' field: {record}")
                    continue
                    
                record_id = record["id"]
                record_ids.append(record_id)
                fields = record.get("fields", {})
                
                # Update the record
                await self._request(
                    "PATCH", 
                    f"/docs/{doc_id}/tables/{table_id}/records/{record_id}", 
                    json_data={"fields": fields}
                )
            
            return record_ids
        except Exception as e:
            logger.error(f"Failed to update records in table {table_id} in document {doc_id}: {str(e)}")
            raise

    async def delete_records(self, doc_id: str, table_id: str, record_ids: List[int]) -> None:
        """Delete records from a table"""
        try:
            for record_id in record_ids:
                await self._request(
                    "DELETE", 
                    f"/docs/{doc_id}/tables/{table_id}/records/{record_id}"
                )
            return {"status": "success", "message": f"Deleted {len(record_ids)} records"}
        except Exception as e:
            logger.error(f"Failed to delete records from table {table_id} in document {doc_id}: {str(e)}")
            raise

def get_client(ctx: Optional[Any] = None) -> GristClient:
    """Get the Grist client instance"""
    global grist_client
    
    # Initialize client if not already done
    if grist_client is None:
        api_key = GRIST_API_KEY
        api_url = GRIST_API_URL
        
        if not api_key:
            logger.error("GRIST_API_KEY is not set")
            raise Exception("GRIST_API_KEY is not set")
        
        grist_client = GristClient(api_key=api_key, api_url=api_url)
        logger.info(f"Client Grist initialisé avec succès pour {api_url}")
    
    return grist_client

# === MCP Protocol Endpoints ===

@app.get("/mcp/info")
async def mcp_info():
    """Information about this MCP server"""
    return {
        "name": "Grist MCP Server",
        "version": __version__,
        "provider": "Grist",
        "protocolVersion": "1.0",
        "supportedFeatures": ["tools"],
        "description": "Serveur MCP pour l'intégration avec Grist"
    }

@app.get("/mcp/")
async def mcp_root():
    """Root MCP endpoint"""
    return {
        "status": "online",
        "message": "Grist MCP Server is running",
        "services": ["tools"]
    }

@app.get("/mcp/tools")
async def mcp_tools():
    """List all available tools"""
    tools = await list_tools()
    return {"tools": tools}

@app.get("/mcp/schema")
async def mcp_schema():
    """Schema for MCP tools"""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Grist MCP API",
            "version": __version__,
            "description": "API pour l'intégration avec Grist"
        },
        "paths": {
            "/mcp/tools": {
                "get": {
                    "summary": "Liste tous les outils disponibles",
                    "responses": {
                        "200": {
                            "description": "Liste d'outils",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "tools": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

@app.post("/mcp")
async def mcp_request(request: Request):
    """Main MCP endpoint to handle requests"""
    try:
        config = request.query_params.get("config", "{}")
        config_dict = json.loads(config)
        body = await request.json()
        
        logger.info(f"MCP Request received: {body}")
        
        # Handle different MCP request types
        if body.get("type") == "tools.list":
            # List available tools
            tools = await list_tools()
            return {"tools": tools}
            
        elif body.get("type") == "tools.execute":
            # Execute a tool
            tool_name = body.get("name")
            params = body.get("params", {})
            
            logger.info(f"Executing tool {tool_name} with params {params}")
            
            result = await execute_tool(tool_name, params)
            return {"result": result}
            
        else:
            return {
                "error": "Unsupported MCP request type",
                "type": body.get("type")
            }
    except Exception as e:
        logger.error(f"Error processing MCP request: {str(e)}")
        return {"error": str(e)}

# Tool functions

async def list_tools():
    """List all available tools"""
    return [
        {
            "name": "list_organizations",
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
            "name": "list_documents",
            "description": "Liste tous les documents d'un espace de travail",
            "parameters": [
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
            "name": "list_columns",
            "description": "Liste toutes les colonnes d'une table",
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
                },
                {
                    "name": "sort",
                    "type": "string",
                    "description": "Champ pour trier les résultats",
                    "required": False
                }
            ]
        },
        {
            "name": "add_grist_records",
            "description": "Ajoute des enregistrements à une table",
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
                    "name": "records",
                    "type": "array",
                    "description": "Liste des enregistrements à ajouter",
                    "required": True
                }
            ]
        },
        {
            "name": "update_grist_records",
            "description": "Met à jour des enregistrements dans une table",
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
                    "name": "records",
                    "type": "array",
                    "description": "Liste des enregistrements à mettre à jour avec ID",
                    "required": True
                }
            ]
        },
        {
            "name": "delete_grist_records",
            "description": "Supprime des enregistrements d'une table",
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
                    "name": "record_ids",
                    "type": "array",
                    "description": "Liste des IDs des enregistrements à supprimer",
                    "required": True
                }
            ]
        }
    ]

async def execute_tool(tool_name: str, params: Dict[str, Any]):
    """Execute a tool with the given parameters"""
    client = get_client()
    
    if tool_name == "list_organizations":
        return await client.list_orgs()
    
    elif tool_name == "list_workspaces":
        org_id = params.get("org_id")
        if not org_id:
            raise HTTPException(status_code=400, detail="Missing required parameter: org_id")
        return await client.list_workspaces(org_id)
    
    elif tool_name == "list_documents":
        workspace_id = params.get("workspace_id")
        if not workspace_id:
            raise HTTPException(status_code=400, detail="Missing required parameter: workspace_id")
        return await client.list_documents(workspace_id)
    
    elif tool_name == "list_tables":
        doc_id = params.get("doc_id")
        if not doc_id:
            raise HTTPException(status_code=400, detail="Missing required parameter: doc_id")
        return await client.list_tables(doc_id)
    
    elif tool_name == "list_columns":
        doc_id = params.get("doc_id")
        table_id = params.get("table_id")
        if not doc_id or not table_id:
            raise HTTPException(status_code=400, detail="Missing required parameters: doc_id and/or table_id")
        return await client.list_columns(doc_id, table_id)
    
    elif tool_name == "list_records":
        doc_id = params.get("doc_id")
        table_id = params.get("table_id")
        limit = params.get("limit")
        sort = params.get("sort")
        if not doc_id or not table_id:
            raise HTTPException(status_code=400, detail="Missing required parameters: doc_id and/or table_id")
        return await client.list_records(doc_id, table_id, sort, limit)
    
    elif tool_name == "add_grist_records":
        doc_id = params.get("doc_id")
        table_id = params.get("table_id")
        records = params.get("records")
        if not doc_id or not table_id or not records:
            raise HTTPException(status_code=400, detail="Missing required parameters: doc_id, table_id, and/or records")
        return await client.add_records(doc_id, table_id, records)
    
    elif tool_name == "update_grist_records":
        doc_id = params.get("doc_id")
        table_id = params.get("table_id")
        records = params.get("records")
        if not doc_id or not table_id or not records:
            raise HTTPException(status_code=400, detail="Missing required parameters: doc_id, table_id, and/or records")
        return await client.update_records(doc_id, table_id, records)
    
    elif tool_name == "delete_grist_records":
        doc_id = params.get("doc_id")
        table_id = params.get("table_id")
        record_ids = params.get("record_ids")
        if not doc_id or not table_id or not record_ids:
            raise HTTPException(status_code=400, detail="Missing required parameters: doc_id, table_id, and/or record_ids")
        return await client.delete_records(doc_id, table_id, record_ids)
    
    else:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

# Legacy API endpoints for compatibility
@app.get("/tools")
async def tools_list():
    """List all available tools (legacy endpoint)"""
    return await list_tools()

@app.post("/execute")
async def execute_tool_legacy(request: Dict[str, Any]):
    """Execute a tool (legacy endpoint)"""
    tool = request.get("tool")
    params = request.get("params", {})
    
    if not tool:
        raise HTTPException(status_code=400, detail="Missing tool name")
    
    try:
        return await execute_tool(tool, params)
    except Exception as e:
        logger.error(f"Error executing tool {tool}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Grist MCP Server",
        "version": __version__,
        "description": "Server that provides MCP access to Grist API",
        "endpoints": [
            "/mcp/info",
            "/mcp/",
            "/mcp",
            "/tools",
            "/execute"
        ]
    }

if __name__ == "__main__":
    try:
        logger.info(f"Starting Grist MCP Server v{__version__}")
        
        # Log configuration
        env_config = {
            "GRIST_API_KEY": mask_api_key(GRIST_API_KEY),
            "GRIST_API_URL": GRIST_API_URL,
            "GRIST_API_HOST": os.getenv("GRIST_API_HOST", ""),
            "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
            "MCP_HOST": MCP_HOST,
            "MCP_PORT": MCP_PORT,
            "FASTMCP_HOST": os.getenv("FASTMCP_HOST", ""),
            "FASTMCP_PORT": os.getenv("FASTMCP_PORT", "")
        }
        logger.info(f"Environment configuration: {env_config}")
        
        # Initialize client
        get_client()
        
        # Start server
        import uvicorn
        logger.info(f"Démarrage du serveur MCP sur {MCP_HOST}:{MCP_PORT}")
        uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)
        
    except Exception as e:
        logger.error(f"Failed to start Grist MCP Server: {str(e)}")
        sys.exit(1) 