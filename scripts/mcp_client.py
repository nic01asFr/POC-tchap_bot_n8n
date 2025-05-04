#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Client pour le Model Context Protocol (MCP).

Ce script permet de :
1. Interroger un serveur MCP pour récupérer les outils disponibles
2. Exécuter un outil MCP spécifique
"""

import os
import sys
import json
import asyncio
import logging
import argparse
from typing import Dict, List, Any, Optional
import aiohttp

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mcp_client')

class MCPClient:
    """Client pour interagir avec un serveur Model Context Protocol."""

    def __init__(self, mcp_url: str, headers: Dict = None):
        """
        Initialise le client MCP.
        
        Args:
            mcp_url: URL du serveur MCP
            headers: En-têtes HTTP optionnels pour les requêtes
        """
        self.mcp_url = mcp_url.rstrip('/')
        self.headers = headers or {}
        
    async def get_schema(self) -> Dict:
        """
        Récupère le schéma du serveur MCP.
        
        Returns:
            Schéma des outils disponibles
        """
        try:
            logger.info(f"Récupération du schéma MCP depuis {self.mcp_url}/schema")
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.mcp_url}/schema", headers=self.headers) as response:
                    if response.status == 200:
                        schema = await response.json()
                        logger.info(f"Schéma récupéré avec succès")
                        return schema
                    else:
                        error_text = await response.text()
                        logger.error(f"Erreur lors de la récupération du schéma: {response.status} - {error_text}")
                        return {"error": f"Erreur {response.status}", "message": error_text}
        except Exception as e:
            logger.exception(f"Exception lors de la récupération du schéma: {str(e)}")
            return {"error": str(e)}
            
    def list_tools(self, schema: Dict) -> List[Dict]:
        """
        Extrait la liste des outils d'un schéma MCP.
        
        Args:
            schema: Schéma MCP complet
            
        Returns:
            Liste des outils disponibles
        """
        tools = []
        
        if "tools" in schema:
            tools = schema["tools"]
        elif "functions" in schema:
            # Format alternatif utilisé par certains serveurs MCP
            tools = schema["functions"]
            
        return tools
        
    async def run_tool(self, tool_id: str, parameters: Dict[str, Any]) -> Dict:
        """
        Exécute un outil spécifique.
        
        Args:
            tool_id: Identifiant de l'outil à exécuter
            parameters: Paramètres à passer à l'outil
            
        Returns:
            Résultat de l'exécution
        """
        try:
            logger.info(f"Exécution de l'outil {tool_id} avec paramètres: {parameters}")
            
            async with aiohttp.ClientSession() as session:
                # Format du payload selon le protocole MCP
                payload = {
                    "name": tool_id,
                    "parameters": parameters
                }
                
                async with session.post(
                    f"{self.mcp_url}/run",
                    headers=self.headers,
                    json=payload
                ) as response:
                    if response.status >= 200 and response.status < 300:
                        result = await response.json()
                        logger.info(f"Outil exécuté avec succès")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Erreur lors de l'exécution de l'outil: {response.status} - {error_text}")
                        return {"error": f"Erreur {response.status}", "message": error_text}
        except Exception as e:
            logger.exception(f"Exception lors de l'exécution de l'outil: {str(e)}")
            return {"error": str(e)}

def format_tools_output(tools: List[Dict]) -> str:
    """
    Formate la liste des outils pour l'affichage.
    
    Args:
        tools: Liste des outils
        
    Returns:
        Texte formaté pour l'affichage
    """
    if not tools:
        return "Aucun outil disponible."
        
    output = "🛠️ Outils disponibles :\n\n"
    
    for i, tool in enumerate(tools, 1):
        tool_id = tool.get("name", "inconnu")
        description = tool.get("description", "Pas de description disponible")
        
        output += f"{i}. **{tool_id}** - {description}\n"
        
        parameters = tool.get("parameters", {})
        if isinstance(parameters, dict) and "properties" in parameters:
            properties = parameters["properties"]
            required = parameters.get("required", [])
            
            if properties:
                output += "   Paramètres:\n"
                for param_name, param_info in properties.items():
                    param_desc = param_info.get("description", "")
                    param_type = param_info.get("type", "")
                    req_mark = "*" if param_name in required else ""
                    
                    output += f"   - {param_name}{req_mark}: {param_type} - {param_desc}\n"
        
        output += "\n"
    
    return output

async def main():
    """Point d'entrée principal du script."""
    parser = argparse.ArgumentParser(description="Client Model Context Protocol (MCP)")
    parser.add_argument("--url", required=True, help="URL du serveur MCP")
    parser.add_argument("--token", help="Token d'authentification (optionnel)")
    parser.add_argument("--action", choices=["list", "run"], default="list", 
                      help="Action à effectuer: lister les outils ou exécuter un outil")
    parser.add_argument("--tool", help="ID de l'outil à exécuter (requis pour run)")
    parser.add_argument("--params", help="Paramètres JSON pour l'outil (requis pour run)")
    parser.add_argument("--output", choices=["text", "json"], default="text",
                      help="Format de sortie: texte ou JSON")
    
    args = parser.parse_args()
    
    # Préparer les headers d'authentification si un token est fourni
    headers = {}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    
    # Créer le client MCP
    client = MCPClient(args.url, headers)
    
    if args.action == "list":
        # Lister les outils disponibles
        schema = await client.get_schema()
        
        if "error" in schema:
            print(f"Erreur: {schema.get('error')}")
            sys.exit(1)
            
        tools = client.list_tools(schema)
        
        if args.output == "json":
            print(json.dumps(tools, indent=2))
        else:
            print(format_tools_output(tools))
            
    elif args.action == "run":
        # Vérifier que les paramètres requis sont présents
        if not args.tool:
            print("Erreur: L'ID de l'outil est requis pour l'action 'run'")
            sys.exit(1)
            
        # Préparer les paramètres
        try:
            params = json.loads(args.params) if args.params else {}
        except json.JSONDecodeError:
            print("Erreur: Les paramètres doivent être au format JSON valide")
            sys.exit(1)
            
        # Exécuter l'outil
        result = await client.run_tool(args.tool, params)
        
        if args.output == "json":
            print(json.dumps(result, indent=2))
        else:
            if "error" in result:
                print(f"Erreur: {result.get('error')}")
                print(f"Message: {result.get('message', 'Pas de détails disponibles')}")
            else:
                print("✅ Résultat:")
                print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main()) 