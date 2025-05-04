"""
Module de configuration pour le MCP Registry.
Charge les paramètres depuis le fichier YAML et les variables d'environnement.
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

class AppConfig(BaseModel):
    """Configuration de l'application."""
    name: str = "MCP Registry Service"
    version: str = "1.0.0"
    description: str = "Service de gestion des serveurs MCP pour Albert"
    host: str = "0.0.0.0"
    port: int = 8000

class EmbeddingConfig(BaseModel):
    """Configuration pour l'embedding."""
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    dimension: int = 384
    cache_dir: str = "./embeddings_cache"

class ServerConfig(BaseModel):
    """Configuration d'un serveur MCP."""
    id: str
    name: str
    description: str = ""
    url: str
    headers: Dict[str, str] = Field(default_factory=dict)

class RegistryConfig(BaseModel):
    """Configuration du registry MCP."""
    discovery_interval: int = 3600
    discovery_enabled: bool = True
    cache_ttl: int = 86400
    server_urls: Optional[List[str]] = None
    discovery_urls: Optional[List[str]] = None
    auth_token: Optional[str] = None
    timeout: int = 30
    manage_servers: bool = False  # Option pour gérer les serveurs MCP

class Settings(BaseModel):
    """Configuration globale."""
    app: AppConfig = Field(default_factory=AppConfig)
    registry: RegistryConfig = Field(default_factory=RegistryConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    servers: List[ServerConfig] = Field(default_factory=list)

def get_config_path() -> Path:
    """Récupère le chemin du fichier de configuration."""
    env_path = os.getenv("MCP_CONFIG_PATH")
    if env_path:
        return Path(env_path)
    
    # Chercher dans les chemins standards
    paths = [
        Path("./conf/config.yaml"),
        Path("../conf/config.yaml"),
        Path("/etc/mcp-registry/config.yaml"),
    ]
    
    for path in paths:
        if path.exists():
            return path
    
    # Utiliser la configuration par défaut
    return Path("./conf/config.yaml")

def load_config() -> Settings:
    """Charge la configuration depuis le fichier YAML et les variables d'environnement."""
    config_path = get_config_path()
    config_dict = {}
    
    # Charger la configuration YAML si elle existe
    if config_path.exists():
        with open(config_path, "r") as f:
            config_dict = yaml.safe_load(f)
    
    # Remplacer les valeurs par les variables d'environnement si définies
    if os.getenv("MCP_APP_PORT"):
        config_dict.setdefault("app", {})["port"] = int(os.getenv("MCP_APP_PORT"))
    
    if os.getenv("MCP_DISCOVERY_INTERVAL"):
        config_dict.setdefault("registry", {})["discovery_interval"] = int(os.getenv("MCP_DISCOVERY_INTERVAL"))
    
    if os.getenv("MCP_DISCOVERY_ENABLED"):
        config_dict.setdefault("registry", {})["discovery_enabled"] = os.getenv("MCP_DISCOVERY_ENABLED").lower() in ("true", "1", "yes")
    
    if os.getenv("MCP_MANAGE_SERVERS"):
        config_dict.setdefault("registry", {})["manage_servers"] = os.getenv("MCP_MANAGE_SERVERS").lower() in ("true", "1", "yes")
    
    # Traiter les serveurs définis dans les variables d'environnement
    # Format: MCP_SERVER_<ID>_URL=<url>
    # Format: MCP_SERVER_<ID>_NAME=<n>
    # Format: MCP_SERVER_<ID>_DESC=<description>
    
    env_servers = []
    for key, value in os.environ.items():
        if key.startswith("MCP_SERVER_") and key.endswith("_URL"):
            server_id = key[11:-4].lower()  # Extraire l'ID du serveur
            server_url = value
            server_name = os.getenv(f"MCP_SERVER_{server_id.upper()}_NAME", server_id.title())
            server_desc = os.getenv(f"MCP_SERVER_{server_id.upper()}_DESC", "")
            
            env_servers.append({
                "id": server_id,
                "name": server_name,
                "description": server_desc,
                "url": server_url,
            })
    
    # Ajouter les serveurs définis dans les variables d'environnement
    if env_servers:
        config_dict.setdefault("servers", []).extend(env_servers)
    
    return Settings(**config_dict)

# Instance globale de la configuration
settings = load_config() 