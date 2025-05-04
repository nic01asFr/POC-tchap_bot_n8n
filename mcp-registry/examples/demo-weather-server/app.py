"""
Serveur MCP de démonstration pour la météo
"""

import os
import json
import time
import logging
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp-demo-weather")

# Configuration du serveur
SERVER_ID = os.getenv("MCP_SERVER_ID", "demo_weather")
SERVER_NAME = os.getenv("MCP_SERVER_NAME", "Service Météo (Demo)")
SERVER_DESCRIPTION = os.getenv("MCP_SERVER_DESCRIPTION", "Service de démonstration pour obtenir la météo")
REGISTRY_URL = os.getenv("MCP_REGISTRY_URL", "")

# Créer l'application FastAPI
app = FastAPI(
    title=SERVER_NAME,
    description=SERVER_DESCRIPTION,
    version="1.0.0",
)

# Ajouter le middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles de données
class ToolRunRequest(BaseModel):
    name: str
    parameters: Dict[str, Any]
    
class WeatherRequest(BaseModel):
    ville: str
    
class ForecastRequest(BaseModel):
    ville: str
    jours: Optional[int] = 3

# Données de météo fictives
WEATHER_DATA = {
    "paris": {"temperature": 22, "conditions": "ensoleillé", "humidité": 65},
    "lyon": {"temperature": 24, "conditions": "partiellement nuageux", "humidité": 60},
    "marseille": {"temperature": 28, "conditions": "ensoleillé", "humidité": 50},
    "bordeaux": {"temperature": 23, "conditions": "nuageux", "humidité": 70},
    "lille": {"temperature": 18, "conditions": "pluvieux", "humidité": 80},
    "strasbourg": {"temperature": 20, "conditions": "partiellement nuageux", "humidité": 65},
    "nice": {"temperature": 26, "conditions": "ensoleillé", "humidité": 55},
    "nantes": {"temperature": 21, "conditions": "nuageux", "humidité": 75},
    "toulouse": {"temperature": 25, "conditions": "ensoleillé", "humidité": 60},
    "montpellier": {"temperature": 27, "conditions": "ensoleillé", "humidité": 55},
}

# Schéma MCP
MCP_SCHEMA = {
    "tools": [
        {
            "name": "get_weather",
            "description": "Obtenir la météo actuelle pour une ville",
            "parameters": {
                "type": "object",
                "properties": {
                    "ville": {
                        "type": "string",
                        "description": "Nom de la ville (ex: Paris, Lyon, Marseille)"
                    }
                },
                "required": ["ville"]
            }
        },
        {
            "name": "get_forecast",
            "description": "Obtenir les prévisions météo pour une ville",
            "parameters": {
                "type": "object",
                "properties": {
                    "ville": {
                        "type": "string",
                        "description": "Nom de la ville (ex: Paris, Lyon, Marseille)"
                    },
                    "jours": {
                        "type": "integer",
                        "description": "Nombre de jours de prévision (max: 5)",
                        "default": 3
                    }
                },
                "required": ["ville"]
            }
        }
    ]
}

@app.get("/")
async def root():
    """Page d'accueil du serveur MCP."""
    return {
        "name": SERVER_NAME,
        "id": SERVER_ID,
        "description": SERVER_DESCRIPTION,
        "status": "active"
    }

@app.get("/schema")
async def get_schema():
    """
    Retourne le schéma MCP avec la liste des outils disponibles.
    Conforme au protocole Model Context Protocol.
    """
    return MCP_SCHEMA

@app.post("/run")
async def run_tool(request: ToolRunRequest):
    """
    Exécute un outil MCP.
    Conforme au protocole Model Context Protocol.
    """
    tool_name = request.name
    params = request.parameters
    
    logger.info(f"Exécution de l'outil: {tool_name} avec paramètres: {params}")
    
    if tool_name == "get_weather":
        return get_weather_data(params.get("ville", ""))
    elif tool_name == "get_forecast":
        return get_forecast_data(params.get("ville", ""), params.get("jours", 3))
    else:
        raise HTTPException(status_code=404, detail=f"Outil '{tool_name}' non trouvé")

def get_weather_data(ville: str):
    """Récupère les données météo pour une ville."""
    if not ville:
        return {"error": "Veuillez spécifier une ville"}
        
    ville_norm = ville.lower().strip()
    
    if ville_norm not in WEATHER_DATA:
        villes_similaires = [v for v in WEATHER_DATA.keys() if ville_norm in v]
        if villes_similaires:
            return {"error": f"Ville '{ville}' non trouvée", "suggestions": villes_similaires}
        return {"error": f"Ville '{ville}' non trouvée"}
    
    data = WEATHER_DATA[ville_norm].copy()
    data["ville"] = ville.capitalize()
    data["timestamp"] = time.time()
    return data

def get_forecast_data(ville: str, jours: int = 3):
    """Génère des prévisions météo fictives pour une ville."""
    if not ville:
        return {"error": "Veuillez spécifier une ville"}
        
    ville_norm = ville.lower().strip()
    
    if ville_norm not in WEATHER_DATA:
        villes_similaires = [v for v in WEATHER_DATA.keys() if ville_norm in v]
        if villes_similaires:
            return {"error": f"Ville '{ville}' non trouvée", "suggestions": villes_similaires}
        return {"error": f"Ville '{ville}' non trouvée"}
    
    # Limiter le nombre de jours à 5
    jours = min(jours, 5)
    
    # Données actuelles comme point de départ
    base_data = WEATHER_DATA[ville_norm]
    
    # Générer des prévisions aléatoires basées sur les données actuelles
    import random
    forecast = []
    
    for i in range(jours):
        # Générer des variations aléatoires
        temp_var = random.randint(-3, 3)
        hum_var = random.randint(-10, 10)
        
        # Liste des conditions possibles
        conditions = ["ensoleillé", "partiellement nuageux", "nuageux", "pluvieux"]
        
        # Générer la prévision pour ce jour
        day_forecast = {
            "jour": i + 1,
            "date": time.strftime("%Y-%m-%d", time.localtime(time.time() + i * 86400)),
            "temperature": base_data["temperature"] + temp_var,
            "conditions": random.choice(conditions),
            "humidité": max(min(base_data["humidité"] + hum_var, 100), 0)  # Entre 0 et 100
        }
        
        forecast.append(day_forecast)
    
    return {
        "ville": ville.capitalize(),
        "prévisions": forecast,
        "timestamp": time.time()
    }

@app.on_event("startup")
async def startup_event():
    """Événement de démarrage - enregistrement auprès du MCP Registry."""
    if REGISTRY_URL:
        try:
            logger.info(f"Enregistrement auprès du MCP Registry: {REGISTRY_URL}")
            
            registration_data = {
                "id": SERVER_ID,
                "name": SERVER_NAME,
                "description": SERVER_DESCRIPTION,
                "url": f"http://localhost:8001",  # À adapter selon votre configuration
                "capabilities": ["weather", "forecast"]
            }
            
            response = requests.post(
                f"{REGISTRY_URL}/register",
                json=registration_data,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info("Enregistrement réussi auprès du MCP Registry")
            else:
                logger.warning(f"Échec de l'enregistrement: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement auprès du MCP Registry: {e}")

@app.get("/ping")
async def ping():
    """Endpoint de healthcheck."""
    return {"status": "ok", "timestamp": time.time()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True) 