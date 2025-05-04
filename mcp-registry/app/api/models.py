"""
Modèles Pydantic pour l'API du MCP Registry.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ServerInfo(BaseModel):
    """Informations sur un serveur MCP."""
    id: str
    name: str
    url: str
    description: Optional[str] = ""
    last_update: Optional[datetime] = None
    tools_count: int = 0

class ToolParameter(BaseModel):
    """Paramètre d'un outil MCP."""
    name: str
    description: Optional[str] = ""
    type: Optional[str] = "string"
    required: bool = False

class ToolInfo(BaseModel):
    """Informations sur un outil MCP."""
    id: Optional[str] = None
    name: Optional[str] = None
    server_id: Optional[str] = None
    server_url: Optional[str] = None
    description: Optional[str] = ""
    parameters: Optional[Dict[str, Any]] = None

    class Config:
        """Configuration pour permettre des champs supplémentaires."""
        extra = "allow"

class SearchQuery(BaseModel):
    """Requête de recherche d'outils."""
    query: str
    limit: int = Field(5, ge=1, le=100)

class ExecuteToolRequest(BaseModel):
    """Requête d'exécution d'un outil."""
    server_id: str
    tool_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

class ErrorResponse(BaseModel):
    """Réponse d'erreur."""
    error: str
    message: Optional[str] = None

class ApiInfo(BaseModel):
    """Informations sur l'API."""
    name: str
    version: str
    description: str 