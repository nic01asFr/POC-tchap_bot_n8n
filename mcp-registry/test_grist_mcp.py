#!/usr/bin/env python
"""
Script de test pour interagir avec le serveur Grist MCP.

Ce script démontre comment utiliser le MCP Registry pour interagir avec 
le serveur Grist MCP démarré par Claude Desktop.
"""

import argparse
import asyncio
import json
import logging
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

logger = logging.getLogger("grist_mcp_test")

# Ajuster le chemin pour importer les modules du package
sys.path.insert(0, str(Path(__file__).parent))

# Importer après avoir ajusté le chemin
from app.core.registry import MCPRegistry

async def list_organizations(registry):
    """Liste les organisations Grist disponibles."""
    logger.info("Recherche d'outils pour lister les organisations...")
    
    # Rechercher l'outil de liste des organisations
    tools = await registry.search_tools("list organizations grist", limit=5)
    
    if not tools:
        logger.error("Aucun outil trouvé pour lister les organisations")
        return []
        
    # Sélectionner l'outil le plus pertinent
    tool = tools[0]
    server_id = tool["server_id"]
    tool_id = tool["id"]
    
    logger.info(f"Exécution de l'outil {tool['name']} ({tool_id})...")
    
    # Exécuter l'outil
    result = await registry.execute_tool(server_id, tool_id, {})
    
    if "error" in result:
        logger.error(f"Erreur lors de l'exécution de l'outil : {result['error']}")
        return []
        
    logger.info(f"Organisations trouvées : {len(result)}")
    
    return result

async def list_workspaces(registry, org_id):
    """Liste les espaces de travail d'une organisation Grist."""
    logger.info(f"Recherche d'outils pour lister les espaces de travail pour l'organisation {org_id}...")
    
    # Rechercher l'outil de liste des espaces de travail
    tools = await registry.search_tools("list workspaces grist", limit=5)
    
    if not tools:
        logger.error("Aucun outil trouvé pour lister les espaces de travail")
        return []
        
    # Sélectionner l'outil le plus pertinent
    tool = tools[0]
    server_id = tool["server_id"]
    tool_id = tool["id"]
    
    logger.info(f"Exécution de l'outil {tool['name']} ({tool_id})...")
    
    # Exécuter l'outil
    result = await registry.execute_tool(server_id, tool_id, {"org_id": org_id})
    
    if "error" in result:
        logger.error(f"Erreur lors de l'exécution de l'outil : {result['error']}")
        return []
        
    logger.info(f"Espaces de travail trouvés : {len(result)}")
    
    return result

async def list_documents(registry, workspace_id):
    """Liste les documents d'un espace de travail Grist."""
    logger.info(f"Recherche d'outils pour lister les documents pour l'espace de travail {workspace_id}...")
    
    # Rechercher l'outil de liste des documents
    tools = await registry.search_tools("list documents grist", limit=5)
    
    if not tools:
        logger.error("Aucun outil trouvé pour lister les documents")
        return []
        
    # Sélectionner l'outil le plus pertinent
    tool = tools[0]
    server_id = tool["server_id"]
    tool_id = tool["id"]
    
    logger.info(f"Exécution de l'outil {tool['name']} ({tool_id})...")
    
    # Exécuter l'outil
    result = await registry.execute_tool(server_id, tool_id, {"workspace_id": workspace_id})
    
    if "error" in result:
        logger.error(f"Erreur lors de l'exécution de l'outil : {result['error']}")
        return []
        
    logger.info(f"Documents trouvés : {len(result)}")
    
    return result

async def list_tables(registry, doc_id):
    """Liste les tables d'un document Grist."""
    logger.info(f"Recherche d'outils pour lister les tables pour le document {doc_id}...")
    
    # Rechercher l'outil de liste des tables
    tools = await registry.search_tools("list tables grist", limit=5)
    
    if not tools:
        logger.error("Aucun outil trouvé pour lister les tables")
        return []
        
    # Sélectionner l'outil le plus pertinent
    tool = tools[0]
    server_id = tool["server_id"]
    tool_id = tool["id"]
    
    logger.info(f"Exécution de l'outil {tool['name']} ({tool_id})...")
    
    # Exécuter l'outil
    result = await registry.execute_tool(server_id, tool_id, {"doc_id": doc_id})
    
    if "error" in result:
        logger.error(f"Erreur lors de l'exécution de l'outil : {result['error']}")
        return []
        
    logger.info(f"Tables trouvées : {len(result)}")
    
    return result

async def list_records(registry, doc_id, table_id, limit=10):
    """Liste les enregistrements d'une table Grist."""
    logger.info(f"Recherche d'outils pour lister les enregistrements pour la table {table_id}...")
    
    # Rechercher l'outil de liste des enregistrements
    tools = await registry.search_tools("list records grist", limit=5)
    
    if not tools:
        logger.error("Aucun outil trouvé pour lister les enregistrements")
        return []
        
    # Sélectionner l'outil le plus pertinent
    tool = tools[0]
    server_id = tool["server_id"]
    tool_id = tool["id"]
    
    logger.info(f"Exécution de l'outil {tool['name']} ({tool_id})...")
    
    # Exécuter l'outil
    result = await registry.execute_tool(
        server_id, 
        tool_id, 
        {
            "doc_id": doc_id,
            "table_id": table_id,
            "limit": limit
        }
    )
    
    if "error" in result:
        logger.error(f"Erreur lors de l'exécution de l'outil : {result['error']}")
        return []
        
    logger.info(f"Enregistrements trouvés : {len(result)}")
    
    return result

async def main():
    """Fonction principale du script de test."""
    parser = argparse.ArgumentParser(description="Test du serveur Grist MCP")
    parser.add_argument("--action", choices=["list-orgs", "list-workspaces", "list-docs", "list-tables", "list-records", "full"],
                        default="list-orgs", help="Action à effectuer")
    parser.add_argument("--org-id", type=int, help="ID de l'organisation")
    parser.add_argument("--workspace-id", type=int, help="ID de l'espace de travail")
    parser.add_argument("--doc-id", help="ID du document")
    parser.add_argument("--table-id", help="ID de la table")
    
    args = parser.parse_args()
    
    logger.info("Initialisation du MCP Registry...")
    registry = MCPRegistry()
    
    try:
        # Démarrer le registre sans gérer les serveurs (on suppose que Claude Desktop les a déjà démarrés)
        await registry.start()
        
        # Vérifier si des serveurs sont disponibles
        servers = await registry.get_servers()
        if not servers:
            logger.error("Aucun serveur MCP disponible. Assurez-vous que Claude Desktop est en cours d'exécution.")
            return
            
        logger.info(f"Serveurs disponibles : {len(servers)}")
        for server in servers:
            logger.info(f"  - {server['name']} ({server['id']})")
            
        # Exécuter l'action demandée
        if args.action == "list-orgs" or args.action == "full":
            logger.info("=== Liste des organisations ===")
            orgs = await list_organizations(registry)
            
            if not orgs:
                return
                
            for org in orgs:
                logger.info(f"  - {org['name']} (ID: {org['id']}, domaine: {org['domain']})")
                
            # Mémoriser le premier ID d'organisation pour les actions suivantes
            org_id = orgs[0]["id"] if orgs else None
        else:
            org_id = args.org_id
            
        if (args.action == "list-workspaces" or args.action == "full") and org_id:
            logger.info(f"=== Liste des espaces de travail pour l'organisation {org_id} ===")
            workspaces = await list_workspaces(registry, org_id)
            
            if not workspaces:
                return
                
            for workspace in workspaces:
                logger.info(f"  - {workspace['name']} (ID: {workspace['id']})")
                
            # Mémoriser le premier ID d'espace de travail pour les actions suivantes
            workspace_id = workspaces[0]["id"] if workspaces else None
        else:
            workspace_id = args.workspace_id
            
        if (args.action == "list-docs" or args.action == "full") and workspace_id:
            logger.info(f"=== Liste des documents pour l'espace de travail {workspace_id} ===")
            docs = await list_documents(registry, workspace_id)
            
            if not docs:
                return
                
            for doc in docs:
                logger.info(f"  - {doc['name']} (ID: {doc['id']})")
                
            # Mémoriser le premier ID de document pour les actions suivantes
            doc_id = docs[0]["id"] if docs else None
        else:
            doc_id = args.doc_id
            
        if (args.action == "list-tables" or args.action == "full") and doc_id:
            logger.info(f"=== Liste des tables pour le document {doc_id} ===")
            tables = await list_tables(registry, doc_id)
            
            if not tables:
                return
                
            for table in tables:
                logger.info(f"  - {table['id']} (colonnes: {len(table.get('columns', []))})")
                
            # Mémoriser le premier ID de table pour les actions suivantes
            table_id = tables[0]["id"] if tables else None
        else:
            table_id = args.table_id
            
        if (args.action == "list-records" or args.action == "full") and doc_id and table_id:
            logger.info(f"=== Liste des enregistrements pour la table {table_id} du document {doc_id} ===")
            records = await list_records(registry, doc_id, table_id, limit=5)
            
            if not records:
                return
                
            for i, record in enumerate(records):
                logger.info(f"  - Enregistrement {i+1}: {json.dumps(record)}")
                
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du test : {str(e)}")
    finally:
        # Arrêter proprement le registre
        await registry.stop()

if __name__ == "__main__":
    asyncio.run(main()) 