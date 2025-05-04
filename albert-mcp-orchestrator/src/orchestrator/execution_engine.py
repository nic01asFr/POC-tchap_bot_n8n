from typing import Dict, List, Optional, Any, Union, Callable
import asyncio
import time
from datetime import datetime
import json
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import uuid
import aiohttp

from ..models.composition import Composition, CompositionStep
from ..registry.storage import CompositionStorage
from .context_manager import ExecutionContext
from .data_transformer import DataTransformer
from .monitor import ExecutionMonitor
from ..config import settings
from loguru import logger


class ExecutionEngine:
    """
    Moteur d'exécution des compositions MCP.
    Gère l'exécution des compositions en appelant les outils appropriés.
    """
    
    def __init__(self, 
                 storage: Optional[CompositionStorage] = None,
                 monitor: Optional[ExecutionMonitor] = None):
        """
        Initialise le moteur d'exécution.
        
        Args:
            storage: Gestionnaire de stockage (crée un nouveau si None)
            monitor: Moniteur d'exécution (crée un nouveau si None)
        """
        self.storage = storage or CompositionStorage()
        self.monitor = monitor or ExecutionMonitor()
        self.transformer = DataTransformer()
        self.timeout_seconds = settings.EXECUTION_TIMEOUT_SECONDS
        self.albert_api_url = settings.ALBERT_TCHAP_API_URL
        self.albert_api_key = settings.ALBERT_TCHAP_API_KEY
    
    async def execute_composition(self, 
                                 composition_id: str, 
                                 input_data: Dict[str, Any],
                                 execution_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Exécute une composition avec les données d'entrée fournies.
        
        Args:
            composition_id: L'ID de la composition à exécuter
            input_data: Les données d'entrée
            execution_id: ID d'exécution (généré si None)
        
        Returns:
            Résultat de l'exécution
        """
        # Générer un ID d'exécution si non fourni
        if execution_id is None:
            execution_id = str(uuid.uuid4())
        
        # Charger la composition
        composition = self.storage.load_composition(composition_id)
        if not composition:
            error_msg = f"Composition {composition_id} non trouvée"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "execution_id": execution_id
            }
        
        # Créer le contexte d'exécution
        context = ExecutionContext(
            composition=composition,
            input_data=input_data,
            execution_id=execution_id
        )
        
        # Initialiser le monitoring
        self.monitor.start_execution(context)
        start_time = time.time()
        
        try:
            # Valider les données d'entrée
            self._validate_input(composition, input_data)
            
            # Trouver la première étape
            first_steps = self._find_starting_steps(composition)
            if not first_steps:
                raise ValueError("Aucune étape de départ trouvée dans la composition")
            
            # Exécuter le workflow
            results = await self._execute_workflow(context, first_steps)
            
            # Transformer la sortie selon le schéma
            output = self.transformer.transform_output(results, composition.output_schema)
            
            execution_time = time.time() - start_time
            
            # Finaliser le monitoring
            self.monitor.end_execution(context, True, output, execution_time)
            
            return {
                "success": True,
                "data": output,
                "execution_id": execution_id,
                "execution_time_ms": int(execution_time * 1000)
            }
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Erreur lors de l'exécution de {composition_id}: {e}")
            
            # Enregistrer l'échec
            self.monitor.end_execution(context, False, {"error": str(e)}, execution_time)
            
            return {
                "success": False,
                "error": str(e),
                "execution_id": execution_id,
                "execution_time_ms": int(execution_time * 1000)
            }
    
    def _validate_input(self, composition: Composition, input_data: Dict[str, Any]) -> None:
        """
        Valide les données d'entrée selon le schéma.
        
        Args:
            composition: La composition
            input_data: Les données d'entrée
        
        Raises:
            ValueError: Si les données d'entrée sont invalides
        """
        schema = composition.input_schema
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        
        # Vérifier les champs requis
        for field in required:
            if field not in input_data:
                raise ValueError(f"Champ requis manquant: {field}")
        
        # Vérifier les types (validation de base)
        for field, value in input_data.items():
            if field in properties:
                prop = properties[field]
                field_type = prop.get("type")
                
                if field_type == "string" and not isinstance(value, str):
                    raise ValueError(f"Le champ {field} doit être une chaîne")
                elif field_type == "number" and not isinstance(value, (int, float)):
                    raise ValueError(f"Le champ {field} doit être un nombre")
                elif field_type == "integer" and not isinstance(value, int):
                    raise ValueError(f"Le champ {field} doit être un entier")
                elif field_type == "boolean" and not isinstance(value, bool):
                    raise ValueError(f"Le champ {field} doit être un booléen")
                elif field_type == "array" and not isinstance(value, list):
                    raise ValueError(f"Le champ {field} doit être un tableau")
                elif field_type == "object" and not isinstance(value, dict):
                    raise ValueError(f"Le champ {field} doit être un objet")
    
    def _find_starting_steps(self, composition: Composition) -> List[CompositionStep]:
        """
        Trouve les étapes de départ d'une composition.
        
        Args:
            composition: La composition
        
        Returns:
            Liste des étapes de départ
        """
        # Trouver toutes les étapes qui sont référencées comme étapes suivantes
        next_steps_ids = set()
        for step in composition.steps:
            next_steps_ids.update(step.next_steps)
        
        # Les étapes de départ sont celles qui ne sont pas référencées comme étapes suivantes
        starting_steps = [
            step for step in composition.steps 
            if step.id not in next_steps_ids
        ]
        
        return starting_steps
    
    async def _execute_workflow(self, 
                               context: ExecutionContext, 
                               steps: List[CompositionStep]) -> Dict[str, Any]:
        """
        Exécute un workflow de plusieurs étapes.
        
        Args:
            context: Contexte d'exécution
            steps: Liste des étapes à exécuter
        
        Returns:
            Résultats de l'exécution
        """
        all_results = {}
        
        for step in steps:
            try:
                # Vérifier si l'étape est conditionnelle
                if step.conditional and not self._evaluate_condition(step.conditional, context):
                    logger.info(f"Étape {step.id} ignorée car la condition n'est pas satisfaite")
                    continue
                
                # Exécuter l'étape
                logger.info(f"Exécution de l'étape {step.id} ({step.name})")
                step_result = await self._execute_step(context, step)
                
                # Stocker le résultat
                context.add_step_result(step.id, step_result)
                all_results[step.id] = step_result
                
                # Trouver et exécuter les étapes suivantes
                next_steps = [
                    next_step for next_step in context.composition.steps
                    if next_step.id in step.next_steps
                ]
                
                if next_steps:
                    next_results = await self._execute_workflow(context, next_steps)
                    all_results.update(next_results)
            
            except Exception as e:
                logger.error(f"Erreur lors de l'exécution de l'étape {step.id}: {e}")
                
                # Gérer la stratégie de retry si définie
                if step.retry_strategy:
                    max_retries = step.retry_strategy.get("max_retries", 3)
                    delay_ms = step.retry_strategy.get("delay_ms", 1000)
                    
                    retry_success = False
                    for retry in range(max_retries):
                        try:
                            logger.info(f"Tentative {retry+1}/{max_retries} pour l'étape {step.id}")
                            await asyncio.sleep(delay_ms / 1000)  # Convertir ms en secondes
                            step_result = await self._execute_step(context, step)
                            context.add_step_result(step.id, step_result)
                            all_results[step.id] = step_result
                            
                            retry_success = True
                            
                            # Succès: exécuter les étapes suivantes
                            next_steps = [
                                next_step for next_step in context.composition.steps
                                if next_step.id in step.next_steps
                            ]
                            
                            if next_steps:
                                next_results = await self._execute_workflow(context, next_steps)
                                all_results.update(next_results)
                            
                            break  # Sortir de la boucle si réussi
                        
                        except Exception as retry_e:
                            logger.error(f"Échec de la tentative {retry+1} pour {step.id}: {retry_e}")
                            if retry == max_retries - 1:  # Dernière tentative
                                context.add_step_error(step.id, str(retry_e))
                                all_results[step.id] = {"error": str(retry_e)}
                    
                    # Si aucune tentative n'a réussi et qu'il y a un fallback défini
                    if not retry_success and step.retry_strategy.get("fallback"):
                        fallback = step.retry_strategy.get("fallback")
                        fallback_type = fallback.get("type")
                        
                        if fallback_type == "default_value":
                            # Utiliser une valeur par défaut pour cette étape
                            default_result = fallback.get("value", {})
                            logger.info(f"Utilisation du fallback (valeur par défaut) pour {step.id}")
                            context.add_step_result(step.id, default_result)
                            all_results[step.id] = default_result
                            
                            # Continuer avec les étapes suivantes
                            next_steps = [
                                next_step for next_step in context.composition.steps
                                if next_step.id in step.next_steps
                            ]
                            
                            if next_steps:
                                next_results = await self._execute_workflow(context, next_steps)
                                all_results.update(next_results)
                        
                        elif fallback_type == "alternative_step":
                            # Exécuter une étape alternative
                            alternative_step_id = fallback.get("step_id")
                            if alternative_step_id:
                                alternative_step = next((s for s in context.composition.steps if s.id == alternative_step_id), None)
                                
                                if alternative_step:
                                    logger.info(f"Exécution de l'étape alternative {alternative_step_id} pour {step.id}")
                                    try:
                                        alt_result = await self._execute_step(context, alternative_step)
                                        context.add_step_result(step.id, alt_result)  # Utiliser l'ID de l'étape originale
                                        all_results[step.id] = alt_result
                                        
                                        # Continuer avec les étapes suivantes de l'étape originale
                                        next_steps = [
                                            next_step for next_step in context.composition.steps
                                            if next_step.id in step.next_steps
                                        ]
                                        
                                        if next_steps:
                                            next_results = await self._execute_workflow(context, next_steps)
                                            all_results.update(next_results)
                                    except Exception as alt_e:
                                        logger.error(f"Échec de l'étape alternative {alternative_step_id}: {alt_e}")
                                        context.add_step_error(step.id, f"Fallback échoué: {str(alt_e)}")
                                        all_results[step.id] = {"error": f"Fallback échoué: {str(alt_e)}"}
                                else:
                                    logger.error(f"Étape alternative {alternative_step_id} non trouvée")
                                    context.add_step_error(step.id, f"Étape alternative non trouvée: {alternative_step_id}")
                                    all_results[step.id] = {"error": f"Étape alternative non trouvée: {alternative_step_id}"}
                        
                        elif fallback_type == "skip":
                            # Ignorer cette étape et continuer avec les suivantes
                            logger.info(f"Fallback: Ignorer l'étape {step.id} et continuer")
                            all_results[step.id] = {"skipped": True, "reason": "Fallback skip"}
                            
                            # Continuer avec les étapes suivantes
                            next_steps = [
                                next_step for next_step in context.composition.steps
                                if next_step.id in step.next_steps
                            ]
                            
                            if next_steps:
                                next_results = await self._execute_workflow(context, next_steps)
                                all_results.update(next_results)
                else:
                    # Pas de stratégie de retry: enregistrer l'erreur
                    context.add_step_error(step.id, str(e))
                    all_results[step.id] = {"error": str(e)}
        
        return all_results
    
    async def _execute_step(self, 
                           context: ExecutionContext, 
                           step: CompositionStep) -> Dict[str, Any]:
        """
        Exécute une étape individuelle d'une composition.
        
        Args:
            context: Contexte d'exécution
            step: L'étape à exécuter
        
        Returns:
            Résultat de l'exécution de l'étape
        """
        start_time = time.time()
        self.monitor.start_step(context, step.id)
        
        try:
            # Préparer les paramètres
            parameters = self._prepare_parameters(context, step)
            
            # Exécuter l'outil
            result = await self._execute_tool(step.tool, parameters, step.timeout_seconds)
            
            execution_time = time.time() - start_time
            self.monitor.end_step(context, step.id, True, result, execution_time)
            
            return result
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Erreur lors de l'exécution de l'étape {step.id}: {e}")
            
            self.monitor.end_step(context, step.id, False, {"error": str(e)}, execution_time)
            raise
    
    def _prepare_parameters(self, 
                           context: ExecutionContext, 
                           step: CompositionStep) -> Dict[str, Any]:
        """
        Prépare les paramètres pour une étape en appliquant les mappages.
        
        Args:
            context: Contexte d'exécution
            step: L'étape pour laquelle préparer les paramètres
        
        Returns:
            Paramètres préparés
        """
        # Paramètres de base
        parameters = step.parameters.copy()
        
        # Appliquer les mappages de données
        for mapping in context.composition.data_mappings:
            if mapping.target.startswith(f"{step.id}."):
                param_name = mapping.target.split(".")[-1]
                
                # Récupérer la valeur source
                if mapping.source.startswith("input."):
                    input_field = mapping.source.split(".")[-1]
                    value = context.input_data.get(input_field)
                else:
                    # Format: "step_id.output_field"
                    source_parts = mapping.source.split(".")
                    source_step_id = source_parts[0]
                    output_field = source_parts[1] if len(source_parts) > 1 else None
                    
                    # Récupérer le résultat de l'étape source
                    step_result = context.get_step_result(source_step_id)
                    
                    if output_field:
                        value = step_result.get(output_field) if step_result else None
                    else:
                        value = step_result
                
                # Appliquer la transformation si définie
                if mapping.transformation:
                    value = self.transformer.apply_transformation(value, mapping.transformation)
                
                # Affecter au paramètre
                parameters[param_name] = value
        
        return parameters
    
    def _evaluate_condition(self, condition: Dict[str, Any], context: ExecutionContext) -> bool:
        """
        Évalue une condition pour une étape conditionnelle.
        
        Args:
            condition: La condition à évaluer
            context: Contexte d'exécution
        
        Returns:
            True si la condition est satisfaite, False sinon
        """
        condition_type = condition.get("type", "simple")
        
        if condition_type == "simple":
            # Format: {"field": "step_id.result_field", "operator": "eq", "value": "expected_value"}
            field = condition["field"]
            operator = condition["operator"]
            expected_value = condition["value"]
            
            # Récupérer la valeur réelle
            actual_value = None
            
            if field.startswith("input."):
                input_field = field.split(".")[-1]
                actual_value = context.input_data.get(input_field)
            else:
                # Format: "step_id.result_field"
                parts = field.split(".")
                step_id = parts[0]
                result_field = parts[1] if len(parts) > 1 else None
                
                step_result = context.get_step_result(step_id)
                
                if result_field:
                    actual_value = step_result.get(result_field) if step_result else None
                else:
                    actual_value = step_result
            
            # Évaluer l'opérateur
            if operator == "eq":
                return actual_value == expected_value
            elif operator == "neq":
                return actual_value != expected_value
            elif operator == "gt":
                return actual_value > expected_value
            elif operator == "gte":
                return actual_value >= expected_value
            elif operator == "lt":
                return actual_value < expected_value
            elif operator == "lte":
                return actual_value <= expected_value
            elif operator == "in":
                return actual_value in expected_value
            elif operator == "contains":
                return expected_value in actual_value
            elif operator == "exists":
                return actual_value is not None
            else:
                logger.warning(f"Opérateur inconnu: {operator}")
                return False
        
        elif condition_type == "and":
            # Format: {"type": "and", "conditions": [condition1, condition2, ...]}
            subconditions = condition.get("conditions", [])
            return all(self._evaluate_condition(subcond, context) for subcond in subconditions)
        
        elif condition_type == "or":
            # Format: {"type": "or", "conditions": [condition1, condition2, ...]}
            subconditions = condition.get("conditions", [])
            return any(self._evaluate_condition(subcond, context) for subcond in subconditions)
        
        elif condition_type == "not":
            # Format: {"type": "not", "condition": condition}
            subcondition = condition.get("condition", {})
            return not self._evaluate_condition(subcondition, context)
        
        else:
            logger.warning(f"Type de condition inconnu: {condition_type}")
            return False
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _execute_tool(self, 
                           tool_name: str, 
                           parameters: Dict[str, Any],
                           timeout_seconds: Optional[int] = None) -> Dict[str, Any]:
        """
        Exécute un outil MCP.
        
        Args:
            tool_name: Nom de l'outil à exécuter
            parameters: Paramètres pour l'outil
            timeout_seconds: Délai d'expiration en secondes
            
        Returns:
            Résultat de l'exécution
        """
        # Déterminer si l'outil est un outil Albert ou un outil direct
        if tool_name.startswith("albert:"):
            # Exécution via Albert API
            return await self._execute_tool_via_albert(tool_name[7:], parameters, timeout_seconds)
        else:
            # Exécution directe via le MCP Registry
            return await self._execute_tool_via_registry(tool_name, parameters, timeout_seconds)
    
    async def _execute_tool_via_albert(self, 
                                     tool_name: str, 
                                     parameters: Dict[str, Any],
                                     timeout_seconds: Optional[int] = None) -> Dict[str, Any]:
        """
        Exécute un outil via Albert API.
        
        Args:
            tool_name: Nom de l'outil Albert à exécuter
            parameters: Paramètres pour l'outil
            timeout_seconds: Délai d'expiration en secondes
            
        Returns:
            Résultat de l'exécution
        """
        try:
            from ..integration.albert_client import AlbertAPIClient
            
            # Initialiser le client Albert API
            client = AlbertAPIClient()
            
            # Convertir en asynchrone si nécessaire
            if timeout_seconds is None:
                timeout_seconds = settings.DEFAULT_STEP_TIMEOUT
            
            # Exécuter l'outil via Albert API
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: client.execute_tool(tool_name, parameters)
            )
            
            # Vérifier si l'exécution a échoué
            if "error" in result:
                raise Exception(f"Erreur lors de l'exécution de l'outil {tool_name}: {result.get('error')}")
            
            return result
        except ImportError:
            logger.error("Module d'intégration Albert non disponible")
            raise Exception("Module d'intégration Albert non disponible")
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de l'outil {tool_name} via Albert: {str(e)}")
            raise
    
    async def _execute_tool_via_registry(self, 
                                       tool_name: str, 
                                       parameters: Dict[str, Any],
                                       timeout_seconds: Optional[int] = None) -> Dict[str, Any]:
        """
        Exécute un outil via le MCP Registry.
        
        Args:
            tool_name: Nom de l'outil à exécuter
            parameters: Paramètres pour l'outil
            timeout_seconds: Délai d'expiration en secondes
            
        Returns:
            Résultat de l'exécution
        """
        timeout = timeout_seconds or settings.EXECUTION_TIMEOUT_SECONDS
        timeout = aiohttp.ClientTimeout(total=timeout)
        
        # Récupérer les informations de l'outil depuis le registry
        mcp_registry_url = settings.MCP_REGISTRY_URL
        tool_endpoint = f"{mcp_registry_url}/tools/{tool_name}/execute"
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.post(
                    tool_endpoint,
                    json=parameters,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {settings.MCP_REGISTRY_API_KEY}"
                    }
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Erreur {response.status} lors de l'exécution de l'outil {tool_name}: {error_text}")
                        raise Exception(f"Erreur {response.status}: {error_text}")
                    
                    return await response.json()
            
            except aiohttp.ClientError as e:
                logger.error(f"Erreur de connexion lors de l'exécution de l'outil {tool_name}: {e}")
                raise Exception(f"Erreur de connexion: {str(e)}")
            except Exception as e:
                logger.error(f"Erreur lors de l'exécution de l'outil {tool_name}: {e}")
                raise 