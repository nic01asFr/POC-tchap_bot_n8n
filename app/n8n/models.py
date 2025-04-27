"""
Modèles de données pour l'intégration n8n.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union


@dataclass
class N8nToolParameter:
    """Paramètre d'un outil n8n."""
    name: str
    type: str
    description: str
    required: bool = False
    default: Optional[Any] = None


@dataclass
class N8nTool:
    """Représentation d'un outil n8n."""
    id: str
    name: str
    type: str  # "mcp" ou "webhook"
    category: str
    description: str
    url: str
    parameters: List[N8nToolParameter] = field(default_factory=list)
    schema_url: Optional[str] = None


@dataclass
class N8nCategory:
    """Catégorie d'outils n8n."""
    name: str
    tools: List[N8nTool] = field(default_factory=list)


@dataclass
class N8nExecutionResult:
    """Résultat d'exécution d'un outil n8n."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None 