#!/usr/bin/env python
"""
Script de test pour vérifier que le système MCP fonctionne correctement.
Permet de tester la communication entre Albert, le MCP Registry et les serveurs MCP.
"""

import argparse
import json
import time
import requests
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

console = Console()

def check_registry(registry_url: str) -> bool:
    """Vérifie que le MCP Registry est accessible."""
    try:
        response = requests.get(f"{registry_url}/ping", timeout=5)
        if response.status_code == 200:
            console.print(Panel("[green]✓ MCP Registry accessible", title="Test Registry"))
            return True
        else:
            console.print(Panel(f"[red]✗ MCP Registry inaccessible - Statut: {response.status_code}", title="Test Registry"))
            return False
    except Exception as e:
        console.print(Panel(f"[red]✗ MCP Registry inaccessible - Erreur: {e}", title="Test Registry"))
        return False

def list_servers(registry_url: str) -> list:
    """Liste les serveurs MCP disponibles dans le Registry."""
    try:
        response = requests.get(f"{registry_url}/servers", timeout=5)
        if response.status_code == 200:
            servers = response.json()
            
            if not servers:
                console.print(Panel("[yellow]! Aucun serveur MCP enregistré", title="Serveurs MCP"))
                return []
            
            table = Table(title="Serveurs MCP enregistrés")
            table.add_column("ID", style="cyan")
            table.add_column("Nom", style="green")
            table.add_column("Description", style="blue")
            table.add_column("URL", style="magenta")
            table.add_column("Outils", style="yellow")
            
            for server in servers:
                table.add_row(
                    server.get("id", "?"),
                    server.get("name", "?"),
                    server.get("description", ""),
                    server.get("url", "?"),
                    str(server.get("tools_count", 0))
                )
                
            console.print(table)
            return servers
        else:
            console.print(Panel(f"[red]✗ Erreur lors de la récupération des serveurs - Statut: {response.status_code}", title="Serveurs MCP"))
            return []
    except Exception as e:
        console.print(Panel(f"[red]✗ Erreur lors de la récupération des serveurs - Erreur: {e}", title="Serveurs MCP"))
        return []

def list_tools(registry_url: str) -> list:
    """Liste tous les outils MCP disponibles."""
    try:
        response = requests.get(f"{registry_url}/tools", timeout=5)
        if response.status_code == 200:
            tools = response.json()
            
            if not tools:
                console.print(Panel("[yellow]! Aucun outil MCP disponible", title="Outils MCP"))
                return []
            
            # Organiser les outils par serveur
            tools_by_server = {}
            for tool in tools:
                server_id = tool.get("server_id", "inconnu")
                if server_id not in tools_by_server:
                    tools_by_server[server_id] = []
                tools_by_server[server_id].append(tool)
            
            # Afficher les outils par serveur
            for server_id, server_tools in tools_by_server.items():
                table = Table(title=f"Outils du serveur {server_id}")
                table.add_column("Nom", style="cyan")
                table.add_column("Description", style="green")
                table.add_column("Paramètres", style="yellow")
                
                for tool in server_tools:
                    params = []
                    if tool.get("parameters") and isinstance(tool["parameters"], dict):
                        if "properties" in tool["parameters"]:
                            for param_name, param_info in tool["parameters"]["properties"].items():
                                required = "*" if "required" in tool["parameters"] and param_name in tool["parameters"]["required"] else ""
                                params.append(f"{param_name}{required}")
                    
                    table.add_row(
                        tool.get("name", "?"),
                        tool.get("description", ""),
                        ", ".join(params)
                    )
                    
                console.print(table)
            
            return tools
        else:
            console.print(Panel(f"[red]✗ Erreur lors de la récupération des outils - Statut: {response.status_code}", title="Outils MCP"))
            return []
    except Exception as e:
        console.print(Panel(f"[red]✗ Erreur lors de la récupération des outils - Erreur: {e}", title="Outils MCP"))
        return []

def search_tools(registry_url: str, query: str, limit: int = 5) -> list:
    """Recherche des outils MCP via l'API de recherche sémantique."""
    try:
        payload = {"query": query, "limit": limit}
        response = requests.post(f"{registry_url}/search", json=payload, timeout=10)
        
        if response.status_code == 200:
            tools = response.json()
            
            if not tools:
                console.print(Panel(f"[yellow]! Aucun outil trouvé pour la requête '[bold]{query}[/bold]'", title="Recherche d'outils"))
                return []
            
            table = Table(title=f"Résultats pour '{query}'")
            table.add_column("Serveur", style="cyan")
            table.add_column("Outil", style="green")
            table.add_column("Description", style="blue")
            
            for tool in tools:
                table.add_row(
                    tool.get("server_id", "?"),
                    tool.get("name", "?"),
                    tool.get("description", "")
                )
                
            console.print(table)
            return tools
        else:
            console.print(Panel(f"[red]✗ Erreur lors de la recherche d'outils - Statut: {response.status_code}", title="Recherche d'outils"))
            return []
    except Exception as e:
        console.print(Panel(f"[red]✗ Erreur lors de la recherche d'outils - Erreur: {e}", title="Recherche d'outils"))
        return []

def execute_tool(registry_url: str, server_id: str, tool_id: str, parameters: dict) -> dict:
    """Exécute un outil MCP via le Registry."""
    try:
        payload = {
            "server_id": server_id,
            "tool_id": tool_id,
            "parameters": parameters
        }
        
        console.print(Panel(f"Exécution de l'outil [bold cyan]{tool_id}[/bold cyan] sur le serveur [bold green]{server_id}[/bold green]", title="Exécution d'outil"))
        console.print(f"Paramètres: {json.dumps(parameters, indent=2, ensure_ascii=False)}")
        
        response = requests.post(f"{registry_url}/execute", json=payload, timeout=30)
        
        if response.status_code >= 200 and response.status_code < 300:
            result = response.json()
            console.print(Panel("[green]✓ Outil exécuté avec succès", title="Résultat"))
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
            return result
        else:
            try:
                error = response.json()
                console.print(Panel(f"[red]✗ Erreur lors de l'exécution de l'outil: {error.get('detail', response.text)}", title="Erreur"))
            except:
                console.print(Panel(f"[red]✗ Erreur lors de l'exécution de l'outil - Statut: {response.status_code}", title="Erreur"))
            return {"error": response.text}
    except Exception as e:
        console.print(Panel(f"[red]✗ Erreur lors de l'exécution de l'outil - Erreur: {e}", title="Erreur"))
        return {"error": str(e)}

def test_full_flow(registry_url: str):
    """Teste l'ensemble du flux MCP."""
    # Vérifier que le MCP Registry est accessible
    if not check_registry(registry_url):
        return
        
    # Lister les serveurs
    servers = list_servers(registry_url)
    if not servers:
        return
        
    # Lister les outils
    tools = list_tools(registry_url)
    if not tools:
        return
        
    # Rechercher des outils (météo, température, climat)
    search_tools(registry_url, "météo")
    
    # Exécuter un outil (sur le serveur météo de démonstration s'il existe)
    for server in servers:
        if server.get("id") == "demo_weather":
            # Exécuter l'outil get_weather
            execute_tool(registry_url, "demo_weather", "get_weather", {"ville": "Paris"})
            
            # Exécuter l'outil get_forecast
            execute_tool(registry_url, "demo_weather", "get_forecast", {"ville": "Lyon", "jours": 3})
            
            break
    else:
        console.print(Panel("[yellow]! Serveur météo de démonstration non trouvé, impossible de tester l'exécution d'outils", title="Test d'exécution"))

def main():
    parser = argparse.ArgumentParser(description="Script de test pour le système MCP")
    parser.add_argument("--registry", default="http://localhost:8000", help="URL du MCP Registry")
    parser.add_argument("--action", choices=["check", "servers", "tools", "search", "execute", "full"], default="full", help="Action à effectuer")
    parser.add_argument("--query", help="Requête de recherche pour l'action 'search'")
    parser.add_argument("--server", help="ID du serveur pour l'action 'execute'")
    parser.add_argument("--tool", help="ID de l'outil pour l'action 'execute'")
    parser.add_argument("--params", help="Paramètres JSON pour l'action 'execute'")
    
    args = parser.parse_args()
    
    md = Markdown("# Test du système MCP")
    console.print(md)
    console.print(f"URL du MCP Registry: {args.registry}")
    
    if args.action == "check":
        check_registry(args.registry)
    elif args.action == "servers":
        if check_registry(args.registry):
            list_servers(args.registry)
    elif args.action == "tools":
        if check_registry(args.registry):
            list_tools(args.registry)
    elif args.action == "search":
        if check_registry(args.registry):
            if not args.query:
                console.print(Panel("[red]✗ Erreur: l'argument --query est requis pour l'action 'search'", title="Erreur"))
                sys.exit(1)
            search_tools(args.registry, args.query)
    elif args.action == "execute":
        if check_registry(args.registry):
            if not args.server or not args.tool:
                console.print(Panel("[red]✗ Erreur: les arguments --server et --tool sont requis pour l'action 'execute'", title="Erreur"))
                sys.exit(1)
                
            params = {}
            if args.params:
                try:
                    params = json.loads(args.params)
                except json.JSONDecodeError:
                    console.print(Panel("[red]✗ Erreur: l'argument --params doit être un JSON valide", title="Erreur"))
                    sys.exit(1)
                    
            execute_tool(args.registry, args.server, args.tool, params)
    elif args.action == "full":
        test_full_flow(args.registry)
        
if __name__ == "__main__":
    main() 