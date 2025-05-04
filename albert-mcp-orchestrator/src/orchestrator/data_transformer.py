from typing import Dict, List, Any, Optional, Union, Callable
import json
import re
from datetime import datetime
from loguru import logger


class DataTransformer:
    """
    Transformateur de données pour manipuler les entrées/sorties lors de l'exécution des compositions.
    """
    
    def __init__(self):
        """Initialise le transformateur de données."""
        # Registre des fonctions de transformation
        self.transformations: Dict[str, Callable] = {
            "extract": self._transform_extract,
            "format": self._transform_format,
            "convert": self._transform_convert,
            "default": self._transform_default,
            "map": self._transform_map,
            "filter": self._transform_filter,
            "join": self._transform_join,
            "split": self._transform_split,
            "replace": self._transform_replace,
            "substring": self._transform_substring,
            "length": self._transform_length,
            "uppercase": self._transform_uppercase,
            "lowercase": self._transform_lowercase,
            "json_path": self._transform_json_path,
            "array_item": self._transform_array_item,
            "concat": self._transform_concat,
            "merge": self._transform_merge,
            "math": self._transform_math,
            "condition": self._transform_condition,
            "timestamp": self._transform_timestamp,
            "regex": self._transform_regex,
        }
    
    def apply_transformation(self, value: Any, transformation: Dict[str, Any]) -> Any:
        """
        Applique une transformation à une valeur.
        
        Args:
            value: La valeur à transformer
            transformation: Configuration de la transformation
        
        Returns:
            La valeur transformée
        """
        if not transformation:
            return value
        
        transform_type = transformation.get("type")
        if not transform_type or transform_type not in self.transformations:
            logger.warning(f"Type de transformation inconnu: {transform_type}")
            return value
        
        try:
            return self.transformations[transform_type](value, transformation)
        except Exception as e:
            logger.error(f"Erreur lors de la transformation '{transform_type}': {e}")
            
            # Utiliser la valeur par défaut si définie, sinon retourner la valeur originale
            if "default" in transformation:
                return transformation["default"]
            return value
    
    def transform_output(self, data: Dict[str, Any], output_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transforme les résultats d'exécution selon le schéma de sortie.
        
        Args:
            data: Données brutes de l'exécution
            output_schema: Schéma de sortie
        
        Returns:
            Données transformées conformes au schéma
        """
        if not output_schema:
            return data
        
        try:
            result = {}
            properties = output_schema.get("properties", {})
            
            # Pour chaque propriété définie dans le schéma de sortie
            for prop_name, prop_schema in properties.items():
                # Vérifier si un mappage est défini
                if "source" in prop_schema:
                    source = prop_schema["source"]
                    
                    # Récupérer la valeur source
                    if "." in source:  # Format: step_id.field
                        step_id, field = source.split(".", 1)
                        step_data = data.get(step_id, {})
                        value = step_data.get(field) if isinstance(step_data, dict) else None
                    else:  # Format: step_id (tout le résultat)
                        value = data.get(source)
                    
                    # Appliquer la transformation si définie
                    if "transformation" in prop_schema:
                        value = self.apply_transformation(value, prop_schema["transformation"])
                    
                    # Assigner la valeur
                    result[prop_name] = value
                
                # Valeur constante
                elif "value" in prop_schema:
                    result[prop_name] = prop_schema["value"]
                
                # Valeur par défaut
                elif "default" in prop_schema:
                    result[prop_name] = prop_schema["default"]
            
            return result
        except Exception as e:
            logger.error(f"Erreur lors de la transformation de sortie: {e}")
            return data
    
    def _transform_extract(self, value: Any, config: Dict[str, Any]) -> Any:
        """
        Extrait une propriété d'un objet ou d'un dictionnaire.
        
        Args:
            value: La valeur à transformer
            config: Configuration de la transformation
        
        Returns:
            La propriété extraite
        """
        if not isinstance(value, dict):
            return None
        
        path = config.get("path", "")
        if not path:
            return value
        
        # Naviguer dans l'objet
        parts = path.split(".")
        current = value
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                if "default" in config:
                    return config["default"]
                return None
        
        return current
    
    def _transform_format(self, value: Any, config: Dict[str, Any]) -> str:
        """
        Formate une valeur en utilisant une chaîne de format.
        
        Args:
            value: La valeur à transformer
            config: Configuration de la transformation
        
        Returns:
            La chaîne formatée
        """
        format_str = config.get("template", "{}")
        
        # Pour les dictionnaires, utiliser comme variables de format
        if isinstance(value, dict):
            try:
                return format_str.format(**value)
            except (KeyError, ValueError) as e:
                logger.error(f"Erreur lors du formatage avec dictionnaire: {e}")
                return format_str
        else:
            # Sinon, utiliser comme valeur unique
            try:
                return format_str.format(value)
            except (ValueError, TypeError) as e:
                logger.error(f"Erreur lors du formatage simple: {e}")
                return format_str
    
    def _transform_convert(self, value: Any, config: Dict[str, Any]) -> Any:
        """
        Convertit une valeur en un type spécifié.
        
        Args:
            value: La valeur à transformer
            config: Configuration de la transformation
        
        Returns:
            La valeur convertie
        """
        target_type = config.get("to", "string")
        
        try:
            if target_type == "string":
                return str(value)
            elif target_type == "integer":
                return int(value)
            elif target_type == "float":
                return float(value)
            elif target_type == "boolean":
                if isinstance(value, str):
                    return value.lower() in ("true", "yes", "1", "y")
                return bool(value)
            elif target_type == "array":
                if isinstance(value, (list, tuple)):
                    return list(value)
                elif isinstance(value, str):
                    separator = config.get("separator", ",")
                    return value.split(separator)
                else:
                    return [value]
            elif target_type == "object":
                if isinstance(value, str):
                    return json.loads(value)
                return dict(value)
            else:
                logger.warning(f"Type cible inconnu pour la conversion: {target_type}")
                return value
        except Exception as e:
            logger.error(f"Erreur lors de la conversion en {target_type}: {e}")
            if "default" in config:
                return config["default"]
            return value
    
    def _transform_default(self, value: Any, config: Dict[str, Any]) -> Any:
        """
        Retourne une valeur par défaut si la valeur d'entrée est None ou vide.
        
        Args:
            value: La valeur à transformer
            config: Configuration de la transformation
        
        Returns:
            La valeur originale ou la valeur par défaut
        """
        if value is None or value == "" or value == [] or value == {}:
            return config.get("value")
        return value
    
    def _transform_map(self, value: Any, config: Dict[str, Any]) -> List[Any]:
        """
        Applique une transformation à chaque élément d'une liste.
        
        Args:
            value: La liste à transformer
            config: Configuration de la transformation
        
        Returns:
            La liste transformée
        """
        if not isinstance(value, (list, tuple)):
            if "default" in config:
                return config["default"]
            return []
        
        transformation = config.get("item_transformation", {})
        if not transformation:
            return value
        
        result = []
        for item in value:
            transformed_item = self.apply_transformation(item, transformation)
            result.append(transformed_item)
        
        return result
    
    def _transform_filter(self, value: Any, config: Dict[str, Any]) -> List[Any]:
        """
        Filtre les éléments d'une liste selon une condition.
        
        Args:
            value: La liste à filtrer
            config: Configuration de la transformation
        
        Returns:
            La liste filtrée
        """
        if not isinstance(value, (list, tuple)):
            if "default" in config:
                return config["default"]
            return []
        
        condition = config.get("condition", {})
        if not condition:
            return value
        
        condition_type = condition.get("type", "simple")
        field = condition.get("field")
        operator = condition.get("operator", "eq")
        expected = condition.get("value")
        
        result = []
        
        for item in value:
            # Extraire la valeur à comparer
            if field:
                if isinstance(item, dict) and field in item:
                    actual = item[field]
                else:
                    continue
            else:
                actual = item
            
            # Évaluer la condition
            if operator == "eq" and actual == expected:
                result.append(item)
            elif operator == "neq" and actual != expected:
                result.append(item)
            elif operator == "gt" and actual > expected:
                result.append(item)
            elif operator == "gte" and actual >= expected:
                result.append(item)
            elif operator == "lt" and actual < expected:
                result.append(item)
            elif operator == "lte" and actual <= expected:
                result.append(item)
            elif operator == "in" and actual in expected:
                result.append(item)
            elif operator == "contains" and expected in actual:
                result.append(item)
            elif operator == "exists" and actual is not None:
                result.append(item)
        
        return result
    
    def _transform_join(self, value: Any, config: Dict[str, Any]) -> str:
        """
        Joint les éléments d'une liste en une chaîne.
        
        Args:
            value: La liste à joindre
            config: Configuration de la transformation
        
        Returns:
            La chaîne jointe
        """
        if not isinstance(value, (list, tuple)):
            if "default" in config:
                return config["default"]
            return str(value)
        
        separator = config.get("separator", "")
        
        # Convertir chaque élément en chaîne
        str_items = [str(item) for item in value]
        return separator.join(str_items)
    
    def _transform_split(self, value: Any, config: Dict[str, Any]) -> List[str]:
        """
        Divise une chaîne en liste.
        
        Args:
            value: La chaîne à diviser
            config: Configuration de la transformation
        
        Returns:
            La liste résultante
        """
        if not isinstance(value, str):
            if "default" in config:
                return config["default"]
            return [str(value)] if value is not None else []
        
        separator = config.get("separator", ",")
        max_splits = config.get("max_splits", -1)
        
        return value.split(separator, max_splits)
    
    def _transform_replace(self, value: Any, config: Dict[str, Any]) -> str:
        """
        Remplace des sous-chaînes dans une chaîne.
        
        Args:
            value: La chaîne à modifier
            config: Configuration de la transformation
        
        Returns:
            La chaîne modifiée
        """
        if not isinstance(value, str):
            if "default" in config:
                return config["default"]
            return str(value) if value is not None else ""
        
        pattern = config.get("pattern", "")
        replacement = config.get("replacement", "")
        count = config.get("count", -1)
        
        if not pattern:
            return value
        
        # Utiliser une expression régulière si spécifié
        if config.get("use_regex", False):
            return re.sub(pattern, replacement, value, count=count)
        else:
            return value.replace(pattern, replacement, count)
    
    def _transform_substring(self, value: Any, config: Dict[str, Any]) -> str:
        """
        Extrait une sous-chaîne.
        
        Args:
            value: La chaîne source
            config: Configuration de la transformation
        
        Returns:
            La sous-chaîne extraite
        """
        if not isinstance(value, str):
            if "default" in config:
                return config["default"]
            return str(value) if value is not None else ""
        
        start = config.get("start", 0)
        end = config.get("end", None)
        
        if end is not None:
            return value[start:end]
        else:
            return value[start:]
    
    def _transform_length(self, value: Any, config: Dict[str, Any]) -> int:
        """
        Retourne la longueur d'une chaîne, liste ou dictionnaire.
        
        Args:
            value: La valeur dont calculer la longueur
            config: Configuration de la transformation
        
        Returns:
            La longueur
        """
        if value is None:
            return 0
        
        try:
            return len(value)
        except (TypeError, AttributeError):
            if "default" in config:
                return config["default"]
            return 0
    
    def _transform_uppercase(self, value: Any, config: Dict[str, Any]) -> str:
        """
        Convertit une chaîne en majuscules.
        
        Args:
            value: La chaîne à convertir
            config: Configuration de la transformation
        
        Returns:
            La chaîne convertie
        """
        if not isinstance(value, str):
            if "default" in config:
                return config["default"]
            return str(value).upper() if value is not None else ""
        
        return value.upper()
    
    def _transform_lowercase(self, value: Any, config: Dict[str, Any]) -> str:
        """
        Convertit une chaîne en minuscules.
        
        Args:
            value: La chaîne à convertir
            config: Configuration de la transformation
        
        Returns:
            La chaîne convertie
        """
        if not isinstance(value, str):
            if "default" in config:
                return config["default"]
            return str(value).lower() if value is not None else ""
        
        return value.lower()
    
    def _transform_json_path(self, value: Any, config: Dict[str, Any]) -> Any:
        """
        Extrait une valeur d'un objet JSON en utilisant un chemin.
        
        Args:
            value: L'objet JSON
            config: Configuration de la transformation
        
        Returns:
            La valeur extraite
        """
        if not isinstance(value, (dict, list)):
            if "default" in config:
                return config["default"]
            return None
        
        path = config.get("path", "")
        if not path:
            return value
        
        # Implémentation simplifiée de JSONPath
        parts = path.replace("[", ".").replace("]", "").split(".")
        parts = [p for p in parts if p]
        
        current = value
        for part in parts:
            try:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                elif isinstance(current, (list, tuple)) and part.isdigit():
                    index = int(part)
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return config.get("default")
                else:
                    return config.get("default")
            except Exception:
                return config.get("default")
        
        return current
    
    def _transform_array_item(self, value: Any, config: Dict[str, Any]) -> Any:
        """
        Récupère un élément d'un tableau.
        
        Args:
            value: Le tableau
            config: Configuration de la transformation
        
        Returns:
            L'élément récupéré
        """
        if not isinstance(value, (list, tuple)):
            if "default" in config:
                return config["default"]
            return None
        
        index = config.get("index", 0)
        
        try:
            if index < len(value):
                return value[index]
            else:
                return config.get("default")
        except (TypeError, IndexError):
            return config.get("default")
    
    def _transform_concat(self, value: Any, config: Dict[str, Any]) -> str:
        """
        Concatène une valeur avec d'autres valeurs.
        
        Args:
            value: La valeur principale
            config: Configuration de la transformation
        
        Returns:
            La chaîne concaténée
        """
        values = config.get("values", [])
        
        # Convertir la valeur principale en chaîne
        result = str(value) if value is not None else ""
        
        # Ajouter les autres valeurs
        for val in values:
            result += str(val) if val is not None else ""
        
        return result
    
    def _transform_merge(self, value: Any, config: Dict[str, Any]) -> Union[Dict, List]:
        """
        Fusionne des dictionnaires ou des listes.
        
        Args:
            value: La valeur principale
            config: Configuration de la transformation
        
        Returns:
            Le résultat de la fusion
        """
        values = config.get("values", [])
        
        # Fusion de dictionnaires
        if isinstance(value, dict):
            result = value.copy()
            for val in values:
                if isinstance(val, dict):
                    result.update(val)
            return result
        
        # Fusion de listes
        elif isinstance(value, (list, tuple)):
            result = list(value)
            for val in values:
                if isinstance(val, (list, tuple)):
                    result.extend(val)
                else:
                    result.append(val)
            return result
        
        # Si la valeur n'est ni dict ni list, retourner une nouvelle liste
        else:
            result = [value] if value is not None else []
            for val in values:
                if isinstance(val, (list, tuple)):
                    result.extend(val)
                else:
                    result.append(val)
            return result
    
    def _transform_math(self, value: Any, config: Dict[str, Any]) -> Union[int, float]:
        """
        Effectue une opération mathématique.
        
        Args:
            value: La valeur principale
            config: Configuration de la transformation
        
        Returns:
            Le résultat de l'opération
        """
        # Convertir en nombre si nécessaire
        try:
            if isinstance(value, str) and value.strip():
                if "." in value:
                    num_value = float(value)
                else:
                    num_value = int(value)
            elif isinstance(value, (int, float)):
                num_value = value
            else:
                num_value = 0
        except (ValueError, TypeError):
            num_value = 0
        
        operation = config.get("operation", "add")
        operand = config.get("operand", 0)
        
        # Effectuer l'opération
        if operation == "add":
            return num_value + operand
        elif operation == "subtract":
            return num_value - operand
        elif operation == "multiply":
            return num_value * operand
        elif operation == "divide":
            if operand == 0:
                logger.warning("Division par zéro, valeur par défaut utilisée")
                return config.get("default", 0)
            return num_value / operand
        elif operation == "modulo":
            if operand == 0:
                logger.warning("Modulo par zéro, valeur par défaut utilisée")
                return config.get("default", 0)
            return num_value % operand
        elif operation == "power":
            return num_value ** operand
        else:
            logger.warning(f"Opération mathématique inconnue: {operation}")
            return num_value
    
    def _transform_condition(self, value: Any, config: Dict[str, Any]) -> Any:
        """
        Retourne une valeur en fonction d'une condition.
        
        Args:
            value: La valeur à évaluer
            config: Configuration de la transformation
        
        Returns:
            La valeur résultante
        """
        condition_operator = config.get("operator", "eq")
        condition_value = config.get("value")
        
        true_result = config.get("true_result")
        false_result = config.get("false_result")
        
        # Évaluer la condition
        condition_met = False
        
        if condition_operator == "eq":
            condition_met = value == condition_value
        elif condition_operator == "neq":
            condition_met = value != condition_value
        elif condition_operator == "gt":
            condition_met = value > condition_value
        elif condition_operator == "gte":
            condition_met = value >= condition_value
        elif condition_operator == "lt":
            condition_met = value < condition_value
        elif condition_operator == "lte":
            condition_met = value <= condition_value
        elif condition_operator == "in":
            condition_met = value in condition_value if isinstance(condition_value, (list, tuple, str)) else False
        elif condition_operator == "contains":
            condition_met = condition_value in value if isinstance(value, (list, tuple, str)) else False
        elif condition_operator == "exists":
            condition_met = value is not None
        elif condition_operator == "empty":
            condition_met = value is None or value == "" or value == [] or value == {}
        
        return true_result if condition_met else false_result
    
    def _transform_timestamp(self, value: Any, config: Dict[str, Any]) -> str:
        """
        Formate un timestamp ou une date.
        
        Args:
            value: La valeur de date/heure
            config: Configuration de la transformation
        
        Returns:
            La date formatée
        """
        format_str = config.get("format", "%Y-%m-%d %H:%M:%S")
        
        # Si value est une chaîne, essayer de la parser
        if isinstance(value, str):
            try:
                # Input format (si spécifié)
                input_format = config.get("input_format")
                if input_format:
                    dt = datetime.strptime(value, input_format)
                else:
                    # Essayer quelques formats courants
                    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                        try:
                            dt = datetime.strptime(value, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        # Aucun format n'a fonctionné
                        raise ValueError(f"Format de date non reconnu: {value}")
            except ValueError:
                logger.error(f"Erreur lors du parsing de la date: {value}")
                return config.get("default", value)
        elif isinstance(value, (int, float)):
            # Considérer comme timestamp UNIX
            dt = datetime.fromtimestamp(value)
        elif isinstance(value, datetime):
            dt = value
        else:
            # Utiliser la date actuelle si la valeur n'est pas exploitable
            dt = datetime.now()
        
        # Formater la date
        try:
            return dt.strftime(format_str)
        except Exception as e:
            logger.error(f"Erreur lors du formatage de la date: {e}")
            return config.get("default", str(value))
    
    def _transform_regex(self, value: Any, config: Dict[str, Any]) -> Any:
        """
        Applique une expression régulière et extrait des correspondances.
        
        Args:
            value: La chaîne à analyser
            config: Configuration de la transformation
        
        Returns:
            Les correspondances ou le groupe capturé
        """
        if not isinstance(value, str):
            if "default" in config:
                return config["default"]
            return None
        
        pattern = config.get("pattern", "")
        if not pattern:
            return value
        
        try:
            match_type = config.get("match_type", "first")
            group = config.get("group", 0)
            
            if match_type == "first":
                match = re.search(pattern, value)
                if match:
                    try:
                        return match.group(group)
                    except IndexError:
                        return config.get("default")
                else:
                    return config.get("default")
            
            elif match_type == "all":
                matches = re.findall(pattern, value)
                if matches:
                    return matches
                else:
                    return config.get("default", [])
            
            else:
                logger.warning(f"Type de correspondance inconnu: {match_type}")
                return config.get("default")
        
        except re.error as e:
            logger.error(f"Erreur d'expression régulière: {e}")
            return config.get("default") 