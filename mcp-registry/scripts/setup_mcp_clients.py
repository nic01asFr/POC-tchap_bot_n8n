#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour configurer l'intégration du MCP Registry avec les clients MCP populaires.
"""

import os
import json
import argparse
from pathlib import Path

def setup_claude_desktop(registry_url="http://localhost:8001"):
    """
    Configure l'intégration avec Claude Desktop.
    
    Args:
        registry_url: URL du MCP Registry
    """
    print("Configuration de Claude Desktop...")
    
    # Chemin vers le fichier de configuration Claude
    config_path = Path.home() / ".config" / "claude"
    
    # Créer le répertoire si nécessaire
    os.makedirs(config_path, exist_ok=True)
    
    servers_file = config_path / "servers.json"
    
    # Charger la configuration existante si elle existe
    servers = []
    if servers_file.exists():
        try:
            with open(servers_file, "r") as f:
                servers = json.load(f)
        except json.JSONDecodeError:
            print("  Erreur: Fichier de configuration Claude invalide. Création d'un nouveau.")
            servers = []
    
    # Vérifier si notre serveur est déjà configuré
    server_exists = False
    for server in servers:
        if server.get("id") == "mcp-registry-albert":
            server_exists = True
            server["url"] = registry_url  # Mettre à jour l'URL si elle a changé
            print("  Serveur MCP Registry déjà configuré, URL mise à jour.")
            break
    
    # Ajouter notre serveur s'il n'existe pas
    if not server_exists:
        servers.append({
            "id": "mcp-registry-albert",
            "name": "Albert-Tchap MCP Registry",
            "url": registry_url,
            "type": "http"
        })
        print("  Serveur MCP Registry ajouté à la configuration.")
    
    # Sauvegarder la configuration
    with open(servers_file, "w") as f:
        json.dump(servers, f, indent=2)
    
    print("✅ Configuration de Claude Desktop terminée.")

def setup_vscode(registry_url="http://localhost:8001"):
    """
    Configure l'intégration avec VS Code.
    
    Args:
        registry_url: URL du MCP Registry
    """
    print("Configuration de VS Code...")
    
    # Chemin vers les paramètres VS Code
    if os.name == "nt":  # Windows
        settings_path = Path.home() / "AppData" / "Roaming" / "Code" / "User" / "settings.json"
    else:  # Linux/Mac
        settings_path = Path.home() / ".config" / "Code" / "User" / "settings.json"
    
    # Vérifier si le fichier existe
    if not settings_path.exists():
        print("  ⚠️ Fichier de paramètres VS Code non trouvé. VS Code est-il installé?")
        return
    
    # Charger les paramètres existants
    try:
        with open(settings_path, "r") as f:
            settings = json.load(f)
    except json.JSONDecodeError:
        print("  Erreur: Fichier de paramètres VS Code invalide. Création d'un nouveau.")
        settings = {}
    
    # Ajouter ou mettre à jour la configuration MCP
    if "mcp.servers" not in settings:
        settings["mcp.servers"] = []
    
    # Vérifier si notre serveur est déjà configuré
    server_exists = False
    for server in settings["mcp.servers"]:
        if server.get("id") == "mcp-registry-albert":
            server_exists = True
            server["url"] = registry_url  # Mettre à jour l'URL si elle a changé
            print("  Serveur MCP Registry déjà configuré, URL mise à jour.")
            break
    
    # Ajouter notre serveur s'il n'existe pas
    if not server_exists:
        settings["mcp.servers"].append({
            "id": "mcp-registry-albert",
            "name": "Albert-Tchap MCP Registry",
            "url": registry_url,
            "transport": "sse"
        })
        print("  Serveur MCP Registry ajouté à la configuration.")
    
    # Sauvegarder les paramètres
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    
    print("✅ Configuration de VS Code terminée.")

def setup_cursor(registry_url="http://localhost:8001"):
    """
    Configure l'intégration avec Cursor.
    
    Args:
        registry_url: URL du MCP Registry
    """
    print("Configuration de Cursor...")
    
    # Chemin vers la configuration Cursor
    if os.name == "nt":  # Windows
        config_path = Path.home() / "AppData" / "Roaming" / "Cursor" / "mcp"
    else:  # Linux/Mac
        config_path = Path.home() / ".cursor" / "mcp"
    
    # Créer le répertoire si nécessaire
    os.makedirs(config_path, exist_ok=True)
    
    servers_file = config_path / "servers.json"
    
    # Charger la configuration existante si elle existe
    data = {"servers": []}
    if servers_file.exists():
        try:
            with open(servers_file, "r") as f:
                data = json.load(f)
                if "servers" not in data:
                    data["servers"] = []
        except json.JSONDecodeError:
            print("  Erreur: Fichier de configuration Cursor invalide. Création d'un nouveau.")
            data = {"servers": []}
    
    # Vérifier si notre serveur est déjà configuré
    server_exists = False
    for server in data["servers"]:
        if server.get("id") == "mcp-registry-albert":
            server_exists = True
            server["url"] = registry_url  # Mettre à jour l'URL si elle a changé
            print("  Serveur MCP Registry déjà configuré, URL mise à jour.")
            break
    
    # Ajouter notre serveur s'il n'existe pas
    if not server_exists:
        data["servers"].append({
            "id": "mcp-registry-albert",
            "name": "Albert-Tchap MCP Registry",
            "url": registry_url
        })
        print("  Serveur MCP Registry ajouté à la configuration.")
    
    # Sauvegarder la configuration
    with open(servers_file, "w") as f:
        json.dump(data, f, indent=2)
    
    print("✅ Configuration de Cursor terminée.")

def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description="Configure l'intégration du MCP Registry avec les clients MCP")
    parser.add_argument("--url", default="http://localhost:8001", help="URL du MCP Registry")
    parser.add_argument("--clients", nargs="+", default=["claude"], 
                        choices=["claude", "vscode", "cursor", "all"], 
                        help="Clients à configurer")
    
    args = parser.parse_args()
    clients = args.clients
    registry_url = args.url
    
    if "all" in clients:
        clients = ["claude", "vscode", "cursor"]
    
    print(f"🔧 Configuration de l'intégration MCP Registry ({registry_url})...")
    
    if "claude" in clients:
        setup_claude_desktop(registry_url)
    
    if "vscode" in clients:
        setup_vscode(registry_url)
    
    if "cursor" in clients:
        setup_cursor(registry_url)
    
    print("\n✨ Configuration terminée !")
    print("\nPour utiliser le MCP Registry:")
    print(f"1. Assurez-vous que le service tourne sur {registry_url}")
    print("2. Redémarrez les clients configurés si nécessaire")
    print("3. Dans Claude, Cursor ou VS Code, vous devriez maintenant voir les outils MCP disponibles")

if __name__ == "__main__":
    main() 