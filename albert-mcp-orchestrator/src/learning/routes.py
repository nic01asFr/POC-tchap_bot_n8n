from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from pydantic import BaseModel

from ..models.composition import CompositionStatus
from ..registry.storage import CompositionStorage
from .performance_analyzer import PerformanceAnalyzer
from .composition_optimizer import CompositionOptimizer
from ..data.metrics import MetricsStorage
from ..auth.dependencies import get_current_user
from ..config import settings
from loguru import logger


# Modèles de données pour les API
class OptimizationRequest(BaseModel):
    composition_id: str
    force: bool = False  # Force l'optimisation même avec peu de données


class OptimizationResponse(BaseModel):
    success: bool
    message: str
    original_id: Optional[str] = None
    optimized_id: Optional[str] = None
    metrics_found: bool = False
    optimization_summary: Optional[Dict[str, Any]] = None


class AnalysisRequest(BaseModel):
    composition_id: str
    days: Optional[int] = 30


class OptimizationSuggestion(BaseModel):
    type: str
    priority: str  
    message: str
    details: str
    step_id: Optional[str] = None
    step_name: Optional[str] = None
    optimization_type: Optional[str] = None
    current_config: Optional[Dict[str, Any]] = None
    suggested_config: Optional[Dict[str, Any]] = None


class AnalysisResponse(BaseModel):
    success: bool
    composition_id: str
    name: str
    status: Optional[str] = None
    metrics_found: bool = False
    overall_score: Optional[float] = None
    global_metrics: Optional[Dict[str, Any]] = None
    step_performance: Optional[Dict[str, Dict[str, Any]]] = None
    suggestions: Optional[List[OptimizationSuggestion]] = None
    message: Optional[str] = None


class BatchOptimizationRequest(BaseModel):
    composition_ids: Optional[List[str]] = None
    status: Optional[str] = "LEARNING"
    force: bool = False


class MetricsStorageRequest(BaseModel):
    composition_id: str
    metrics: Dict[str, Any]


class MetricsResponse(BaseModel):
    success: bool
    message: str
    metrics_count: Optional[int] = None
    composition_id: Optional[str] = None


# Router pour les endpoints d'apprentissage
learning_router = APIRouter(
    prefix="/learning",
    tags=["learning"],
    dependencies=[Depends(get_current_user)]
)


@learning_router.post("/optimize", response_model=OptimizationResponse)
async def optimize_composition(request: OptimizationRequest):
    """
    Optimise une composition en fonction de l'analyse de ses performances.
    Génère une nouvelle version avec des paramètres améliorés.
    """
    try:
        optimizer = CompositionOptimizer()
        storage = CompositionStorage()
        
        # Vérifier que la composition existe
        composition = storage.load_composition(request.composition_id)
        if not composition:
            raise HTTPException(status_code=404, detail=f"Composition {request.composition_id} non trouvée")
        
        # Demander l'optimisation
        result = optimizer.optimize_composition(request.composition_id)
        
        if not result["success"] and not request.force:
            return OptimizationResponse(
                success=False,
                message=result.get("error", "Pas assez de données pour l'optimisation"),
                original_id=request.composition_id,
                metrics_found=result.get("metrics_found", False)
            )
        
        # Si l'optimisation a réussi
        if result["success"]:
            return OptimizationResponse(
                success=True,
                message=f"Composition optimisée avec succès (version {result['optimized_composition']['version']})",
                original_id=request.composition_id,
                optimized_id=result["optimized_id"],
                metrics_found=True,
                optimization_summary=result.get("optimizations")
            )
        
        return OptimizationResponse(
            success=False,
            message="Échec de l'optimisation",
            original_id=request.composition_id
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de l'optimisation de {request.composition_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'optimisation: {str(e)}")


@learning_router.post("/analyze", response_model=AnalysisResponse)
async def analyze_composition(request: AnalysisRequest):
    """
    Analyse les performances d'une composition et suggère des optimisations.
    """
    try:
        analyzer = PerformanceAnalyzer()
        storage = CompositionStorage()
        
        # Vérifier que la composition existe
        composition = storage.load_composition(request.composition_id)
        if not composition:
            raise HTTPException(status_code=404, detail=f"Composition {request.composition_id} non trouvée")
        
        # Analyser la composition
        analysis = analyzer.analyze_composition(request.composition_id)
        
        if not analysis["metrics_found"]:
            return AnalysisResponse(
                success=True,
                composition_id=request.composition_id,
                name=composition.name,
                status=composition.status.value,
                metrics_found=False,
                message=analysis.get("message", "Pas assez de données pour l'analyse")
            )
        
        # Récupérer les suggestions d'optimisation
        optimizer = CompositionOptimizer(storage=storage, analyzer=analyzer)
        suggestions_result = optimizer.suggest_optimizations(request.composition_id)
        
        return AnalysisResponse(
            success=True,
            composition_id=request.composition_id,
            name=composition.name,
            status=composition.status.value,
            metrics_found=True,
            overall_score=analysis.get("overall_score"),
            global_metrics=analysis.get("global_metrics"),
            step_performance=analysis.get("step_performance"),
            suggestions=suggestions_result.get("suggestions") if suggestions_result.get("success") else []
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse de {request.composition_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse: {str(e)}")


@learning_router.post("/batch-optimize", response_model=Dict[str, OptimizationResponse])
async def optimize_multiple_compositions(request: BatchOptimizationRequest):
    """
    Optimise plusieurs compositions en une seule opération.
    """
    try:
        optimizer = CompositionOptimizer()
        
        # Si des IDs spécifiques sont fournis, les utiliser
        composition_ids = request.composition_ids
        
        # Sinon, récupérer les compositions du statut spécifié
        if not composition_ids and request.status:
            storage = CompositionStorage()
            try:
                status = CompositionStatus(request.status)
                compositions = storage.list_compositions(status=status)
                composition_ids = [c.id for c in compositions]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Statut invalide: {request.status}")
        
        if not composition_ids:
            return {}
        
        # Exécuter l'optimisation en batch
        results = optimizer.optimize_multiple_compositions(composition_ids)
        
        # Formater les résultats
        formatted_results = {}
        for comp_id, result in results.items():
            if result.get("success"):
                formatted_results[comp_id] = OptimizationResponse(
                    success=True,
                    message=f"Composition optimisée avec succès",
                    original_id=comp_id,
                    optimized_id=result.get("optimized_id"),
                    metrics_found=True,
                    optimization_summary=result.get("optimizations")
                )
            else:
                formatted_results[comp_id] = OptimizationResponse(
                    success=False,
                    message=result.get("error", "Échec de l'optimisation"),
                    original_id=comp_id,
                    metrics_found=result.get("metrics_found", False)
                )
        
        return formatted_results
    
    except Exception as e:
        logger.error(f"Erreur lors de l'optimisation par lot: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'optimisation par lot: {str(e)}")


@learning_router.post("/metrics", response_model=MetricsResponse)
async def store_metrics(request: MetricsStorageRequest):
    """
    Stocke des métriques d'exécution pour une composition.
    """
    try:
        metrics_storage = MetricsStorage()
        
        # Stocker les métriques
        success = metrics_storage.store_execution_metrics(
            composition_id=request.composition_id,
            metrics=request.metrics
        )
        
        if success:
            return MetricsResponse(
                success=True,
                message="Métriques stockées avec succès",
                composition_id=request.composition_id
            )
        else:
            return MetricsResponse(
                success=False,
                message="Échec du stockage des métriques",
                composition_id=request.composition_id
            )
    
    except Exception as e:
        logger.error(f"Erreur lors du stockage des métriques pour {request.composition_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du stockage des métriques: {str(e)}")


@learning_router.get("/metrics/{composition_id}", response_model=MetricsResponse)
async def get_metrics(
    composition_id: str,
    limit: Optional[int] = Query(10, description="Nombre maximum de métriques à récupérer"),
    latest: bool = Query(True, description="Récupérer les métriques les plus récentes")
):
    """
    Récupère les métriques d'exécution pour une composition.
    """
    try:
        metrics_storage = MetricsStorage()
        
        # Récupérer les métriques
        if latest:
            metrics = metrics_storage.get_latest_metrics(
                composition_id=composition_id,
                count=limit
            )
        else:
            metrics = metrics_storage.get_execution_metrics(
                composition_id=composition_id,
                limit=limit
            )
        
        return MetricsResponse(
            success=True,
            message=f"{len(metrics)} métriques récupérées",
            metrics_count=len(metrics),
            composition_id=composition_id
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des métriques pour {composition_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des métriques: {str(e)}")


@learning_router.get("/top-performers", response_model=List[AnalysisResponse])
async def get_top_performers(count: int = Query(5, description="Nombre de compositions à récupérer")):
    """
    Récupère les compositions les plus performantes.
    """
    try:
        analyzer = PerformanceAnalyzer()
        
        # Analyser toutes les compositions en apprentissage
        all_results = analyzer.analyze_all_learning_compositions()
        
        # Filtrer les résultats valides et les trier
        valid_results = [
            result for result in all_results.values()
            if result.get("success") and result.get("metrics_found", False)
        ]
        
        sorted_results = sorted(
            valid_results,
            key=lambda x: x.get("overall_score", 0),
            reverse=True  # Du plus haut au plus bas
        )
        
        # Limiter les résultats
        top_results = sorted_results[:count]
        
        # Formater les résultats
        formatted_results = []
        for result in top_results:
            formatted_results.append(
                AnalysisResponse(
                    success=True,
                    composition_id=result["composition_id"],
                    name=result["name"],
                    metrics_found=True,
                    overall_score=result.get("overall_score"),
                    global_metrics=result.get("global_metrics"),
                    status=result.get("status")
                )
            )
        
        return formatted_results
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des meilleures compositions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des meilleures compositions: {str(e)}") 