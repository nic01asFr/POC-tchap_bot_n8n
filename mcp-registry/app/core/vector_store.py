"""
VectorStore module for indexing and searching MCP tools.

Ce module fournit une recherche vectorielle pour les outils MCP en utilisant
l'API Albert pour la génération d'embeddings au lieu de SentenceTransformers.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import json
import requests
import numpy as np
from ..config.settings import EmbeddingConfig

logger = logging.getLogger(__name__)

class AlbertEmbedder:
    """Client pour l'API d'embeddings d'Albert."""
    
    def __init__(self, api_url: str, api_key: str, model: str = "embeddings-small"):
        """
        Initialise le client d'embedding Albert.
        
        Args:
            api_url: URL de l'API Albert
            api_key: Clé API pour l'authentification
            model: Modèle d'embedding à utiliser
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Génère des embeddings pour les textes fournis en utilisant l'API Albert.
        
        Args:
            texts: Textes à transformer en embeddings
            
        Returns:
            Array numpy des embeddings
        """
        if not texts:
            return np.array([])
            
        try:
            embeddings_url = f"{self.api_url}/v1/embeddings"
            
            # Log détaillé des paramètres d'appel API
            payload = {"model": self.model, "input": texts}
            logger.info(f"Appel de l'API d'embeddings avec: URL={embeddings_url}, Modèle={self.model}, Nombre de textes={len(texts)}")
            logger.debug(f"Headers API: {self.headers}")
            
            response = requests.post(
                embeddings_url,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"Erreur lors de l'appel à l'API d'embeddings: {response.status_code} - {response.text}")
                # Retourner un embedding vide si l'appel échoue
                return np.zeros((len(texts), 1536))  # Dimension standard pour text-embedding-ada-002
                
            result = response.json()
            
            # Extraire les embeddings des résultats
            embeddings = []
            for item in result.get("data", []):
                embedding = item.get("embedding", [])
                if embedding:
                    embeddings.append(embedding)
                    
            if not embeddings:
                logger.warning("Aucun embedding reçu de l'API Albert")
                return np.zeros((len(texts), 1536))
                
            return np.array(embeddings)
            
        except Exception as e:
            logger.error(f"Exception lors de la génération d'embeddings: {str(e)}")
            # Retourner un embedding vide si une exception se produit
            return np.zeros((len(texts), 1536))


class SimpleVectorStore:
    """
    Version simplifiée du store vectoriel sans FAISS.
    
    Utilise une comparaison de similarité cosinus simple à la place de FAISS pour éviter
    les problèmes de compatibilité.
    """
    
    def __init__(self):
        """Initialise le store vectoriel simplifié."""
        self.embeddings = []
        self.tool_ids = []
    
    def add(self, embeddings: np.ndarray, tool_ids: List[str]):
        """
        Ajoute des embeddings au store.
        
        Args:
            embeddings: Embeddings à ajouter
            tool_ids: IDs des outils correspondants
        """
        self.embeddings = embeddings
        self.tool_ids = tool_ids
    
    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Tuple[int, float]]:
        """
        Recherche les embeddings les plus proches.
        
        Args:
            query_embedding: Embedding de la requête
            k: Nombre de résultats à retourner
            
        Returns:
            Liste de tuples (indice, score de similarité)
        """
        if len(self.embeddings) == 0:
            return []
            
        # Calculer la similarité cosinus
        dot_product = np.dot(self.embeddings, query_embedding.T).flatten()
        
        # Normaliser pour obtenir la similarité cosinus
        query_norm = np.linalg.norm(query_embedding)
        corpus_norm = np.linalg.norm(self.embeddings, axis=1)
        cosine_similarities = dot_product / (query_norm * corpus_norm)
        
        # Obtenir les indices triés
        sorted_indices = np.argsort(cosine_similarities)[::-1]
        
        # Retourner les k premiers résultats
        results = []
        for i in range(min(k, len(sorted_indices))):
            idx = sorted_indices[i]
            score = float(cosine_similarities[idx])
            results.append((idx, score))
            
        return results


class VectorStore:
    """
    Vector store for MCP tools using Albert API.
    
    Cette classe gère l'embedding et l'indexation des descriptions d'outils
    pour permettre la recherche sémantique.
    """
    
    def __init__(self, config: EmbeddingConfig):
        """
        Initialise le store vectoriel avec la configuration donnée.
        
        Args:
            config: Configuration pour le modèle d'embedding et le store vectoriel
        """
        self.config = config
        self.index = SimpleVectorStore()
        self.tool_ids = []
        
        # Récupérer la configuration Albert depuis les variables d'environnement
        self.albert_api_url = os.environ.get("ALBERT_API_URL", "https://albert.api.etalab.gouv.fr/")
        self.albert_api_token = os.environ.get("ALBERT_API_TOKEN", "")
        
        if not self.albert_api_token:
            logger.warning("ALBERT_API_TOKEN non défini, l'embedding et la recherche sémantique ne fonctionneront pas")
            
        # Initialiser le client d'embedding Albert
        self.embedding_model = AlbertEmbedder(
            api_url=self.albert_api_url,
            api_key=self.albert_api_token,
            model=os.environ.get("ALBERT_EMBEDDING_MODEL", "embeddings-small")
        )
    
    def build_index(self, tools: List[Dict[str, Any]]) -> None:
        """
        Construit un index à partir des outils fournis.
        
        Args:
            tools: Liste des dictionnaires d'outils avec métadonnées
        """
        if not tools:
            logger.warning("Aucun outil fourni pour l'indexation")
            self.index = SimpleVectorStore()
            self.tool_ids = []
            return
        
        try:
            # Extraire les IDs d'outils et générer du texte riche pour l'embedding
            self.tool_ids = []
            texts = []
            
            for tool in tools:
                tool_id = tool.get("id")
                if not tool_id:
                    continue
                
                self.tool_ids.append(tool_id)
                
                # Créer une représentation textuelle riche pour l'embedding
                text = f"{tool.get('name', '')} - {tool.get('description', '')}"
                
                # Ajouter des informations sur les paramètres si disponibles
                params = tool.get("parameters", {})
                if params and isinstance(params, dict) and "properties" in params:
                    param_properties = params.get("properties", {})
                    param_text = " ".join([
                        f"{name}: {prop.get('description', '')}"
                        for name, prop in param_properties.items()
                    ])
                    text += f" Parameters: {param_text}"
                
                texts.append(text)
            
            if not texts:
                logger.warning("Aucun outil valide pour l'indexation")
                self.index = SimpleVectorStore()
                return
                
            # Générer les embeddings avec Albert API
            embeddings = self.get_embeddings(texts)
            
            # Créer l'index simplifié
            self.index = SimpleVectorStore()
            self.index.add(embeddings, self.tool_ids)
            
            logger.info(f"Index construit avec {len(self.tool_ids)} outils")
        except Exception as e:
            logger.error(f"Échec de la construction de l'index: {str(e)}")
            self.index = SimpleVectorStore()
            self.tool_ids = []
    
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Génère des embeddings pour les textes fournis.
        
        Args:
            texts: Liste de textes à transformer en embeddings
            
        Returns:
            Array numpy des embeddings
        """
        if not self.embedding_model:
            logger.error("Modèle d'embedding non initialisé")
            # Retourner un embedding vide de dimension standard
            return np.zeros((len(texts), 1536))
        
        return self.embedding_model.get_embeddings(texts)
    
    def search(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        """
        Recherche des outils similaires à la requête.
        
        Args:
            query: La requête de recherche
            k: Nombre de résultats à retourner
            
        Returns:
            Liste de tuples (tool_id, score)
        """
        if not self.index or not self.tool_ids:
            logger.warning("Index non construit ou vide, impossible d'effectuer la recherche")
            return []
        
        try:
            # Obtenir l'embedding de la requête
            query_embedding = self.get_embeddings([query])
            
            # Rechercher dans l'index
            k = min(k, len(self.tool_ids))
            results = self.index.search(query_embedding, k)
            
            # Formater les résultats
            formatted_results = []
            for idx, score in results:
                if idx < 0 or idx >= len(self.tool_ids):
                    continue
                    
                tool_id = self.tool_ids[idx]
                formatted_results.append((tool_id, float(score)))
            
            return formatted_results
        except Exception as e:
            logger.error(f"Échec de la recherche: {str(e)}")
            return [] 