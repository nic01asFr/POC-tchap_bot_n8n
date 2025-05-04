#!/usr/bin/env python
"""
Script de test pour accéder directement à un serveur MCP Grist sans passer par le MCP Registry.
"""

import asyncio
import json
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.core.mcp_client import MCPClient, ServerConfig

console = Console()

async def test_direct_connection(server_url):
    """Test direct d'une connexion avec un serveur MCP Grist."""
    console.print(Panel(f"Test de connexion directe au serveur MCP: [bold]{server_url}[/bold]", 
                        title="Test MCP Direct"))
    
    # Configurer le client MCP avec l'URL du serveur
    config = ServerConfig(
        id="direct_test",
        name="Test Direct",
        url=server_url
    )
    
    client = MCPClient(config)
    
    try:
        # Récupérer les informations du serveur
        server_info = await client._fetch_server_info(server_url)
        
        if server_info:
            console.print(Panel(f"[green]✓ Connexion réussie au serveur MCP", title="Info Serveur"))
            console.print(f"ID: [cyan]{server_info.id}[/cyan]")
            console.print(f"Nom: [green]{server_info.name}[/green]")
            console.print(f"Description: {server_info.description}")
            console.print(f"Version: {server_info.version}")
            console.print(f"URL: [magenta]{server_info.url}[/magenta]")
            
            # Récupérer les outils disponibles
            tools = await client._fetch_tools(server_info)
            
            if tools:
                console.print(Panel(f"[green]✓ {len(tools)} outils disponibles", title="Outils MCP"))
                
                table = Table(title=f"Outils du serveur {server_info.id}")
                table.add_column("Nom", style="cyan")
                table.add_column("Description", style="green")
                table.add_column("Paramètres", style="yellow")
                
                for tool in tools:
                    params = []
                    if tool.parameters:
                        for param in tool.parameters:
                            required = "*" if param.get("required", False) else ""
                            params.append(f"{param.get('name', '?')}{required}")
                    
                    table.add_row(
                        tool.name,
                        tool.description or "",
                        ", ".join(params)
                    )
                    
                console.print(table)
                
                return {"server": server_info, "tools": tools}
            else:
                console.print(Panel("[yellow]! Aucun outil trouvé", title="Outils MCP"))
                return {"server": server_info, "tools": []}
        else:
            console.print(Panel("[red]✗ Impossible de se connecter au serveur MCP", title="Erreur"))
            return None
    except Exception as e:
        console.print(Panel(f"[red]✗ Erreur lors de la connexion: {str(e)}", title="Erreur"))
        return None
    finally:
        await client.close()

async def execute_tool_direct(server_url, tool_name, parameters):
    """Exécute un outil directement sur un serveur MCP."""
    console.print(Panel(f"Exécution directe de l'outil [bold cyan]{tool_name}[/bold cyan]", 
                        title="Exécution d'outil"))
    console.print(f"Paramètres: {json.dumps(parameters, indent=2, ensure_ascii=False)}")
    
    # Configurer le client MCP avec l'URL du serveur
    config = ServerConfig(
        id="direct_test",
        name="Test Direct",
        url=server_url
    )
    
    client = MCPClient(config)
    
    try:
        # Récupérer les informations du serveur
        server_info = await client._fetch_server_info(server_url)
        
        if not server_info:
            console.print(Panel("[red]✗ Impossible de se connecter au serveur MCP", title="Erreur"))
            return None
        
        # Exécuter l'outil
        result = await client.execute_tool(server_info.id, tool_name, parameters)
        
        console.print(Panel("[green]✓ Outil exécuté avec succès", title="Résultat"))
        console.print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    except Exception as e:
        console.print(Panel(f"[red]✗ Erreur lors de l'exécution: {str(e)}", title="Erreur"))
        return None
    finally:
        await client.close()

async def main_async():
    parser = argparse.ArgumentParser(description="Test direct d'un serveur MCP")
    parser.add_argument("--url", default="http://localhost:3000/mcp/", help="URL du serveur MCP")
    parser.add_argument("--action", choices=["info", "execute"], default="info", help="Action à effectuer")
    parser.add_argument("--tool", help="Nom de l'outil à exécuter (pour l'action 'execute')")
    parser.add_argument("--params", help="Paramètres JSON pour l'exécution de l'outil")
    
    args = parser.parse_args()
    
    if args.action == "info":
        await test_direct_connection(args.url)
    elif args.action == "execute":
        if not args.tool:
            console.print(Panel("[red]✗ Erreur: l'argument --tool est requis pour l'action 'execute'", title="Erreur"))
            return
            
        params = {}
        if args.params:
            try:
                params = json.loads(args.params)
            except json.JSONDecodeError:
                console.print(Panel("[red]✗ Erreur: l'argument --params doit être un JSON valide", title="Erreur"))
                return
                
        await execute_tool_direct(args.url, args.tool, params)

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main() 