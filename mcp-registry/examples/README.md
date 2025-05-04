# Exemples de serveurs MCP

Ce répertoire contient des exemples de serveurs MCP pour tester l'intégration avec le MCP Registry.

## Serveur météo de démonstration

Un serveur MCP simple qui fournit des données météorologiques fictives.

### Outils disponibles

- `get_weather` : Obtenir la météo actuelle pour une ville
- `get_forecast` : Obtenir les prévisions météo pour une ville

### Déploiement

#### Avec Docker Compose

Le moyen le plus simple de déployer le MCP Registry et le serveur de démonstration est d'utiliser Docker Compose :

```bash
cd examples
docker-compose up -d
```

Cela va déployer à la fois le MCP Registry sur le port 8000 et le serveur météo sur le port 8001.

#### Sans Docker

Pour démarrer le serveur météo de démonstration sans Docker :

1. Créez un environnement virtuel (optionnel mais recommandé)
```bash
cd examples/demo-weather-server
python -m venv venv
source venv/bin/activate  # Sur Windows : venv\Scripts\activate
```

2. Installez les dépendances
```bash
pip install -r requirements.txt
```

3. Démarrez le serveur
```bash
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

### Test du serveur

Une fois le serveur démarré, vous pouvez accéder à :

- Page d'accueil : http://localhost:8001/
- Schéma MCP : http://localhost:8001/schema
- Documentation API : http://localhost:8001/docs

### Test avec le MCP Registry

Pour tester la communication avec le MCP Registry, assurez-vous que:

1. Le MCP Registry est en cours d'exécution sur le port 8000
2. La variable d'environnement `MCP_REGISTRY_URL` est définie avec l'URL du MCP Registry (par exemple `http://localhost:8000`)

Le serveur météo de démonstration s'enregistrera automatiquement auprès du MCP Registry au démarrage.

### Utilisation via Albert

Une fois le serveur enregistré, vous pouvez utiliser les outils météo via les commandes Albert:

```
# Obtenir la météo pour Paris
!mcp-run demo_weather get_weather ville="Paris"

# Obtenir les prévisions météo pour Lyon sur 5 jours
!mcp-run demo_weather get_forecast ville="Lyon" jours=5
```

## Développer votre propre serveur MCP

Pour développer votre propre serveur MCP compatible avec le MCP Registry, consultez le serveur météo de démonstration comme exemple. Les éléments clés à implémenter sont:

1. Un endpoint `/schema` qui renvoie la structure des outils disponibles
2. Un endpoint `/run` qui exécute les outils
3. Une logique d'enregistrement auprès du MCP Registry au démarrage 