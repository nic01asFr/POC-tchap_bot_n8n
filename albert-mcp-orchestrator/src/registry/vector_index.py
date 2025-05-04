import os
import json
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
import redis
from redis.exceptions import ConnectionError
from sentence_transformers import SentenceTransformer
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models.composition import Composition, CompositionStatus
from ..config import settings
from loguru import logger
from .storage import CompositionStorage


class VectorIndex:
    """
    Index vectoriel pour la recherche sémantique des compositions MCP.
    Utilise des embeddings pour trouver les compositions les plus pertinentes
    pour une requête donnée.
    """
    
    def __init__(self):
        """Initialise l'index vectoriel."""
        self.redis_host = settings.REDIS_HOST
        self.redis_port = settings.REDIS_PORT
        self.redis_password = settings.REDIS_PASSWORD
        self.redis_db = settings.REDIS_DB
        
        self.embeddings_model_name = settings.EMBEDDINGS_MODEL
        self.similarity_threshold = settings.SIMILARITY_THRESHOLD
        self.max_results = settings.MAX_COMPOSITIONS_RESULTS
        
        self.composition_storage = CompositionStorage()
        
        # Initialiser le modèle d'embeddings
        try:
            self.embeddings_model = SentenceTransformer(self.embeddings_model_name)
            logger.info(f"Modèle d'embeddings '{self.embeddings_model_name}' chargé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle d'embeddings: {e}")
            raise
        
        # Initialiser la connexion Redis
        self._init_redis_connection()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _init_redis_connection(self):
        """Initialise la connexion à Redis avec retry."""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                db=self.redis_db,
                decode_responses=True
            )
            
            # Vérifier la connexion
            self.redis_client.ping()
            logger.info(f"Connexion à Redis établie avec succès à {self.redis_host}:{self.redis_port}")
        except ConnectionError as e:
            logger.error(f"Impossible de se connecter à Redis: {e}")
            raise
    
    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Génère un embedding pour un texte donné.
        
        Args:
            text: Le texte à encoder
        
        Returns:
            L'embedding sous forme de vecteur numpy
        """
        # Vérifie si l'option d'utilisation d'Albert API est activée
        use_albert_embedding = getattr(settings, 'USE_ALBERT_EMBEDDING', False)
        
        if use_albert_embedding:
            try:
                # Essayer d'utiliser Albert API pour les embeddings
                from ..integration.albert_client import AlbertAPIClient
                
                logger.debug(f"Utilisation d'Albert API pour générer l'embedding")
                client = AlbertAPIClient()
                return client.get_embedding(text)
            except ImportError:
                logger.warning("Module Albert API non disponible, utilisation du modèle local")
                # Fallback au modèle local
                return self.embeddings_model.encode(text)
            except Exception as e:
                logger.warning(f"Erreur lors de l'utilisation d'Albert API pour l'embedding: {e}, utilisation du modèle local")
                # Fallback au modèle local
                return self.embeddings_model.encode(text)
        else:
            # Utilisation du modèle local d'embeddings
            return self.embeddings_model.encode(text)
    
    def index_composition(self, composition: Composition) -> bool:
        """
        Indexe une composition dans Redis.
        
        Args:
            composition: La composition à indexer
        
        Returns:
            True si l'indexation a réussi, False sinon
        """
        try:
            # Créer le texte à encoder
            index_text = f"{composition.name} {composition.description} {' '.join(composition.tags)}"
            
            # Générer l'embedding
            embedding = self.generate_embedding(index_text).tolist()
            
            # Stocker dans Redis
            composition_key = f"composition:{composition.id}"
            embedding_key = f"embedding:{composition.id}"
            
            # Stocker les données de la composition
            self.redis_client.set(composition_key, json.dumps(composition.dict()))
            
            # Stocker l'embedding
            self.redis_client.set(embedding_key, json.dumps(embedding))
            
            # Ajouter à l'index par statut
            self.redis_client.sadd(f"compositions:{composition.status.value}", composition.id)
            
            # Ajouter à l'index par tag
            for tag in composition.tags:
                self.redis_client.sadd(f"tag:{tag}", composition.id)
            
            logger.info(f"Composition '{composition.name}' (ID: {composition.id}) indexée avec succès")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'indexation de la composition {composition.id}: {e}")
            return False
    
    def batch_index_compositions(self, compositions: List[Composition]) -> Tuple[int, int]:
        """
        Indexe un lot de compositions.
        
        Args:
            compositions: Liste des compositions à indexer
        
        Returns:
            Tuple (nombre de succès, nombre d'échecs)
        """
        success = 0
        failures = 0
        
        for composition in compositions:
            if self.index_composition(composition):
                success += 1
            else:
                failures += 1
        
        logger.info(f"Indexation par lot terminée: {success} succès, {failures} échecs")
        return success, failures
    
    def remove_from_index(self, composition_id: str) -> bool:
        """
        Supprime une composition de l'index.
        
        Args:
            composition_id: L'ID de la composition à supprimer
        
        Returns:
            True si la suppression a réussi, False sinon
        """
        try:
            # Récupérer la composition pour les métadonnées
            composition_key = f"composition:{composition_id}"
            composition_data = self.redis_client.get(composition_key)
            
            if composition_data:
                # Récupérer les données pour nettoyer les index
                composition_dict = json.loads(composition_data)
                status = composition_dict.get("status")
                tags = composition_dict.get("tags", [])
                
                # Supprimer des sets
                if status:
                    self.redis_client.srem(f"compositions:{status}", composition_id)
                
                for tag in tags:
                    self.redis_client.srem(f"tag:{tag}", composition_id)
            
            # Supprimer les clés principales
            self.redis_client.delete(composition_key)
            self.redis_client.delete(f"embedding:{composition_id}")
            
            logger.info(f"Composition {composition_id} supprimée de l'index")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de {composition_id} de l'index: {e}")
            return False
    
    def search_compositions(self, query: str, limit: int = None, statuses: List[CompositionStatus] = None) -> List[Dict[str, Any]]:
        """
        Recherche des compositions pertinentes pour une requête.
        
        Args:
            query: La requête de recherche
            limit: Nombre maximum de résultats (utilise la config par défaut si None)
            statuses: Liste des statuts à inclure (tous si None)
        
        Returns:
            Liste des compositions avec score de similarité, triée par pertinence
        """
        if limit is None:
            limit = self.max_results
        
        if statuses is None:
            statuses = [CompositionStatus.VALIDATED, CompositionStatus.PRODUCTION]
        
        try:
            # Générer l'embedding de la requête
            query_embedding = self.generate_embedding(query).tolist()
            
            # Récupérer tous les IDs des compositions filtrées par statut
            composition_ids = []
            for status in statuses:
                status_compositions = self.redis_client.smembers(f"compositions:{status.value}")
                composition_ids.extend(status_compositions)
            
            # Si aucune composition n'est trouvée, retourner une liste vide
            if not composition_ids:
                return []
            
            # Calculer les scores de similarité pour toutes les compositions
            similarities = []
            
            for comp_id in composition_ids:
                embedding_key = f"embedding:{comp_id}"
                composition_key = f"composition:{comp_id}"
                
                # Récupérer l'embedding et les données de la composition
                embedding_json = self.redis_client.get(embedding_key)
                composition_json = self.redis_client.get(composition_key)
                
                if embedding_json and composition_json:
                    try:
                        # Calculer la similarité cosinus
                        comp_embedding = json.loads(embedding_json)
                        similarity = self._cosine_similarity(query_embedding, comp_embedding)
                        
                        # Extraire les métadonnées de la composition
                        comp_data = json.loads(composition_json)
                        
                        # Ajouter aux résultats
                        if similarity >= self.similarity_threshold:
                            similarities.append({
                                "id": comp_id,
                                "name": comp_data.get("name"),
                                "description": comp_data.get("description"),
                                "status": comp_data.get("status"),
                                "tags": comp_data.get("tags", []),
                                "similarity": similarity,
                                "composition": comp_data
                            })
                    except Exception as e:
                        logger.error(f"Erreur lors du calcul de similarité pour {comp_id}: {e}")
            
            # Trier par similarité décroissante
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            
            # Utiliser le reranking si disponible
            use_albert_reranking = getattr(settings, 'USE_ALBERT_RERANKING', False)
            
            if use_albert_reranking and len(similarities) > 1:
                try:
                    # Appliquer le reranking via Albert API
                    reranked_results = self.rerank_results(query, similarities[:min(limit*2, len(similarities))])
                    
                    # Si le reranking a réussi, utiliser ces résultats
                    if reranked_results:
                        return reranked_results[:limit]
                except Exception as e:
                    logger.warning(f"Échec du reranking: {e}, utilisation du tri par similarité")
            
            # Limiter le nombre de résultats
            return similarities[:limit]
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de compositions: {e}")
            return []
    
    def rerank_results(self, query: str, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Utilise Albert API pour reclasser les résultats de recherche.
        
        Args:
            query: La requête originale
            search_results: Les résultats de recherche initiaux
            
        Returns:
            Les résultats reclassés
        """
        try:
            from ..integration.albert_client import AlbertAPIClient
            
            # Préparer les documents pour le reranking
            documents = []
            
            for result in search_results:
                # Construire un texte représentatif pour chaque composition
                text = (
                    f"Composition: {result['name']}\n"
                    f"Description: {result['description']}\n"
                    f"Tags: {', '.join(result['tags'])}"
                )
                documents.append(text)
            
            if not documents:
                return search_results
            
            # Initialiser le client Albert API
            client = AlbertAPIClient()
            
            # Exécuter le reranking
            reranked_docs = client.rerank_documents(query, documents)
            
            # Réorganiser les résultats originaux selon le nouvel ordre
            reranked_results = []
            
            for item in reranked_docs:
                index = item["index"]
                if 0 <= index < len(search_results):
                    # Ajouter le nouveau score de pertinence
                    result = search_results[index].copy()
                    result["rerank_score"] = item["score"]
                    reranked_results.append(result)
            
            # Ajouter les résultats qui n'auraient pas été inclus dans le reranking
            remaining_indices = set(range(len(search_results))) - set(item["index"] for item in reranked_docs)
            for idx in sorted(remaining_indices):
                reranked_results.append(search_results[idx])
            
            return reranked_results
            
        except ImportError:
            logger.warning("Module Albert API non disponible pour le reranking")
            return search_results
        except Exception as e:
            logger.warning(f"Erreur lors du reranking: {e}")
            return search_results
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calcule la similarité cosinus entre deux vecteurs.
        
        Args:
            vec1: Premier vecteur
            vec2: Second vecteur
        
        Returns:
            Score de similarité cosinus (0-1)
        """
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        # Similarité cosinus: dot(v1, v2) / (norm(v1) * norm(v2))
        dot_product = np.dot(vec1, vec2)
        norm_v1 = np.linalg.norm(vec1)
        norm_v2 = np.linalg.norm(vec2)
        
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
        
        return dot_product / (norm_v1 * norm_v2)
    
    def reindex_all_compositions(self) -> Tuple[int, int]:
        """
        Réindexe toutes les compositions depuis le stockage.
        
        Returns:
            Tuple (nombre de succès, nombre d'échecs)
        """
        # Charger toutes les compositions
        compositions = self.composition_storage.list_compositions()
        
        # Vider l'index actuel
        self._clear_index()
        
        # Réindexer
        return self.batch_index_compositions(compositions)
    
    def _clear_index(self):
        """Vide tous les index dans Redis."""
        try:
            # Récupérer toutes les clés liées aux compositions
            composition_keys = self.redis_client.keys("composition:*")
            embedding_keys = self.redis_client.keys("embedding:*")
            status_keys = self.redis_client.keys("compositions:*")
            tag_keys = self.redis_client.keys("tag:*")
            
            # Supprimer toutes les clés
            all_keys = composition_keys + embedding_keys + status_keys + tag_keys
            if all_keys:
                self.redis_client.delete(*all_keys)
            
            logger.info(f"Index vectoriel vidé: {len(all_keys)} clés supprimées")
        except Exception as e:
            logger.error(f"Erreur lors du vidage de l'index: {e}")
            raise 