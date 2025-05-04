"""
Module de gestion des serveurs MCP.

Ce module fournit des fonctionnalités pour démarrer, surveiller et arrêter
des serveurs MCP basés sur une configuration similaire à celle de Claude Desktop.
"""

import json
import logging
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class MCPServerManager:
    """
    Gestionnaire de serveurs MCP.
    
    Cette classe permet de démarrer, surveiller et arrêter des serveurs MCP
    basés sur une configuration similaire à celle de Claude Desktop.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialise le gestionnaire de serveurs MCP.
        
        Args:
            config_path: Chemin vers le fichier de configuration des serveurs MCP.
                Si None, cherche dans les emplacements standards.
        """
        self.config_path = config_path
        self.config = {}
        self.servers = {}
        self._load_config()
        
    def _load_config(self) -> None:
        """Charge la configuration des serveurs MCP."""
        if not self.config_path:
            # Chercher dans les emplacements standards
            paths = [
                Path("./conf/mcp_servers.json"),
                Path("../conf/mcp_servers.json"),
                Path("/etc/mcp-registry/mcp_servers.json"),
                Path(os.path.expanduser("~/.config/claude-desktop/claude_desktop_config.json")),
            ]
            
            for path in paths:
                if path.exists():
                    self.config_path = str(path)
                    break
        
        if not self.config_path or not os.path.exists(self.config_path):
            logger.warning("Aucun fichier de configuration MCP trouvé")
            return
            
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                
            if "mcpServers" in config:
                self.config = config["mcpServers"]
            else:
                self.config = config
                
            logger.info(f"Configuration MCP chargée depuis {self.config_path}")
        except Exception as e:
            logger.error(f"Erreur lors du chargement de la configuration MCP: {str(e)}")
    
    def start_servers(self) -> Dict[str, Any]:
        """
        Démarre tous les serveurs MCP définis dans la configuration.
        
        Returns:
            Dictionnaire des serveurs démarrés avec leur statut
        """
        results = {}
        
        for server_id, server_config in self.config.items():
            try:
                result = self.start_server(server_id, server_config)
                results[server_id] = result
            except Exception as e:
                logger.error(f"Erreur lors du démarrage du serveur MCP {server_id}: {str(e)}")
                results[server_id] = {"status": "error", "error": str(e)}
                
        return results
        
    def start_server(self, server_id: str, server_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Démarre un serveur MCP spécifique.
        
        Args:
            server_id: Identifiant du serveur
            server_config: Configuration du serveur
            
        Returns:
            Statut du démarrage du serveur
        """
        if server_id in self.servers and self.servers[server_id].get("process") and self.is_server_running(server_id):
            logger.info(f"Le serveur MCP {server_id} est déjà en cours d'exécution")
            return {"status": "already_running"}
            
        command = server_config.get("command")
        args = server_config.get("args", [])
        env_vars = server_config.get("env", {})
        
        if not command:
            logger.error(f"Commande non spécifiée pour le serveur MCP {server_id}")
            return {"status": "error", "error": "Commande non spécifiée"}
            
        # Préparer l'environnement
        env = os.environ.copy()
        for key, value in env_vars.items():
            env[key] = str(value)
            
        # Construire la commande complète
        cmd = [command] + args
        cmd_str = shlex.join(cmd)
        
        logger.info(f"Démarrage du serveur MCP {server_id}: {cmd_str}")
        
        try:
            # Démarrer le processus
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Attendre que le serveur soit prêt (idéalement avec une vérification appropriée)
            # Pour l'instant, on attend simplement 2 secondes
            time.sleep(2)
            
            if process.poll() is not None:
                # Le processus s'est terminé trop rapidement
                stdout, stderr = process.communicate()
                logger.error(f"Le serveur MCP {server_id} s'est terminé prématurément")
                logger.error(f"Sortie standard: {stdout}")
                logger.error(f"Erreur standard: {stderr}")
                return {"status": "error", "error": "Terminé prématurément", "stdout": stdout, "stderr": stderr}
                
            # Stocker les informations du serveur
            self.servers[server_id] = {
                "process": process,
                "command": cmd_str,
                "config": server_config,
                "start_time": time.time()
            }
            
            logger.info(f"Serveur MCP {server_id} démarré avec PID {process.pid}")
            return {"status": "success", "pid": process.pid}
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage du serveur MCP {server_id}: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def stop_server(self, server_id: str) -> Dict[str, Any]:
        """
        Arrête un serveur MCP spécifique.
        
        Args:
            server_id: Identifiant du serveur
            
        Returns:
            Statut de l'arrêt du serveur
        """
        if server_id not in self.servers or not self.servers[server_id].get("process"):
            logger.warning(f"Le serveur MCP {server_id} n'est pas en cours d'exécution")
            return {"status": "not_running"}
            
        process = self.servers[server_id]["process"]
        
        try:
            # Tenter de terminer proprement le processus
            process.terminate()
            
            # Attendre que le processus se termine
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Si le processus ne se termine pas proprement, le forcer
                process.kill()
                process.wait()
                
            logger.info(f"Serveur MCP {server_id} arrêté")
            
            # Nettoyer les informations du serveur
            self.servers[server_id]["process"] = None
            
            return {"status": "success"}
            
        except Exception as e:
            logger.error(f"Erreur lors de l'arrêt du serveur MCP {server_id}: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def stop_all_servers(self) -> Dict[str, Any]:
        """
        Arrête tous les serveurs MCP en cours d'exécution.
        
        Returns:
            Statut de l'arrêt des serveurs
        """
        results = {}
        
        for server_id in list(self.servers.keys()):
            results[server_id] = self.stop_server(server_id)
            
        return results
    
    def is_server_running(self, server_id: str) -> bool:
        """
        Vérifie si un serveur MCP est en cours d'exécution.
        
        Args:
            server_id: Identifiant du serveur
            
        Returns:
            True si le serveur est en cours d'exécution, False sinon
        """
        if server_id not in self.servers or not self.servers[server_id].get("process"):
            return False
            
        process = self.servers[server_id]["process"]
        return process.poll() is None
    
    def get_server_status(self, server_id: str) -> Dict[str, Any]:
        """
        Obtient le statut d'un serveur MCP.
        
        Args:
            server_id: Identifiant du serveur
            
        Returns:
            Statut du serveur
        """
        if server_id not in self.servers:
            return {"status": "unknown"}
            
        server_info = self.servers[server_id]
        process = server_info.get("process")
        
        if not process:
            return {"status": "stopped"}
            
        is_running = process.poll() is None
        
        if is_running:
            uptime = time.time() - server_info.get("start_time", time.time())
            return {
                "status": "running",
                "pid": process.pid,
                "uptime": int(uptime),
                "command": server_info.get("command")
            }
        else:
            return {"status": "stopped", "exit_code": process.returncode}
    
    def get_all_servers_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Obtient le statut de tous les serveurs MCP.
        
        Returns:
            Statut de tous les serveurs
        """
        results = {}
        
        # Serveurs actuellement gérés
        for server_id in self.servers.keys():
            results[server_id] = self.get_server_status(server_id)
            
        # Serveurs définis dans la configuration mais pas encore démarrés
        for server_id in self.config.keys():
            if server_id not in results:
                results[server_id] = {"status": "not_started"}
                
        return results
    
    def get_server_url(self, server_id: str) -> Optional[str]:
        """
        Obtient l'URL d'un serveur MCP basée sur des heuristiques.
        
        Args:
            server_id: Identifiant du serveur
            
        Returns:
            URL du serveur ou None si indéterminée
        """
        # Pour le moment, utilisation d'heuristiques simples basées sur le nom du serveur
        # À terme, cela devrait être configuré ou découvert automatiquement
        
        if server_id == "grist-mcp":
            return "http://localhost:5000/"
        elif server_id == "filesystem":
            return "http://localhost:3000/mcp/"
        elif server_id == "github":
            return "http://localhost:3000/mcp/"
        elif server_id == "n8n":
            return "http://localhost:5678/mcp/nextcloud_tools/"
            
        return None 