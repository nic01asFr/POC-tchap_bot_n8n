#!/usr/bin/env python3
"""
Script de test pour le serveur MCP Grist.
"""
import asyncio
import json
import sys
import os
import logging
import requests
import argparse

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_grist_mcp")

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

def test_grist_mcp_direct(server_config, operation, parameters=None):
    """Teste le serveur MCP Grist en utilisant des requêtes HTTP directes."""
    if not server_config:
        logger.error("Configuration du serveur Grist MCP non trouvée")
        return False
    
    base_url = server_config["url"]
    endpoint = server_config["mcp_endpoint"]
    
    full_url = f"{base_url}{endpoint}"
    logger.info(f"Test du serveur MCP Grist à l'URL: {full_url}")
    
    if parameters is None:
        parameters = {}
    
    try:
        # Préparer la requête MCP
        payload = {
            "name": operation,
            "parameters": parameters
        }
        
        logger.info(f"Envoi de la requête: {json.dumps(payload, indent=2)}")
        
        # Effectuer la requête
        response = requests.post(full_url, json=payload)
        
        # Vérifier la réponse
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Réponse reçue: {json.dumps(result, indent=2)}")
            return True
        else:
            logger.error(f"Erreur HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Erreur lors de la communication avec le serveur MCP Grist: {e}")
        return False

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Test du serveur MCP Grist")
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
        sys.exit(1)
    
    # Tester le serveur MCP Grist
    success = test_grist_mcp_direct(server_config, args.operation, parameters)
    
    # Retourner le code de statut
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 