#!/usr/bin/env python3
"""
Client MCP pour le serveur Grist en utilisant la bibliothèque fastmcp.
"""
import asyncio
import json
import sys
import os
import logging
import argparse

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("grist_mcp_client")

# Chemins relatifs
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "..", "conf", "mcp_servers.json")

def load_servers():
    """Charge les serveurs enregistrés depuis le fichier JSON."""
    try:
        with open(CONFIG_PATH, "r") as f:
            servers = json.load(f)
        return servers
    except Exception as e:
        logger.error(f"Erreur lors du chargement des serveurs: {e}")
        return None

def get_grist_server():
    """Récupère la configuration du serveur Grist MCP."""
    servers = load_servers()
    if not servers:
        return None
    
    return servers.get("grist-mcp")

async def execute_grist_mcp_operation(hostname, port, operation, parameters=None):
    """
    Exécute une opération sur le serveur MCP Grist en utilisant fastmcp.client.
    
    Note: Assurez-vous d'avoir installé la bibliothèque fastmcp:
    pip install fastmcp
    """
    try:
        # Import conditionnel de fastmcp pour éviter les erreurs si non installé
        try:
            from fastmcp.client import MCPClient
        except ImportError:
            logger.error("La bibliothèque fastmcp n'est pas installée. Exécutez 'pip install fastmcp'.")
            return None
        
        if parameters is None:
            parameters = {}
        
        logger.info(f"Connexion au serveur MCP: {hostname}:{port}")
        logger.info(f"Exécution de l'opération: {operation}")
        logger.info(f"Avec les paramètres: {json.dumps(parameters, indent=2)}")
        
        # Créer le client MCP
        client = MCPClient(hostname, port)
        
        # Exécuter l'opération
        result = await client.execute(operation, parameters)
        
        logger.info(f"Résultat de l'opération: {json.dumps(result, indent=2)}")
        return result
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de l'opération MCP: {e}")
        return None

async def main_async():
    """Fonction principale asynchrone."""
    parser = argparse.ArgumentParser(description="Client MCP pour le serveur Grist")
    parser.add_argument("--operation", "-o", default="list_organizations",
                        help="Opération à exécuter (par défaut: list_organizations)")
    parser.add_argument("--doc-id", "-d",
                        help="ID du document Grist (pour les opérations list_tables, get_table_data, etc.)")
    parser.add_argument("--table-id", "-t",
                        help="ID de la table Grist (pour les opérations get_table_data, etc.)")
    
    args = parser.parse_args()
    
    # Construire les paramètres en fonction des arguments
    parameters = {}
    if args.doc_id:
        parameters["doc_id"] = args.doc_id
    if args.table_id:
        parameters["table_id"] = args.table_id
    
    # Récupérer la configuration du serveur Grist MCP
    server_config = get_grist_server()
    if not server_config:
        logger.error("Impossible de trouver la configuration du serveur Grist MCP")
        return 1
    
    # Extraire l'hôte et le port de l'URL
    url = server_config["url"]
    if url.startswith("http://"):
        url = url[7:]
    elif url.startswith("https://"):
        url = url[8:]
    
    parts = url.split(":")
    hostname = parts[0]
    port = int(parts[1]) if len(parts) > 1 else 80
    
    # Exécuter l'opération MCP
    result = await execute_grist_mcp_operation(hostname, port, args.operation, parameters)
    
    # Retourner le code de statut
    return 0 if result is not None else 1

def main():
    """Fonction principale."""
    return asyncio.run(main_async())

if __name__ == "__main__":
    sys.exit(main()) 