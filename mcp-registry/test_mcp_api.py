#!/usr/bin/env python
"""
Script de test pour vérifier le fonctionnement du MCP Registry.

Ce script teste les principaux endpoints du MCP Registry, notamment:
- L'API d'état
- L'API de liste des serveurs
- L'API de liste des outils
- L'API d'analyse d'intention
"""

import os
import sys
import json
import argparse
import requests

def test_api_status(base_url, auth_token=None):
    """Teste l'endpoint d'état de l'API."""
    print("\n=== Test de l'API d'état ===")
    
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    try:
        response = requests.get(f"{base_url}/api/status", headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API d'état OK: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"❌ Erreur API d'état: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception lors du test de l'API d'état: {str(e)}")
        return False

def test_api_servers(base_url, auth_token=None):
    """Teste l'endpoint de liste des serveurs."""
    print("\n=== Test de l'API de liste des serveurs ===")
    
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    try:
        response = requests.get(f"{base_url}/api/servers", headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API de liste des serveurs OK: {len(result)} serveurs trouvés")
            for server in result:
                print(f"  - {server.get('name', 'Sans nom')} ({server.get('id', 'unknown')}) : {server.get('tools_count', 0)} outils")
            return True
        else:
            print(f"❌ Erreur API de liste des serveurs: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception lors du test de l'API de liste des serveurs: {str(e)}")
        return False

def test_api_tools(base_url, auth_token=None):
    """Teste l'endpoint de liste des outils."""
    print("\n=== Test de l'API de liste des outils ===")
    
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    try:
        response = requests.get(f"{base_url}/api/tools", headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API de liste des outils OK: {len(result)} outils trouvés")
            for tool in result:
                print(f"  - {tool.get('name', 'Sans nom')} ({tool.get('id', 'unknown')})")
                print(f"    {tool.get('description', 'Pas de description')}")
            return True
        else:
            print(f"❌ Erreur API de liste des outils: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception lors du test de l'API de liste des outils: {str(e)}")
        return False

def test_api_analyze(base_url, auth_token=None):
    """Teste l'endpoint d'analyse d'intention."""
    print("\n=== Test de l'API d'analyse d'intention ===")
    
    headers = {
        "Content-Type": "application/json"
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    # Messages de test
    test_messages = [
        "Liste tous les documents Grist disponibles",
        "Quelles sont les tables du document budget?",
        "Je voudrais voir les enregistrements de la table Dépenses"
    ]
    
    success = True
    
    for message in test_messages:
        print(f"\nTest avec le message: '{message}'")
        
        try:
            response = requests.post(
                f"{base_url}/api/analyze",
                headers=headers,
                json={"message": message}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ API d'analyse OK")
                print(f"  - Intention: {result.get('intent')}")
                print(f"  - Confiance: {result.get('confidence')}")
                print(f"  - Outil recommandé: {result.get('tool_id')}")
                print(f"  - Nécessite un outil: {result.get('requires_tool')}")
                
                tools = result.get("tools", [])
                if tools:
                    print(f"  - Outils pertinents trouvés:")
                    for tool in tools:
                        print(f"    * {tool.get('name')} ({tool.get('id')})")
            else:
                print(f"❌ Erreur API d'analyse: {response.status_code} - {response.text}")
                success = False
        except Exception as e:
            print(f"❌ Exception lors du test de l'API d'analyse: {str(e)}")
            success = False
    
    return success

def main():
    """Point d'entrée principal."""
    
    parser = argparse.ArgumentParser(description="Teste les endpoints du MCP Registry")
    parser.add_argument("--url", default="http://localhost:8001", help="URL du MCP Registry")
    parser.add_argument("--token", help="Token d'authentification (optionnel)")
    args = parser.parse_args()
    
    # Normaliser l'URL
    base_url = args.url.rstrip("/")
    
    print(f"Test du MCP Registry à l'URL: {base_url}")
    
    # Tester les différents endpoints
    status_ok = test_api_status(base_url, args.token)
    if not status_ok:
        print("❌ Le service MCP Registry n'est pas accessible. Impossible de continuer les tests.")
        sys.exit(1)
    
    servers_ok = test_api_servers(base_url, args.token)
    tools_ok = test_api_tools(base_url, args.token)
    analyze_ok = test_api_analyze(base_url, args.token)
    
    # Résumé des tests
    print("\n=== Résumé des tests ===")
    print(f"API d'état: {'✅ OK' if status_ok else '❌ Échec'}")
    print(f"API de liste des serveurs: {'✅ OK' if servers_ok else '❌ Échec'}")
    print(f"API de liste des outils: {'✅ OK' if tools_ok else '❌ Échec'}")
    print(f"API d'analyse d'intention: {'✅ OK' if analyze_ok else '❌ Échec'}")
    
    if status_ok and servers_ok and tools_ok and analyze_ok:
        print("\n✅ Tous les tests ont réussi !")
        sys.exit(0)
    else:
        print("\n❌ Certains tests ont échoué.")
        sys.exit(1)

if __name__ == "__main__":
    main() 