#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour installer un serveur MCP.

Ce script aide à installer et configurer des serveurs MCP pour différents services
comme Grist, GitHub, le système de fichiers, etc.
"""

import os
import sys
import argparse
import json
import shutil
from pathlib import Path
import subprocess
import platform

def create_directory(path):
    """Crée un répertoire s'il n'existe pas déjà."""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Répertoire créé : {path}")
    else:
        print(f"Le répertoire {path} existe déjà")

def get_server_template(server_type):
    """Retourne le template pour un type de serveur spécifique."""
    templates = {
        "grist": {
            "requirements": [
                "fastapi==0.95.1",
                "uvicorn==0.22.0",
                "pydantic==1.10.7",
                "httpx==0.24.0",
                "python-dotenv==1.0.0"
            ],
            "env": [
                "GRIST_API_KEY=",
                "GRIST_API_URL=https://docs.getgrist.com/api",
                "MCP_HOST=0.0.0.0",
                "MCP_PORT=8083"
            ],
            "code": """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
Serveur MCP pour Grist.

Ce serveur expose les fonctionnalités de Grist via le protocole MCP.
\"\"\"

import os
import json
import logging
from typing import Dict, Any, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Body
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
GRIST_API_URL = os.getenv("GRIST_API_URL", "https://docs.getgrist.com/api")
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

# Outils MCP
@app.get("/tools")
async def list_tools():
    """Liste tous les outils MCP disponibles."""
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
            "description": "Met à jour un enregistrement",
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
            "description": "Supprime un enregistrement",
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

@app.post("/execute")
async def execute_tool(request: Dict[str, Any]):
    """
    Exécute un outil MCP.
    
    Format de la requête: {"name": "nom_outil", "parameters": {"param1": "valeur1", ...}}
    """
    tool_name = request.get("name")
    parameters = request.get("parameters", {})
    
    if not tool_name:
        raise HTTPException(status_code=400, detail="Nom de l'outil manquant")
    
    # Router vers la fonction appropriée
    if tool_name == "list_orgs":
        return await list_orgs()
    elif tool_name == "list_workspaces":
        return await list_workspaces(parameters.get("org_id"))
    elif tool_name == "list_docs":
        return await list_docs(parameters.get("org_id"), parameters.get("workspace_id"))
    elif tool_name == "list_tables":
        return await list_tables(parameters.get("doc_id"))
    elif tool_name == "list_records":
        return await list_records(
            parameters.get("doc_id"), 
            parameters.get("table_id"),
            parameters.get("limit", 10)
        )
    elif tool_name == "add_record":
        return await add_record(
            parameters.get("doc_id"),
            parameters.get("table_id"),
            parameters.get("fields", {})
        )
    elif tool_name == "update_record":
        return await update_record(
            parameters.get("doc_id"),
            parameters.get("table_id"),
            parameters.get("record_id"),
            parameters.get("fields", {})
        )
    elif tool_name == "delete_record":
        return await delete_record(
            parameters.get("doc_id"),
            parameters.get("table_id"),
            parameters.get("record_id")
        )
    elif tool_name == "execute_query":
        return await execute_query(
            parameters.get("doc_id"),
            parameters.get("query")
        )
    else:
        raise HTTPException(status_code=404, detail=f"Outil {tool_name} non trouvé")

@app.get("/info")
async def get_info():
    """Retourne les informations sur le serveur MCP."""
    return {
        "name": "Grist MCP Server",
        "description": "Serveur MCP pour Grist",
        "version": "1.0.0",
        "features": {
            "tools": True
        }
    }

# Implémentation des outils
async def list_orgs():
    """Liste toutes les organisations Grist."""
    try:
        response = await client.get(f"{GRIST_API_URL}/orgs")
        response.raise_for_status()
        orgs = response.json()
        return {"orgs": orgs}
    except httpx.HTTPError as e:
        logger.error(f"Erreur lors de la récupération des organisations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def list_workspaces(org_id):
    """Liste tous les espaces de travail d'une organisation."""
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id requis")
    
    try:
        response = await client.get(f"{GRIST_API_URL}/orgs/{org_id}/workspaces")
        response.raise_for_status()
        workspaces = response.json()
        return {"workspaces": workspaces}
    except httpx.HTTPError as e:
        logger.error(f"Erreur lors de la récupération des espaces de travail: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def list_docs(org_id, workspace_id):
    """Liste tous les documents d'un espace de travail."""
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id requis")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id requis")
    
    try:
        response = await client.get(f"{GRIST_API_URL}/orgs/{org_id}/workspaces/{workspace_id}/docs")
        response.raise_for_status()
        docs = response.json()
        return {"docs": docs}
    except httpx.HTTPError as e:
        logger.error(f"Erreur lors de la récupération des documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def list_tables(doc_id):
    """Liste toutes les tables d'un document."""
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id requis")
    
    try:
        response = await client.get(f"{GRIST_API_URL}/docs/{doc_id}/tables")
        response.raise_for_status()
        tables = response.json()
        return {"tables": tables}
    except httpx.HTTPError as e:
        logger.error(f"Erreur lors de la récupération des tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def list_records(doc_id, table_id, limit=10):
    """Liste les enregistrements d'une table."""
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id requis")
    if not table_id:
        raise HTTPException(status_code=400, detail="table_id requis")
    
    try:
        response = await client.get(
            f"{GRIST_API_URL}/docs/{doc_id}/tables/{table_id}/records",
            params={"limit": limit}
        )
        response.raise_for_status()
        records = response.json()
        return {"records": records}
    except httpx.HTTPError as e:
        logger.error(f"Erreur lors de la récupération des enregistrements: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def add_record(doc_id, table_id, fields):
    """Ajoute un enregistrement à une table."""
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id requis")
    if not table_id:
        raise HTTPException(status_code=400, detail="table_id requis")
    if not fields:
        raise HTTPException(status_code=400, detail="fields requis")
    
    try:
        response = await client.post(
            f"{GRIST_API_URL}/docs/{doc_id}/tables/{table_id}/records",
            json={"records": [{"fields": fields}]}
        )
        response.raise_for_status()
        result = response.json()
        return {"result": result}
    except httpx.HTTPError as e:
        logger.error(f"Erreur lors de l'ajout de l'enregistrement: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def update_record(doc_id, table_id, record_id, fields):
    """Met à jour un enregistrement."""
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id requis")
    if not table_id:
        raise HTTPException(status_code=400, detail="table_id requis")
    if not record_id:
        raise HTTPException(status_code=400, detail="record_id requis")
    if not fields:
        raise HTTPException(status_code=400, detail="fields requis")
    
    try:
        response = await client.patch(
            f"{GRIST_API_URL}/docs/{doc_id}/tables/{table_id}/records/{record_id}",
            json={"fields": fields}
        )
        response.raise_for_status()
        result = response.json()
        return {"result": result}
    except httpx.HTTPError as e:
        logger.error(f"Erreur lors de la mise à jour de l'enregistrement: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def delete_record(doc_id, table_id, record_id):
    """Supprime un enregistrement."""
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id requis")
    if not table_id:
        raise HTTPException(status_code=400, detail="table_id requis")
    if not record_id:
        raise HTTPException(status_code=400, detail="record_id requis")
    
    try:
        response = await client.delete(
            f"{GRIST_API_URL}/docs/{doc_id}/tables/{table_id}/records/{record_id}"
        )
        response.raise_for_status()
        return {"success": True}
    except httpx.HTTPError as e:
        logger.error(f"Erreur lors de la suppression de l'enregistrement: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def execute_query(doc_id, query):
    """Exécute une requête SQL sur un document."""
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id requis")
    if not query:
        raise HTTPException(status_code=400, detail="query requis")
    
    try:
        response = await client.post(
            f"{GRIST_API_URL}/docs/{doc_id}/sql",
            json={"q": query}
        )
        response.raise_for_status()
        result = response.json()
        return {"result": result}
    except httpx.HTTPError as e:
        logger.error(f"Erreur lors de l'exécution de la requête: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Point d'entrée
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)
"""
        }
    }
    
    return templates.get(server_type, {})

def create_server_directory(server_type, target_dir):
    """Crée la structure de répertoires pour un serveur MCP."""
    template = get_server_template(server_type)
    if not template:
        print(f"Type de serveur non pris en charge : {server_type}")
        return False
    
    # Créer les répertoires
    create_directory(target_dir)
    
    # Créer requirements.txt
    if "requirements" in template:
        with open(os.path.join(target_dir, "requirements.txt"), "w") as f:
            f.write("\n".join(template["requirements"]))
            print(f"Fichier requirements.txt créé dans {target_dir}")
    
    # Créer .env
    if "env" in template:
        with open(os.path.join(target_dir, ".env"), "w") as f:
            f.write("\n".join(template["env"]))
            print(f"Fichier .env créé dans {target_dir}")
    
    # Créer serveur MCP
    if "code" in template:
        server_file = os.path.join(target_dir, f"{server_type}_mcp_server.py")
        with open(server_file, "w") as f:
            f.write(template["code"])
            print(f"Fichier {server_file} créé")
        
        # Rendre le fichier exécutable
        make_executable(server_file)
    
    # Créer Dockerfile
    create_dockerfile(server_type, target_dir)
    
    return True

def create_dockerfile(server_type, target_dir):
    """Crée un Dockerfile pour le serveur MCP."""
    dockerfile = f"""FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de dépendances
COPY requirements.txt /app/

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY {server_type}_mcp_server.py /app/
COPY .env /app/

# Exposer le port pour le serveur MCP
EXPOSE 8083

# Point d'entrée
CMD ["python", "{server_type}_mcp_server.py"]
"""
    
    with open(os.path.join(target_dir, "Dockerfile"), "w") as f:
        f.write(dockerfile)
        print(f"Dockerfile créé dans {target_dir}")
    
    # Créer docker-compose.yml
    docker_compose = f"""version: '3.8'

services:
  {server_type}-mcp:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: {server_type}-mcp
    restart: unless-stopped
    ports:
      - "8083:8083"
    volumes:
      - ./{server_type}_mcp_server.py:/app/{server_type}_mcp_server.py
      - ./.env:/app/.env
    networks:
      - mcp-network
    extra_hosts:
      - "host.docker.internal:host-gateway"

networks:
  mcp-network:
    external: true
"""
    
    with open(os.path.join(target_dir, "docker-compose.yml"), "w") as f:
        f.write(docker_compose)
        print(f"docker-compose.yml créé dans {target_dir}")

def make_executable(file_path):
    """Rendre un fichier exécutable."""
    if platform.system() != "Windows":
        mode = os.stat(file_path).st_mode
        os.chmod(file_path, mode | 0o111)  # Ajouter les droits d'exécution
        print(f"Droits d'exécution ajoutés à {file_path}")

def install_dependencies(target_dir):
    """Installe les dépendances Python."""
    requirements_file = os.path.join(target_dir, "requirements.txt")
    if os.path.exists(requirements_file):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file])
            print("Dépendances installées avec succès")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Erreur lors de l'installation des dépendances : {e}")
            return False
    else:
        print(f"Fichier {requirements_file} introuvable")
        return False

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Installer un serveur MCP")
    parser.add_argument("server_type", choices=["grist"], help="Type de serveur MCP à installer")
    parser.add_argument("--target-dir", "-d", default="./", help="Répertoire cible pour l'installation")
    parser.add_argument("--install-deps", "-i", action="store_true", help="Installer les dépendances Python")
    
    args = parser.parse_args()
    
    # Normaliser le chemin cible
    target_dir = os.path.abspath(args.target_dir)
    if args.server_type == "grist":
        target_dir = os.path.join(target_dir, "grist-mcp")
    
    # Créer la structure du serveur
    success = create_server_directory(args.server_type, target_dir)
    
    if success and args.install_deps:
        install_dependencies(target_dir)
    
    if success:
        print(f"\nServeur MCP {args.server_type} installé avec succès dans {target_dir}")
        print("\nPour démarrer le serveur :")
        print(f"1. Configurez le fichier .env dans {target_dir}")
        print(f"2. Exécutez : cd {target_dir} && python {args.server_type}_mcp_server.py")
        print("\nPour démarrer avec Docker :")
        print(f"1. Configurez le fichier .env dans {target_dir}")
        print(f"2. Exécutez : cd {target_dir} && docker-compose up -d")

if __name__ == "__main__":
    main() 