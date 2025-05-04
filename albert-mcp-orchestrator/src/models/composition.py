from typing import Dict, List, Optional, Any, Union, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum
import uuid
from datetime import datetime


class CompositionStatus(str, Enum):
    """État possible d'une composition."""
    DRAFT = "draft"            # En cours de création
    VALIDATED = "validated"    # Validée et prête à l'utilisation
    LEARNING = "learning"      # En phase d'apprentissage/amélioration
    PRODUCTION = "production"  # En production, utilisée activement
    ARCHIVED = "archived"      # Obsolète, mais conservée pour référence


class ToolDefinition(BaseModel):
    """Définition d'un outil MCP utilisé dans une composition."""
    name: str = Field(..., description="Nom de l'outil MCP")
    description: str = Field(..., description="Description de l'outil")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Paramètres de l'outil")
    required_parameters: List[str] = Field(default_factory=list, description="Paramètres obligatoires")


class CompositionStep(BaseModel):
    """Une étape individuelle dans une composition."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Identifiant unique de l'étape")
    name: str = Field(..., description="Nom de l'étape")
    description: str = Field(..., description="Description détaillée")
    tool: str = Field(..., description="Nom de l'outil MCP à utiliser")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Paramètres pour l'outil")
    conditional: Optional[Dict[str, Any]] = Field(None, description="Conditions d'exécution de l'étape")
    next_steps: List[str] = Field(default_factory=list, description="IDs des étapes suivantes")
    retry_strategy: Optional[Dict[str, Any]] = Field(None, description="Stratégie de nouvelle tentative en cas d'échec.\n"
        "Format: {\n"
        "  'max_retries': int,    # Nombre maximal de tentatives\n"
        "  'delay_ms': int,       # Délai entre les tentatives en ms\n"
        "  'fallback': {          # Stratégie de secours si toutes les tentatives échouent\n"
        "    'type': str,         # 'default_value', 'alternative_step', ou 'skip'\n"
        "    'value': dict,       # Pour type='default_value': valeur à utiliser\n"
        "    'step_id': str       # Pour type='alternative_step': ID de l'étape alternative\n"
        "  }\n"
        "}")
    timeout_seconds: int = Field(default=60, description="Délai d'expiration en secondes")


class DataMapping(BaseModel):
    """Mappage des données entre les étapes d'une composition."""
    source: str = Field(..., description="Source de la donnée (étape.sortie ou entrée)")
    target: str = Field(..., description="Cible de la donnée (étape.paramètre)")
    transformation: Optional[Dict[str, Any]] = Field(None, description="Transformation à appliquer")


class PerformanceMetrics(BaseModel):
    """Métriques de performance d'une composition."""
    avg_execution_time_ms: float = Field(default=0, description="Temps d'exécution moyen en ms")
    success_rate: float = Field(default=0, description="Taux de réussite (0-1)")
    error_rate: float = Field(default=0, description="Taux d'erreur (0-1)")
    usage_count: int = Field(default=0, description="Nombre d'utilisations")
    last_execution: Optional[datetime] = Field(None, description="Dernière exécution")
    user_feedback_score: float = Field(default=0, description="Score de satisfaction utilisateur (0-5)")


class CompositionTrigger(BaseModel):
    """Définition des déclencheurs pour une composition."""
    type: Literal["intent", "schedule", "event"] = Field(..., description="Type de déclencheur")
    configuration: Dict[str, Any] = Field(..., description="Configuration du déclencheur")
    
    @validator("configuration")
    def validate_config(cls, v, values):
        """Valider la configuration en fonction du type."""
        trigger_type = values.get("type")
        if trigger_type == "intent":
            required_fields = ["intent_patterns", "confidence_threshold"]
            if not all(field in v for field in required_fields):
                missing = [f for f in required_fields if f not in v]
                raise ValueError(f"Champs manquants pour le déclencheur d'intention: {missing}")
        elif trigger_type == "schedule":
            if "cron_expression" not in v:
                raise ValueError("Expression cron manquante pour le déclencheur planifié")
        elif trigger_type == "event":
            if "event_name" not in v:
                raise ValueError("Nom de l'événement manquant pour le déclencheur d'événement")
        return v


class Composition(BaseModel):
    """Modèle principal d'une composition MCP."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Identifiant unique")
    name: str = Field(..., description="Nom de la composition")
    description: str = Field(..., description="Description détaillée")
    version: str = Field(default="0.1.0", description="Version sémantique")
    status: CompositionStatus = Field(default=CompositionStatus.DRAFT, description="Statut de la composition")
    created_at: datetime = Field(default_factory=datetime.now, description="Date de création")
    updated_at: datetime = Field(default_factory=datetime.now, description="Date de dernière mise à jour")
    
    author: str = Field(..., description="Auteur de la composition")
    tags: List[str] = Field(default_factory=list, description="Tags pour la catégorisation")
    icons: Optional[str] = Field(None, description="Icône représentative (nom ou emoji)")
    
    tools: List[ToolDefinition] = Field(default_factory=list, description="Outils utilisés dans la composition")
    steps: List[CompositionStep] = Field(..., description="Étapes de la composition")
    data_mappings: List[DataMapping] = Field(default_factory=list, description="Mappages de données entre étapes")
    
    input_schema: Dict[str, Any] = Field(..., description="Schéma des entrées attendues")
    output_schema: Dict[str, Any] = Field(..., description="Schéma des sorties produites")
    
    triggers: List[CompositionTrigger] = Field(default_factory=list, description="Déclencheurs de la composition")
    performance_metrics: PerformanceMetrics = Field(default_factory=PerformanceMetrics, description="Métriques de performance")
    
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="Exemples d'utilisation")
    documentation_url: Optional[str] = Field(None, description="URL vers la documentation")
    
    @validator("updated_at", always=True)
    def update_timestamp(cls, v, values):
        """Mettre à jour le timestamp de mise à jour."""
        return datetime.now()
    
    @validator("steps")
    def validate_steps(cls, v):
        """Valider que les steps sont cohérentes (références valides)."""
        step_ids = {step.id for step in v}
        for step in v:
            for next_id in step.next_steps:
                if next_id not in step_ids:
                    raise ValueError(f"L'étape {step.id} référence une étape inexistante {next_id}")
        return v
    
    class Config:
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        } 