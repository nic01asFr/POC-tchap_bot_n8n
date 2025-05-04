#!/usr/bin/env python3
"""
Script pour tester la connexion à un serveur MCP.
Suivant le standard MCP (Model Context Protocol).
"""
import asyncio
import json
import base64
import httpx
import yaml
import sys
import os
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_client_test")

# Chemins relatifs
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "..", "conf", "config.yaml")

async def load_config():
    """Charge la configuration depuis le fichier YAML."""
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error(f"Erreur lors du chargement de la configuration: {e}")
        return None

async def test_mcp_connection(server_url):
    """Teste la connexion à un serveur MCP en utilisant le protocole standard."""
    logger.info(f"Test de connexion au serveur MCP: {server_url}")
    
    # Configuration à envoyer au serveur MCP
    config = {
        "client_id": "mcp-registry-test",
        "client_version": "1.0.0"
    }
    
    # Encoder la configuration en base64
    config_base64 = base64.b64encode(json.dumps(config).encode()).decode()
    
    # Construire l'URL complète avec la configuration
    full_url = f"{server_url}?config={config_base64}"
    
    # En-têtes pour la requête
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        # Démarrer une session HTTP pour le streaming
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", full_url, headers=headers, json={
                "type": "init",
                "body": {}
            }) as response:
                logger.info(f"Statut de la réponse: {response.status_code}")
                
                if response.status_code != 200:
                    logger.error(f"Erreur de connexion: {response.status_code}")
                    return False
                
                # Lire et traiter les réponses en streaming
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            message = json.loads(line)
                            logger.info(f"Reçu: {message['type']}")
                            
                            # Si on reçoit la liste des outils, le test est réussi
                            if message["type"] == "tools":
                                logger.info(f"Serveur MCP opérationnel. Outils disponibles: {len(message['body'])}")
                                return True
                        except json.JSONDecodeError:
                            logger.warning(f"Ligne non-JSON reçue: {line}")
        
        return False
    except Exception as e:
        logger.error(f"Erreur lors de la connexion au serveur MCP: {e}")
        return False

async def main():
    """Fonction principale."""
    # Charger la configuration
    config = await load_config()
    if not config:
        logger.error("Impossible de charger la configuration.")
        sys.exit(1)
    
    # Récupérer les URLs des serveurs MCP
    server_urls = config.get("registry", {}).get("server_urls", [])
    if not server_urls:
        logger.error("Aucun serveur MCP configuré.")
        sys.exit(1)
    
    logger.info(f"Serveurs MCP à tester: {len(server_urls)}")
    
    # Tester chaque serveur MCP
    results = []
    for url in server_urls:
        result = await test_mcp_connection(url)
        results.append((url, result))
    
    # Afficher les résultats
    logger.info("=== Résultats des tests ===")
    for url, result in results:
        status = "✅ Opérationnel" if result else "❌ Non opérationnel"
        logger.info(f"{url}: {status}")
    
    # Compter les serveurs opérationnels
    operational = sum(1 for _, result in results if result)
    logger.info(f"Serveurs opérationnels: {operational}/{len(server_urls)}")

if __name__ == "__main__":
    asyncio.run(main()) 