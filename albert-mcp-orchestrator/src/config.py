from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import os
import json
from loguru import logger


class Settings(BaseSettings):
    """Configuration globale de l'application MCP Orchestrator."""
    
    # Informations de base
    APP_NAME: str = "Albert MCP Orchestrator"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", env="MCP_ENV")
    DEBUG: bool = Field(default=True, env="MCP_DEBUG")
    
    # Configuration du serveur
    HOST: str = Field(default="0.0.0.0", env="MCP_HOST")
    PORT: int = Field(default=8000, env="MCP_PORT")
    
    # Chemins des répertoires
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    COMPOSITIONS_DIR: Optional[Path] = Field(default=None)
    VALIDATED_COMPOSITIONS_DIR: Optional[Path] = Field(default=None)
    LEARNING_COMPOSITIONS_DIR: Optional[Path] = Field(default=None)
    TEMPLATES_COMPOSITIONS_DIR: Optional[Path] = Field(default=None)
    PRODUCTION_COMPOSITIONS_DIR: Optional[Path] = Field(default=None)
    ARCHIVED_COMPOSITIONS_DIR: Optional[Path] = Field(default=None)
    
    # Configuration de la base de données vectorielle (Redis)
    REDIS_HOST: str = Field(default="vector-db", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    
    # Configuration de l'intégration avec Albert Tchapbot
    ALBERT_TCHAP_API_URL: str = Field(default="http://localhost:8080", env="ALBERT_TCHAP_API_URL")
    ALBERT_TCHAP_API_KEY: Optional[str] = Field(default=None, env="ALBERT_TCHAP_API_KEY")
    
    # MCP Registry pour l'exécution d'outils
    MCP_REGISTRY_URL: str = Field(default="http://localhost:8000", env="MCP_REGISTRY_URL")
    MCP_REGISTRY_API_KEY: Optional[str] = Field(default=None, env="MCP_REGISTRY_API_KEY")
    
    # Configuration du modèle d'embeddings
    EMBEDDINGS_MODEL: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", 
        env="EMBEDDINGS_MODEL"
    )
    
    # Seuils et limites
    SIMILARITY_THRESHOLD: float = Field(default=0.7, env="SIMILARITY_THRESHOLD")
    MAX_COMPOSITIONS_RESULTS: int = Field(default=5, env="MAX_COMPOSITIONS_RESULTS")
    EXECUTION_TIMEOUT_SECONDS: int = Field(default=60, env="EXECUTION_TIMEOUT_SECONDS")
    
    # Métriques d'apprentissage
    LEARNING_METRICS: Dict[str, float] = {
        "success_rate_weight": 0.5,
        "execution_time_weight": 0.3,
        "retry_efficiency_weight": 0.1,
        "resource_usage_weight": 0.1
    }
    
    # Configuration de l'analyseur de performance
    ANALYZER_MINIMUM_EXECUTIONS: int = Field(5, env="MCP_ANALYZER_MIN_EXEC")
    ANALYZER_SUCCESS_RATE_THRESHOLD: float = Field(0.95, env="MCP_ANALYZER_SUCCESS_THRESHOLD")
    ANALYZER_ERROR_RATE_WARNING: float = Field(0.05, env="MCP_ANALYZER_ERROR_WARNING")
    ANALYZER_LATENCY_THRESHOLD_MS: int = Field(1000, env="MCP_ANALYZER_LATENCY_THRESHOLD")
    
    # Configuration des optimiseurs
    OPTIMIZER_ENABLE_AUTO: bool = Field(False, env="MCP_OPTIMIZER_AUTO")
    OPTIMIZER_AUTO_INTERVAL_MINUTES: int = Field(1440, env="MCP_OPTIMIZER_INTERVAL")  # 24h par défaut
    
    # Configuration de l'analyseur de performance
    METRICS_DIR: Optional[Path] = Field(None, env="MCP_METRICS_DIR")
    
    # Timeout par défaut pour les étapes (en secondes)
    DEFAULT_STEP_TIMEOUT: int = Field(30, env="MCP_DEFAULT_STEP_TIMEOUT")
    
    # Répertoire temporaire pour les exécutions
    TEMP_DIR: Optional[Path] = Field(None, env="MCP_TEMP_DIR")
    
    # Auth
    SECRET_KEY: str = Field("CHANGE_ME_IN_PRODUCTION", env="MCP_SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, env="MCP_TOKEN_EXPIRE")
    
    @field_validator("COMPOSITIONS_DIR", "VALIDATED_COMPOSITIONS_DIR", "LEARNING_COMPOSITIONS_DIR", 
               "TEMPLATES_COMPOSITIONS_DIR", "PRODUCTION_COMPOSITIONS_DIR", "ARCHIVED_COMPOSITIONS_DIR", 
               "METRICS_DIR", "TEMP_DIR", mode="before")
    @classmethod
    def set_directory_paths(cls, v, info):
        """Définir les chemins des répertoires avec valeurs par défaut."""
        if v is not None:
            return Path(v)
        
        base_dir = Path(__file__).resolve().parent.parent
        compositions_dir = base_dir / "compositions"
        
        # Définir les valeurs par défaut selon le nom du champ
        field_name = info.field_name
        if field_name == "COMPOSITIONS_DIR":
            return compositions_dir
        elif field_name == "VALIDATED_COMPOSITIONS_DIR":
            return compositions_dir / "validated"
        elif field_name == "LEARNING_COMPOSITIONS_DIR":
            return compositions_dir / "learning"
        elif field_name == "TEMPLATES_COMPOSITIONS_DIR":
            return compositions_dir / "templates"
        elif field_name == "PRODUCTION_COMPOSITIONS_DIR":
            return compositions_dir / "production"
        elif field_name == "ARCHIVED_COMPOSITIONS_DIR":
            return compositions_dir / "archived"
        elif field_name == "METRICS_DIR":
            return base_dir / "metrics"
        elif field_name == "TEMP_DIR":
            return base_dir / "temp"
        
        return v
    
    # Configuration par dictionnaire au lieu de classe interne
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"  # Ignorer les variables d'environnement supplémentaires
    }


# Instance globale des paramètres
settings = Settings() 

# Configurer loguru
logger.remove()  # Supprimer le gestionnaire par défaut
logger.add(
    "logs/mcp_{time}.log",
    rotation="500 MB",
    retention="10 days",
    level="DEBUG" if settings.DEBUG else "INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} - {message}"
)
logger.add(lambda msg: print(msg, end=""), level="INFO")

# Log du démarrage
logger.info(f"Configuration chargée pour l'environnement: {settings.ENVIRONMENT}")

# Assurer l'existence des répertoires essentiels
for directory in [settings.COMPOSITIONS_DIR, settings.VALIDATED_COMPOSITIONS_DIR, settings.LEARNING_COMPOSITIONS_DIR, 
                 settings.TEMPLATES_COMPOSITIONS_DIR, settings.PRODUCTION_COMPOSITIONS_DIR, settings.ARCHIVED_COMPOSITIONS_DIR,
                 settings.METRICS_DIR, settings.TEMP_DIR]:
    if directory:
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"Répertoire vérifié: {directory}") 