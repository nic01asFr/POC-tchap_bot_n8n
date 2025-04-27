FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir .
# Installation des dépendances supplémentaires pour le webhook
RUN pip install --no-cache-dir aiohttp python-dotenv

# Création des répertoires pour les données persistantes
RUN mkdir -p /app/data/store

# Exposer le port webhook
EXPOSE 8080

# Utiliser le fichier de configuration Docker et notre serveur optimisé
CMD ["sh", "-c", "cp -n /app/.env.docker /app/app/.env && python -m app.webhook_optimized"]