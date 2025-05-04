#!/usr/bin/env python
"""
Client MCP simple pour tester la connexion avec un serveur MCP Grist.
Utilise uniquement la bibliothèque standard et requests.
"""

import argparse
import json
import requests
import sys

def test_mcp_server(url):
    """Teste la connexion avec un serveur MCP."""
    print(f"Test de connexion au serveur MCP: {url}")
    
    # S'assurer que l'URL se termine par un slash
    if not url.endswith('/'):
        url += '/'
    
    # Récupérer les informations du serveur
    try:
        info_url = f"{url}info"
        print(f"Requête vers: {info_url}")
        
        response = requests.get(info_url, timeout=10)
        
        if response.status_code == 200:
            info = response.json()
            print("\n✅ Connexion réussie au serveur MCP")
            print(f"ID: {info.get('id', 'N/A')}")
            print(f"Nom: {info.get('name', 'N/A')}")
            print(f"Description: {info.get('description', 'N/A')}")
            print(f"Version: {info.get('version', 'N/A')}")
            
            # Récupérer les outils disponibles
            tools_url = f"{url}tools"
            print(f"\nRécupération des outils depuis: {tools_url}")
            
            tools_response = requests.get(tools_url, timeout=10)
            
            if tools_response.status_code == 200:
                tools = tools_response.json()
                print(f"\n✅ {len(tools)} outils disponibles:")
                
                for i, tool in enumerate(tools, 1):
                    print(f"\nOutil {i}: {tool.get('name')}")
                    print(f"Description: {tool.get('description', 'N/A')}")
                    
                    # Afficher les paramètres
                    if "parameters" in tool:
                        print("Paramètres:")
                        params = tool["parameters"]
                        
                        # Format JSONSchema
                        if isinstance(params, dict) and "properties" in params:
                            required_params = params.get("required", [])
                            for param_name, param_info in params["properties"].items():
                                req = "(requis)" if param_name in required_params else "(optionnel)"
                                print(f"  - {param_name} {req}: {param_info.get('description', 'N/A')}")
                        
                        # Format liste de paramètres
                        elif isinstance(params, list):
                            for param in params:
                                name = param.get("name", "N/A")
                                req = "(requis)" if param.get("required", False) else "(optionnel)"
                                print(f"  - {name} {req}: {param.get('description', 'N/A')}")
                
                return True
            else:
                print(f"\n❌ Erreur lors de la récupération des outils - Statut: {tools_response.status_code}")
                return False
        else:
            print(f"\n❌ Impossible de se connecter au serveur MCP - Statut: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"\n❌ Erreur lors de la connexion: {str(e)}")
        return False

def execute_tool(url, tool_name, parameters):
    """Exécute un outil sur un serveur MCP."""
    print(f"Exécution de l'outil '{tool_name}' sur le serveur: {url}")
    print(f"Paramètres: {json.dumps(parameters, indent=2, ensure_ascii=False)}")
    
    # S'assurer que l'URL se termine par un slash
    if not url.endswith('/'):
        url += '/'
    
    execute_url = f"{url}execute"
    payload = {
        "tool": tool_name,
        "parameters": parameters
    }
    
    try:
        response = requests.post(
            execute_url, 
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            result = response.json()
            print("\n✅ Outil exécuté avec succès")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return True
        else:
            print(f"\n❌ Erreur lors de l'exécution de l'outil - Statut: {response.status_code}")
            try:
                error = response.json()
                print(f"Détail: {error.get('detail', response.text)}")
            except:
                print(f"Réponse: {response.text}")
            return False
    
    except Exception as e:
        print(f"\n❌ Erreur lors de l'exécution: {str(e)}")
        return False

def try_multiple_urls():
    """Essaye de se connecter à plusieurs URL potentielles pour un serveur MCP Grist."""
    urls = [
        # URL standard Grist MCP
        "http://localhost:3000/mcp/",
        "http://localhost:8484/mcp/",
        "http://localhost:5000/mcp/",
        
        # URL basées sur la configuration Claude Desktop
        "http://localhost:5678/mcp/",
        "http://localhost:4000/mcp/",
        
        # URL pour le serveur grist-mcp personnalisé
        "http://localhost:5000/",
        "http://localhost:8000/",
        "http://localhost:3001/",
        "http://127.0.0.1:5000/",
        "http://127.0.0.1:8000/",
        
        # URL pour supergateway (n8n)
        "http://localhost:5678/mcp/nextcloud_tools/",
        
        # URL existantes
        "http://localhost:3000/api/mcp/",
        "http://localhost:8484/api/mcp/",
        "http://localhost:3333/mcp/",
        "http://localhost:3333/api/mcp/",
        "http://localhost:9000/mcp/"
    ]
    
    print("🔍 Recherche de serveurs MCP Grist actifs...")
    
    success = False
    for url in urls:
        print(f"\nTest de l'URL: {url}")
        try:
            if test_mcp_server(url):
                success = True
                print(f"\n✅ Serveur MCP trouvé à l'URL: {url}")
                break
        except Exception as e:
            print(f"Erreur: {str(e)}")
    
    if not success:
        print("\n❌ Aucun serveur MCP trouvé aux URL testées.")
        print("Vérifiez que le serveur Grist est bien en cours d'exécution et exposant le point d'entrée MCP.")

def main():
    parser = argparse.ArgumentParser(description="Client MCP simple pour tester un serveur")
    parser.add_argument("--url", help="URL du serveur MCP")
    parser.add_argument("--action", choices=["info", "execute", "discover"], default="discover", help="Action à effectuer")
    parser.add_argument("--tool", help="Nom de l'outil à exécuter (pour l'action 'execute')")
    parser.add_argument("--params", help="Paramètres JSON pour l'exécution de l'outil")
    
    args = parser.parse_args()
    
    if args.action == "discover":
        try_multiple_urls()
    elif args.action == "info":
        if not args.url:
            print("❌ Erreur: l'argument --url est requis pour l'action 'info'")
            sys.exit(1)
        test_mcp_server(args.url)
    elif args.action == "execute":
        if not args.url or not args.tool:
            print("❌ Erreur: les arguments --url et --tool sont requis pour l'action 'execute'")
            sys.exit(1)
            
        params = {}
        if args.params:
            try:
                params = json.loads(args.params)
            except json.JSONDecodeError:
                print("❌ Erreur: l'argument --params doit être un JSON valide")
                sys.exit(1)
                
        execute_tool(args.url, args.tool, params)

if __name__ == "__main__":
    main() 