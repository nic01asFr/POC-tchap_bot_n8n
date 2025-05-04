"""
Client API pour interagir avec l'API Albert Tchapbot.

Ce module fournit un client pour les interactions avec l'API Albert Tchapbot,
permettant l'enregistrement d'outils, l'exécution de commandes et la génération d'embeddings.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Union

import aiohttp
import numpy as np
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings

logger = logging.getLogger(__name__)

class AlbertAPIClient:
    """Client pour interagir avec l'API Albert Tchapbot."""
    
    def __init__(
        self, 
        api_url: Optional[str] = None, 
        api_key: Optional[str] = None,
        default_model: Optional[str] = None
    ):
        """
        Initialise le client API Albert.
        
        Args:
            api_url: URL de base de l'API Albert (par défaut: valeur de ALBERT_TCHAP_API_URL)
            api_key: Clé API pour l'authentification (par défaut: valeur de ALBERT_TCHAP_API_KEY)
            default_model: Modèle par défaut à utiliser (par défaut: valeur de ALBERT_DEFAULT_MODEL)
        """
        self.api_url = api_url or settings.ALBERT_TCHAP_API_URL
        self.api_key = api_key or settings.ALBERT_TCHAP_API_KEY
        self.default_model = default_model or settings.ALBERT_DEFAULT_MODEL
        
        # En-têtes par défaut pour les requêtes
        self.headers = {
            "Content-Type": "application/json"
        }
        
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
    
    def _check_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Vérifie la réponse de l'API et renvoie les données JSON.
        
        Args:
            response: Objet de réponse HTTP
            
        Returns:
            Données JSON de la réponse
            
        Raises:
            Exception: Si la requête n'a pas réussi
        """
        if not response.ok:
            error_message = f"Erreur API Albert: {response.status_code} - {response.text}"
            logger.error(error_message)
            response.raise_for_status()
        
        return response.json()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def register_tools(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Enregistre des outils auprès de l'API Albert.
        
        Args:
            tools: Liste des outils à enregistrer
            
        Returns:
            Réponse JSON de l'API avec au moins les champs 'success' et 'message'
            
        Raises:
            Exception: Si l'enregistrement échoue
        """
        if not tools:
            logger.warning("Aucun outil à enregistrer")
            return {"success": True, "message": "Aucun outil à enregistrer"}
        
        endpoint = f"{self.api_url}/api/v1/tools/register"
        payload = {"tools": tools}
        
        try:
            logger.debug(f"Enregistrement de {len(tools)} outils auprès d'Albert API")
            response = requests.post(endpoint, headers=self.headers, json=payload)
            result = self._check_response(response)
            
            # Assurer un format de réponse cohérent
            if "success" not in result:
                result["success"] = response.status_code == 200
            if "message" not in result:
                result["message"] = "Enregistrement effectué" if result["success"] else "Échec de l'enregistrement"
                
            return result
        except Exception as e:
            logger.error(f"Échec de l'enregistrement des outils: {str(e)}")
            return {"success": False, "message": f"Erreur: {str(e)}"}
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def execute_tool(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exécute un outil via l'API Albert.
        
        Args:
            tool_name: Nom de l'outil à exécuter
            parameters: Paramètres pour l'outil
            model: Modèle à utiliser pour l'exécution (facultatif)
            
        Returns:
            Résultat de l'exécution de l'outil
            
        Raises:
            Exception: Si l'exécution échoue
        """
        endpoint = f"{self.api_url}/api/v1/tools/execute"
        payload = {
            "tool": tool_name,
            "parameters": parameters,
            "model": model or self.default_model
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                logger.debug(f"Exécution de l'outil {tool_name} via Albert API")
                async with session.post(endpoint, headers=self.headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        error_message = f"Erreur d'exécution de l'outil: {response.status} - {error_text}"
                        logger.error(error_message)
                        response.raise_for_status()
                    
                    result = await response.json()
                    return result
            except Exception as e:
                logger.error(f"Échec de l'exécution de l'outil {tool_name}: {str(e)}")
                raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def generate_embedding(
        self, 
        text: str,
        model: Optional[str] = None
    ) -> np.ndarray:
        """
        Génère un embedding vectoriel pour un texte via l'API Albert.
        
        Args:
            text: Texte pour lequel générer l'embedding
            model: Modèle d'embedding à utiliser (facultatif)
            
        Returns:
            Array NumPy contenant l'embedding
            
        Raises:
            Exception: Si la génération échoue
        """
        endpoint = f"{self.api_url}/api/v1/embeddings"
        payload = {
            "input": text,
            "model": model or settings.ALBERT_EMBEDDING_MODEL
        }
        
        try:
            logger.debug(f"Génération d'embedding via Albert API")
            response = requests.post(endpoint, headers=self.headers, json=payload)
            result = self._check_response(response)
            
            # Extraire l'embedding du résultat
            embedding = result.get("data", [])[0].get("embedding", [])
            if not embedding:
                raise ValueError("Aucun embedding reçu de l'API Albert")
                
            return np.array(embedding, dtype=np.float32)
            
        except Exception as e:
            logger.error(f"Échec de la génération d'embedding: {str(e)}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def rerank_documents(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        model: Optional[str] = None,
        top_n: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Réordonne les documents par pertinence par rapport à la requête.
        
        Args:
            query: La requête de recherche
            documents: Liste de documents à réordonner
            model: Modèle de reranking à utiliser (facultatif)
            top_n: Nombre maximum de documents à retourner (facultatif)
            
        Returns:
            Liste des documents réordonnés avec scores
            
        Raises:
            Exception: Si le reranking échoue
        """
        endpoint = f"{self.api_url}/api/v1/rerank"
        payload = {
            "query": query,
            "documents": documents,
            "model": model or settings.ALBERT_RERANKING_MODEL
        }
        
        if top_n is not None:
            payload["top_n"] = top_n
        
        try:
            logger.debug(f"Reranking de {len(documents)} documents via Albert API")
            response = requests.post(endpoint, headers=self.headers, json=payload)
            result = self._check_response(response)
            
            # Extraire les documents réordonnés du résultat
            reranked_docs = result.get("results", [])
            if not reranked_docs:
                logger.warning("Aucun document réordonné reçu de l'API Albert")
                return documents  # Renvoyer les documents d'origine en cas d'échec
                
            return reranked_docs
            
        except Exception as e:
            logger.error(f"Échec du reranking: {str(e)}")
            raise 