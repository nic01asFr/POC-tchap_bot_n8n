from typing import Dict, List, Optional, Any, Tuple
import re
from sentence_transformers import SentenceTransformer
import numpy as np

from ..models.composition import Composition, CompositionTrigger
from ..registry.vector_index import VectorIndex
from ..config import settings
from loguru import logger


class IntentAnalyzer:
    """
    Analyseur d'intention qui identifie les compositions pertinentes
    en fonction des requêtes utilisateur.
    """
    
    def __init__(self, vector_index: Optional[VectorIndex] = None):
        """
        Initialise l'analyseur d'intention.
        
        Args:
            vector_index: Index vectoriel à utiliser (en crée un nouveau si None)
        """
        self.vector_index = vector_index or VectorIndex()
        
        # Charger le modèle d'embeddings
        try:
            self.embeddings_model_name = settings.EMBEDDINGS_MODEL
            self.embeddings_model = SentenceTransformer(self.embeddings_model_name)
            logger.info(f"Modèle d'embeddings '{self.embeddings_model_name}' chargé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle d'embeddings: {e}")
            raise
        
        self.similarity_threshold = settings.SIMILARITY_THRESHOLD
    
    def analyze_intent(self, query: str) -> List[Dict[str, Any]]:
        """
        Analyse l'intention de l'utilisateur et trouve les compositions pertinentes.
        
        Args:
            query: La requête de l'utilisateur
        
        Returns:
            Liste des compositions pertinentes avec score de similarité
        """
        # Utiliser la recherche vectorielle
        matches = self.vector_index.search_compositions(query)
        
        logger.info(f"Analyse d'intention pour '{query}': {len(matches)} compositions trouvées")
        return matches
    
    def match_intent_patterns(self, query: str, composition: Composition) -> Optional[float]:
        """
        Vérifie si une requête correspond aux patterns d'intention d'une composition.
        
        Args:
            query: La requête de l'utilisateur
            composition: La composition à vérifier
        
        Returns:
            Score de confiance si correspondance, None sinon
        """
        # Vérifier les déclencheurs d'intention
        intent_triggers = [
            trigger for trigger in composition.triggers 
            if trigger.type == "intent"
        ]
        
        if not intent_triggers:
            return None
        
        max_confidence = 0.0
        
        for trigger in intent_triggers:
            config = trigger.configuration
            patterns = config.get("intent_patterns", [])
            
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    confidence = config.get("confidence_threshold", 0.7)
                    max_confidence = max(max_confidence, confidence)
            
            # Vérifier également avec la similarité sémantique
            if "semantic_examples" in config:
                examples = config["semantic_examples"]
                
                # Générer les embeddings
                query_emb = self.embeddings_model.encode(query)
                examples_emb = self.embeddings_model.encode(examples)
                
                # Calculer les similarités
                similarities = [
                    self._cosine_similarity(query_emb, example_emb) 
                    for example_emb in examples_emb
                ]
                
                if similarities:
                    max_semantic_sim = max(similarities)
                    if max_semantic_sim >= config.get("semantic_threshold", self.similarity_threshold):
                        max_confidence = max(max_confidence, max_semantic_sim)
        
        return max_confidence if max_confidence > 0 else None
    
    def find_best_composition(self, query: str) -> Tuple[Optional[str], float]:
        """
        Trouve la meilleure composition pour une requête.
        
        Args:
            query: La requête de l'utilisateur
        
        Returns:
            Tuple (ID de la composition, score de confiance) ou (None, 0) si aucune trouvée
        """
        matches = self.analyze_intent(query)
        
        if not matches:
            return None, 0.0
        
        # Retourner la meilleure correspondance
        best_match = matches[0]
        return best_match["id"], best_match["similarity_score"]
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calcule la similarité cosinus entre deux vecteurs.
        
        Args:
            vec1: Premier vecteur
            vec2: Second vecteur
        
        Returns:
            Score de similarité cosinus (0-1)
        """
        # Similarité cosinus: dot(v1, v2) / (norm(v1) * norm(v2))
        dot_product = np.dot(vec1, vec2)
        norm_v1 = np.linalg.norm(vec1)
        norm_v2 = np.linalg.norm(vec2)
        
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
        
        return dot_product / (norm_v1 * norm_v2) 