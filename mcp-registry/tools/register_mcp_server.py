#!/usr/bin/env python3
"""
Script pour enregistrer manuellement un serveur MCP dans le registre.
Conforme au standard MCP (Model Context Protocol).
"""
import argparse
import json
import os
import sys
import yaml
import logging
import httpx
import asyncio
import base64

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("register_mcp_server")

# Chemins relatifs
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "..", "conf", "config.yaml")
SERVERS_PATH = os.path.join(SCRIPT_DIR, "..", "conf", "mcp_servers.json")

async def load_config():
    """Charge la configuration depuis le fichier YAML."""
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error(f"Erreur lors du chargement de la configuration: {e}")
        return None

async def load_servers():
    """Charge les serveurs enregistrés depuis le fichier JSON."""
    try:
        with open(SERVERS_PATH, "r") as f:
            # Si le fichier est vide ou ne contient pas une structure JSON valide, retourner un dictionnaire vide
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        logger.error(f"Erreur de décodage JSON pour {SERVERS_PATH}, création d'une nouvelle structure")
        return {}
    except Exception as e:
        logger.error(f"Erreur lors du chargement des serveurs: {e}")
        return {}

async def save_servers(servers):
    """Sauvegarde les serveurs dans le fichier JSON."""
    try:
        with open(SERVERS_PATH, "w") as f:
            json.dump(servers, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde des serveurs: {e}")
        return False

async def validate_mcp_server(url):
    """Valide qu'un serveur est bien un serveur MCP."""
    logger.info(f"Validation du serveur MCP: {url}")
    
    # Configuration minimale pour le test
    config = {
        "client_id": "mcp-registry-validator",
        "client_version": "1.0.0"
    }
    
    # Encoder la configuration en base64
    config_base64 = base64.b64encode(json.dumps(config).encode()).decode()
    
    # Construire l'URL complète
    full_url = f"{url}?config={config_base64}"
    
    try:
        # Tenter une requête d'initialisation MCP
        async with httpx.AsyncClient(timeout=10.0) as client:
            async with client.stream("POST", full_url, json={"type": "init", "body": {}}) as response:
                if response.status_code != 200:
                    logger.error(f"Le serveur a répondu avec le code {response.status_code}")
                    return False, None
                
                # Lire la première ligne de réponse
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            message = json.loads(line)
                            
                            # Vérifier s'il s'agit d'une réponse d'initialisation MCP valide
                            if message.get("type") == "tools":
                                tools = message.get("body", [])
                                return True, {
                                    "tool_count": len(tools),
                                    "tools": tools
                                }
                        except json.JSONDecodeError:
                            continue
                        break
        
        logger.error("Pas de réponse valide du serveur MCP")
        return False, None
    except Exception as e:
        logger.error(f"Erreur lors de la validation du serveur MCP: {e}")
        return False, None

async def register_server(args):
    """Enregistre un nouveau serveur MCP."""
    # Charger les serveurs existants
    servers = await load_servers()
    
    # Si le fichier était vide, initialiser une structure appropriée
    if not isinstance(servers, dict):
        servers = {}
    
    # Vérifier si un serveur avec cet ID existe déjà
    if args.id in servers:
        if not args.force:
            logger.error(f"Un serveur avec l'ID '{args.id}' existe déjà. Utilisez --force pour remplacer.")
            return False
        logger.warning(f"Remplacement du serveur existant avec l'ID '{args.id}'")
    
    # Valider l'URL du serveur MCP si demandé
    if args.validate:
        is_valid, details = await validate_mcp_server(args.url)
        if not is_valid:
            logger.error(f"Le serveur à l'URL '{args.url}' n'est pas un serveur MCP valide")
            return False
        logger.info(f"Serveur MCP validé. {details['tool_count']} outil(s) disponible(s).")
        
        # Ajouter les détails des outils s'ils sont disponibles
        tools = details.get("tools", [])
        capabilities = [tool.get("name") for tool in tools if tool.get("name")]
    else:
        capabilities = args.capabilities or []
    
    # Construire la configuration du serveur
    server_config = {
        "name": args.name,
        "description": args.description,
        "url": args.url,
        "mcp_endpoint": args.endpoint,
        "capabilities": capabilities,
        "metadata": {
            "manual_registration": True,
            "registration_date": datetime.datetime.now().isoformat()
        }
    }
    
    # Ajouter le serveur à la configuration
    servers[args.id] = server_config
    
    # Sauvegarder la configuration mise à jour
    if await save_servers(servers):
        logger.info(f"Serveur MCP '{args.name}' enregistré avec succès avec l'ID '{args.id}'")
        return True
    else:
        logger.error("Échec de l'enregistrement du serveur MCP")
        return False

def parse_args():
    """Parse les arguments de ligne de commande."""
    parser = argparse.ArgumentParser(description="Enregistre un serveur MCP dans le registre")
    
    parser.add_argument("--id", "-i", required=True,
                        help="Identifiant unique du serveur MCP")
    parser.add_argument("--name", "-n", required=True,
                        help="Nom convivial du serveur MCP")
    parser.add_argument("--description", "-d", default="",
                        help="Description du serveur MCP")
    parser.add_argument("--url", "-u", required=True,
                        help="URL de base du serveur MCP")
    parser.add_argument("--endpoint", "-e", default="/mcp",
                        help="Endpoint MCP (par défaut: /mcp)")
    parser.add_argument("--capabilities", "-c", nargs="+",
                        help="Liste des capacités du serveur (facultatif si --validate est utilisé)")
    parser.add_argument("--validate", "-v", action="store_true",
                        help="Valider l'URL du serveur MCP")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Forcer le remplacement si un serveur avec cet ID existe déjà")
    
    return parser.parse_args()

async def main():
    """Fonction principale."""
    # Vérifier l'import de datetime (nécessaire pour la date d'enregistrement)
    global datetime
    import datetime
    
    # Parser les arguments
    args = parse_args()
    
    # Charger la configuration
    config = await load_config()
    if not config:
        logger.error("Impossible de charger la configuration.")
        sys.exit(1)
    
    # Enregistrer le serveur
    success = await register_server(args)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main()) 