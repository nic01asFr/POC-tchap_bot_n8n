"""
Gestionnaire de commandes n8n pour Albert-Tchap.

Ce module permet de traiter les commandes liées à n8n envoyées au bot.
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Union

from .client import N8nClient
from .models import N8nExecutionResult

logger = logging.getLogger(__name__)


class N8nCommandHandler:
    """Gestionnaire de commandes n8n pour Albert-Tchap."""

    def __init__(self, n8n_client: N8nClient):
        """
        Initialise le gestionnaire de commandes.
        
        Args:
            n8n_client: Client n8n à utiliser
        """
        self.n8n_client = n8n_client
        
    async def handle_tools_command(self, args: str = "") -> str:
        """
        Gère la commande !tools.
        
        Args:
            args: Arguments de la commande
            
        Returns:
            Message de réponse formaté
        """
        try:
            logger.info(f"Traitement de la commande !tools avec args: '{args}'")
            
            if not args:
                # Liste toutes les catégories disponibles
                logger.info("Récupération des catégories d'outils disponibles")
                categories = await self.n8n_client.get_tool_categories()
                tools_by_category = await self.n8n_client.get_tools_by_category()
                
                if not categories:
                    logger.warning("Aucune catégorie d'outils trouvée dans la réponse")
                    return "⚠️ Aucun outil n'est disponible pour le moment."
                
                logger.info(f"Catégories trouvées: {', '.join(categories)}")
                response = "📋 **Catégories d'outils disponibles:**\n\n"
                for category in sorted(categories):
                    cat_tools = tools_by_category.get(category, [])
                    response += f"**{category.upper()}** ({len(cat_tools)} outils)\n"
                    
                response += "\nUtilisez `!tools <catégorie>` pour voir les outils d'une catégorie"
                response += "\nUtilisez `!tools search <terme>` pour rechercher des outils"
                
                return response
                
            if args.startswith("search "):
                # Recherche par terme
                query = args[7:].strip()
                logger.info(f"Recherche d'outils avec le terme: '{query}'")
                tools = await self.n8n_client.search_tools(query)
                
                if not tools:
                    logger.info(f"Aucun outil trouvé pour le terme: '{query}'")
                    return f"⚠️ Aucun outil trouvé pour '{query}'"
                    
                logger.info(f"Outils trouvés: {len(tools)}")
                response = f"🔍 **Résultats pour '{query}':**\n\n"
                for tool in tools:
                    response += f"**{tool.get('name')}** - {tool.get('description')}\n"
                    
                response += "\nUtilisez `!run <nom_outil> [paramètres]` pour exécuter un outil"
                
                return response
                
            else:
                # Liste les outils d'une catégorie spécifique
                category = args.strip()
                logger.info(f"Récupération des outils dans la catégorie: '{category}'")
                tools = await self.n8n_client.get_tools_in_category(category)
                
                if not tools:
                    logger.info(f"Aucun outil trouvé dans la catégorie: '{category}'")
                    return f"⚠️ Aucun outil trouvé dans la catégorie '{category}'"
                    
                logger.info(f"Outils trouvés dans la catégorie {category}: {len(tools)}")
                response = f"🧰 **Outils dans {category.upper()}:**\n\n"
                for tool in tools:
                    response += f"**{tool.get('name')}** - {tool.get('description')}\n"
                    
                response += "\nUtilisez `!run <nom_outil> [paramètres]` pour exécuter un outil"
                
                return response
                
        except Exception as e:
            logger.exception(f"Erreur lors du traitement de la commande !tools: {str(e)}")
            return f"⚠️ Erreur lors de la récupération des outils: {str(e)}"
    
    async def handle_run_command(self, args: str) -> str:
        """
        Gère la commande !run.
        
        Args:
            args: Arguments de la commande
            
        Returns:
            Message de réponse formaté
        """
        if not args:
            return "⚠️ Usage: `!run <nom_outil> [paramètres]`"
            
        # Extraction du nom de l'outil et des paramètres
        match = re.match(r'(\w+)\s*(.*)', args)
        if not match:
            return "⚠️ Format de commande incorrect"
            
        tool_name, params_str = match.groups()
        
        # Parsing des paramètres
        parameters = {}
        if params_str:
            # Format: param1=valeur1 param2="valeur avec espaces"
            param_matches = re.finditer(r'(\w+)=(?:"([^"]+)"|([^\s]+))', params_str)
            for param_match in param_matches:
                param_name = param_match.group(1)
                param_value = param_match.group(2) if param_match.group(2) else param_match.group(3)
                parameters[param_name] = param_value
        
        # Exécution de l'outil
        result = await self.n8n_client.execute_tool(tool_name, parameters)
        
        if not result.success:
            return f"❌ Erreur: {result.message}"
        
        # Formatage de la réponse
        if result.data:
            if "message" in result.data:
                return f"✅ {result.data['message']}"
            return f"✅ Résultat:\n```json\n{json.dumps(result.data, indent=2, ensure_ascii=False)}\n```"
        else:
            return f"✅ {result.message}"
    
    async def get_tools_help(self) -> str:
        """
        Génère l'aide pour les commandes liées aux outils.
        
        Returns:
            Message d'aide formaté
        """
        help_text = """
**📚 Guide d'utilisation des outils n8n**

Pour interagir avec les outils disponibles, vous pouvez utiliser les commandes suivantes:

**Découverte des outils:**
`!tools` - Liste toutes les catégories d'outils disponibles
`!tools <catégorie>` - Liste tous les outils dans une catégorie spécifique
`!tools search <terme>` - Recherche des outils par mot-clé

**Exécution des outils:**
`!run <nom_outil> [paramètres]` - Exécute un outil spécifique

**Format des paramètres:**
Les paramètres doivent être spécifiés au format `nom=valeur`
Pour les valeurs contenant des espaces, utilisez des guillemets: `nom="valeur avec espaces"`

**Exemple:**
`!run send_email destinataire="jean@example.fr" sujet="Réunion importante" contenu="Bonjour Jean, n'oublie pas la réunion de demain."`
"""
        return help_text
        
    async def detect_tool_request(self, message: str) -> Optional[Dict]:
        """
        Détecte si un message contient une intention d'utilisation d'outil.
        
        Args:
            message: Message à analyser
            
        Returns:
            Informations sur l'outil détecté, ou None
        """
        # Cette méthode pourrait être enrichie avec une analyse plus sophistiquée
        # Pour l'instant, détection simple basée sur des mots-clés
        tool_keywords = {
            "email": ["envoyer email", "envoyer un mail", "envoyer un message"],
            "database": ["requête", "database", "base de données"],
            # Ajoutez d'autres catégories et mots-clés selon vos outils
        }
        
        message_lower = message.lower()
        
        for category, keywords in tool_keywords.items():
            for keyword in keywords:
                if keyword in message_lower:
                    tools = await self.n8n_client.get_tools_in_category(category)
                    if tools:
                        return {
                            "detected": True,
                            "category": category,
                            "tools": tools,
                            "keyword": keyword
                        }
        
        return None 