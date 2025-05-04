# Guide de dépannage

Ce document fournit des conseils pour diagnostiquer et résoudre les problèmes courants rencontrés avec le système d'orchestration adaptative MCP pour Albert Tchapbot.

## Diagnostic des problèmes

### 1. Vérification de l'état du système

Commencez par vérifier l'état général du système d'orchestration adaptative :

```bash
# Vérifier que les services sont en cours d'exécution
systemctl status albert-tchapbot
systemctl status mcp-registry
systemctl status mcp-memory-server

# Vérifier les journaux récents
journalctl -u albert-tchapbot -n 50 --no-pager
journalctl -u mcp-registry -n 50 --no-pager

# Vérifier l'utilisation des ressources
df -h /data/albert  # Espace disque
free -m             # Mémoire disponible
top -b -n 1         # CPU et processus
```

### 2. Vérification de la configuration

Assurez-vous que la configuration est correcte :

```bash
# Vérifier les fichiers de configuration
cat /etc/albert/config.yaml | grep -A20 "adaptive_orchestrator"
cat /etc/mcp-registry/config.yaml

# Vérifier que les chemins existent
ls -la /data/albert/compositions
ls -la /data/albert/knowledge_base
```

### 3. Vérification de la connectivité

Testez la connectivité entre les composants :

```bash
# Tester la connexion au registry MCP
curl -I http://localhost:5000/api/health

# Vérifier les ports ouverts
netstat -tuln | grep -E '5000|8000|8080'

# Tester la connectivité entre Albert et le registry
curl -X POST http://localhost:5000/api/tools/list \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <votre_clé_api>"
```

## Problèmes courants et solutions

### Problème 1 : Albert ne détecte pas l'orchestrateur adaptatif

**Symptômes :**
- Les messages qui devraient utiliser des outils MCP sont traités par le LLM standard
- Pas de mention de l'orchestrateur dans les journaux

**Causes possibles :**
1. Configuration désactivée
2. Bibliothèque non installée
3. Erreur lors de l'initialisation

**Solutions :**

```yaml
# Vérifier dans config.yaml que l'orchestrateur est activé
mcp:
  adaptive_orchestrator:
    enabled: true  # Doit être true
```

```bash
# Vérifier l'installation du package
pip list | grep albert-mcp-adaptive-orchestrator

# Réinstaller si nécessaire
pip install --upgrade albert-mcp-adaptive-orchestrator

# Redémarrer Albert
systemctl restart albert-tchapbot
```

Vérifiez les erreurs d'initialisation dans les logs :

```bash
# Activer temporairement le mode debug
sed -i 's/level: "INFO"/level: "DEBUG"/' /etc/albert/config.yaml
systemctl restart albert-tchapbot
journalctl -u albert-tchapbot -f
```

### Problème 2 : Échecs fréquents des compositions

**Symptômes :**
- Les compositions échouent fréquemment
- Messages d'erreur comme "Execution timeout" ou "Tool not found"

**Causes possibles :**
1. Timeout trop court
2. Outils MCP non disponibles
3. Erreurs dans les mappings de données

**Solutions :**

Augmenter les timeouts et limites :

```yaml
# Dans config.yaml
mcp:
  adaptive_orchestrator:
    execution_timeout: 60  # Augmenter (en secondes)
    max_composition_steps: 15  # Ajuster si nécessaire
```

Vérifier les outils MCP disponibles :

```bash
# Lister tous les outils disponibles
curl -X GET http://localhost:5000/api/tools/list \
     -H "Authorization: Bearer <votre_clé_api>" | jq

# Vérifier les journaux du registry MCP
journalctl -u mcp-registry -f
```

Activer la journalisation détaillée pour identifier les problèmes de mapping :

```yaml
# Dans config.yaml
logging:
  orchestrator:
    level: "DEBUG"
    file: "/var/log/albert/orchestrator.log"
```

### Problème 3 : L'apprentissage ne semble pas fonctionner

**Symptômes :**
- Pas de nouvelles compositions créées
- Les compositions existantes ne s'améliorent pas
- Mêmes erreurs qui se répètent

**Causes possibles :**
1. Module d'apprentissage désactivé
2. Problèmes de permissions sur la base de connaissances
3. Pas assez de données collectées

**Solutions :**

Vérifiez la configuration du module d'apprentissage :

```yaml
# Dans config.yaml
mcp:
  adaptive_orchestrator:
    learning:
      enabled: true  # Doit être true
      min_executions_for_pattern: 5  # Diminuer si nécessaire pour le test
```

Vérifiez les permissions et l'espace disque :

```bash
# Vérifier les permissions
ls -la /data/albert/knowledge_base
sudo chown -R albert:albert /data/albert/knowledge_base

# Vérifier l'espace disque
df -h /data/albert
```

Forcez une analyse d'apprentissage :

```python
# Script à exécuter via l'API d'administration d'Albert
import requests

response = requests.post(
    "http://localhost:8000/admin/api/orchestrator/force-learning",
    headers={"Authorization": "Bearer <votre_clé_admin>"},
    json={"composition_ids": ["all"]}
)
print(response.json())
```

### Problème 4 : Problèmes de performances

**Symptômes :**
- Temps de réponse lents
- Forte utilisation CPU/mémoire
- Timeouts fréquents

**Causes possibles :**
1. Trop de données stockées
2. Compositions trop complexes
3. Ressources système insuffisantes

**Solutions :**

Nettoyez les anciennes données :

```bash
# Nettoyer les anciennes données d'exécution
find /data/albert/knowledge_base/executions -type f -name "*.json" -mtime +30 -delete

# Compresser les données plus anciennes
find /data/albert/knowledge_base/executions -type f -name "*.json" -mtime +7 -exec gzip {} \;
```

Optimisez la configuration pour les performances :

```yaml
# Dans config.yaml
mcp:
  adaptive_orchestrator:
    max_parallel_executions: 3  # Limiter les exécutions parallèles
    use_caching: true  # Activer le cache
    cache_ttl: 3600  # Durée de vie du cache en secondes
```

Surveillez et augmentez les ressources si nécessaire :

```bash
# Installer outil de surveillance
sudo apt install htop

# Surveiller l'utilisation des ressources en temps réel
htop

# Limiter l'utilisation des ressources
systemctl set-property albert-tchapbot.service CPUQuota=80%
systemctl set-property albert-tchapbot.service MemoryLimit=2G
```

### Problème 5 : Les compositions ne sont pas exposées comme outils MCP

**Symptômes :**
- Les compositions validées n'apparaissent pas comme outils
- Les compositions ne sont pas utilisables depuis d'autres systèmes

**Causes possibles :**
1. Exposition des compositions désactivée
2. Problèmes de communication avec le MCP Registry
3. Compositions mal configurées

**Solutions :**

Vérifiez la configuration d'exposition :

```yaml
# Dans config.yaml
mcp:
  adaptive_orchestrator:
    expose_compositions_as_tools: true  # Doit être true
    composition_tool_prefix: "compose_"  # Préfixe pour les outils exposés
```

Vérifiez l'enregistrement auprès du registry :

```bash
# Lister les outils exposés
curl -X GET "http://localhost:5000/api/tools/list?query=compose_" \
     -H "Authorization: Bearer <votre_clé_api>" | jq
```

Forcez une ré-exposition des compositions :

```python
# Script à exécuter via l'API d'administration
import requests

response = requests.post(
    "http://localhost:8000/admin/api/orchestrator/reexpose-compositions",
    headers={"Authorization": "Bearer <votre_clé_admin>"}
)
print(response.json())
```

## Résolution des erreurs courantes

### Erreur 1 : "No MCP tool found for: server_id/tool_id"

**Cause :** L'outil spécifié dans une composition n'existe pas ou n'est pas accessible.

**Solution :**
1. Vérifiez que tous les serveurs MCP nécessaires sont installés et fonctionnels
2. Vérifiez l'orthographe exacte de server_id et tool_id dans la composition
3. Vérifiez les autorisations d'accès aux outils

```bash
# Lister tous les outils disponibles
curl -X GET http://localhost:5000/api/tools/list \
     -H "Authorization: Bearer <votre_clé_api>" | grep -E "server_id|tool_id"
```

### Erreur 2 : "Execution timeout after X seconds"

**Cause :** L'exécution d'une composition a dépassé le délai configuré.

**Solution :**
1. Augmentez le timeout dans la configuration
2. Optimisez les étapes qui prennent du temps
3. Divisez les compositions complexes en compositions plus petites

```yaml
# Dans config.yaml
mcp:
  adaptive_orchestrator:
    execution_timeout: 120  # Augmenter (en secondes)
    step_timeout: 30        # Timeout par étape
```

### Erreur 3 : "Invalid data mapping: $.stepX.output not found"

**Cause :** Problème dans le mapping des données entre les étapes d'une composition.

**Solution :**
1. Vérifiez les mappings de sortie de l'étape précédente
2. Vérifiez le format des données produites par chaque étape
3. Corrigez les chemins JSON dans les mappings

```json
// Exemple de correction d'un mapping
// Avant:
"input_mapping": {
  "data": "$.step1.results.items"
}

// Après (corrigé):
"input_mapping": {
  "data": "$.step1.result.items"
}
```

### Erreur 4 : "Cannot write to knowledge base: Permission denied"

**Cause :** Problèmes de permissions sur les dossiers de la base de connaissances.

**Solution :**
1. Vérifiez et corrigez les permissions
2. Vérifiez l'utilisateur qui exécute le service

```bash
# Corriger les permissions
sudo chown -R albert:albert /data/albert/knowledge_base
sudo chmod -R 755 /data/albert/knowledge_base

# Vérifier l'utilisateur du processus
ps aux | grep albert-tchapbot
```

### Erreur 5 : "Composition registry is corrupted or inaccessible"

**Cause :** Problèmes avec le stockage des compositions.

**Solution :**
1. Vérifiez l'intégrité des fichiers de composition
2. Restaurez depuis une sauvegarde si disponible
3. Recréez le registre des compositions

```bash
# Vérifier les fichiers de composition
find /data/albert/compositions -name "*.json" -exec jq . {} \; > /dev/null

# Sauvegarde du registre actuel
cp -r /data/albert/compositions /data/albert/compositions_backup_$(date +%Y%m%d)

# Réinitialiser le registre (dernier recours)
systemctl stop albert-tchapbot
rm -rf /data/albert/compositions/*
systemctl start albert-tchapbot
```

## Outils de diagnostic

### Outil 1 : Vérificateur de santé du système

Créez un script de diagnostic complet :

```bash
#!/bin/bash
# /opt/albert/scripts/check_orchestrator_health.sh

echo "=== Vérification de l'orchestrateur adaptatif ==="
echo

echo "1. Vérification des services"
systemctl is-active albert-tchapbot || echo "ERREUR: Albert n'est pas actif"
systemctl is-active mcp-registry || echo "ERREUR: MCP Registry n'est pas actif"

echo
echo "2. Vérification des configurations"
grep -q "enabled: true" /etc/albert/config.yaml || echo "ERREUR: Orchestrateur non activé dans la config"
grep -q "knowledge_base_path" /etc/albert/config.yaml || echo "AVERTISSEMENT: Chemin de la base de connaissances non configuré"

echo
echo "3. Vérification des dossiers"
[[ -d /data/albert/compositions ]] || echo "ERREUR: Dossier des compositions inexistant"
[[ -d /data/albert/knowledge_base ]] || echo "ERREUR: Dossier de la base de connaissances inexistant"

echo
echo "4. Vérification des permissions"
[[ -w /data/albert/compositions ]] || echo "ERREUR: Dossier des compositions non inscriptible"
[[ -w /data/albert/knowledge_base ]] || echo "ERREUR: Dossier de la base de connaissances non inscriptible"

echo
echo "5. Vérification de l'API"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health | grep -q "200" || echo "ERREUR: API Albert non accessible"
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/api/health | grep -q "200" || echo "ERREUR: API MCP Registry non accessible"

echo
echo "6. Statistiques"
echo "Compositions: $(find /data/albert/compositions -name "*.json" | wc -l)"
echo "Exécutions enregistrées: $(find /data/albert/knowledge_base/executions -name "*.json" | wc -l)"
echo "Utilisation disque: $(du -sh /data/albert)"
echo "Mémoire disponible: $(free -h | grep Mem | awk '{print $7}')"

echo
echo "=== Fin de la vérification ==="
```

### Outil 2 : Visualiseur de compositions

Créez un script pour visualiser les compositions existantes :

```python
#!/usr/bin/env python3
# /opt/albert/scripts/list_compositions.py

import json
import os
import sys
from datetime import datetime
import argparse

def format_time(time_str):
    try:
        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return time_str

def list_compositions(directory, status=None, sort_by='created_at'):
    """Liste les compositions avec filtre optionnel par statut"""
    compositions = []
    
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'r') as f:
                    comp = json.load(f)
                    
                if status and comp.get('status') != status:
                    continue
                    
                compositions.append({
                    'id': comp.get('id', 'unknown'),
                    'name': comp.get('name', 'unnamed'),
                    'intent_type': comp.get('intent_type', 'unknown'),
                    'created_at': comp.get('created_at', ''),
                    'status': comp.get('status', 'unknown'),
                    'version': comp.get('version', 1),
                    'steps': len(comp.get('steps', [])),
                    'success_rate': comp.get('stats', {}).get('success_rate', 0),
                    'usage_count': comp.get('stats', {}).get('usage_count', 0)
                })
            except json.JSONDecodeError:
                print(f"Erreur: {filepath} n'est pas un JSON valide")
            except Exception as e:
                print(f"Erreur lors de la lecture de {filepath}: {e}")
                
    if sort_by in compositions[0] if compositions else {}:
        compositions.sort(key=lambda x: x[sort_by], reverse=True)
                
    return compositions

def display_compositions(compositions):
    """Affiche les compositions dans un format tabulaire"""
    if not compositions:
        print("Aucune composition trouvée")
        return
        
    # Entêtes
    headers = ['ID', 'Nom', 'Type', 'Créé le', 'Statut', 'Ver', 'Étapes', 'Succès', 'Usage']
    widths = [20, 30, 15, 19, 10, 3, 6, 6, 5]
    
    # Ligne d'entête
    header_fmt = ''.join(f"{{:<{w}}}" for w in widths)
    print(header_fmt.format(*headers))
    print('-' * sum(widths))
    
    # Contenu
    row_fmt = ''.join(f"{{:<{w}}}" for w in widths)
    for comp in compositions:
        print(row_fmt.format(
            comp['id'][:18] + '..' if len(comp['id']) > 20 else comp['id'],
            comp['name'][:28] + '..' if len(comp['name']) > 30 else comp['name'],
            comp['intent_type'][:13] + '..' if len(comp['intent_type']) > 15 else comp['intent_type'],
            format_time(comp['created_at']),
            comp['status'],
            str(comp['version']),
            str(comp['steps']),
            f"{comp['success_rate']:.2f}" if comp['success_rate'] else 'N/A',
            str(comp['usage_count'])
        ))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Liste les compositions dans le registre')
    parser.add_argument('--dir', default='/data/albert/compositions', help='Répertoire des compositions')
    parser.add_argument('--status', help='Filtrer par statut (learning, validated, deprecated)')
    parser.add_argument('--sort', default='created_at', help='Trier par (created_at, usage_count, success_rate)')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.dir):
        print(f"Erreur: Le répertoire {args.dir} n'existe pas")
        sys.exit(1)
        
    compositions = list_compositions(args.dir, args.status, args.sort)
    display_compositions(compositions)
```

### Outil 3 : Testeur de compositions

Créez un outil pour tester directement une composition :

```python
#!/usr/bin/env python3
# /opt/albert/scripts/test_composition.py

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime

sys.path.append('/opt/albert')
from albert_mcp_adaptive_orchestrator import AdaptiveOrchestrator
from albert.utils.mcp import MCPRegistryClient

async def test_composition(comp_id, params, config_file):
    """Teste l'exécution d'une composition spécifique"""
    
    # Charger la configuration
    with open(config_file, 'r') as f:
        import yaml
        config = yaml.safe_load(f)
    
    # Initialiser le client MCP Registry
    mcp_registry = MCPRegistryClient(
        config['mcp']['registry']['url'],
        config['mcp']['registry']['api_key']
    )
    
    # Initialiser l'orchestrateur
    orchestrator = AdaptiveOrchestrator(
        config['mcp']['adaptive_orchestrator'],
        mcp_registry
    )
    
    # Exécuter la composition directement
    print(f"Exécution de la composition {comp_id} avec les paramètres: {params}")
    print("Démarrage à", datetime.now().strftime('%H:%M:%S'))
    
    start_time = time.time()
    result = await orchestrator.execute_composition(comp_id, params)
    elapsed = time.time() - start_time
    
    print(f"Exécution terminée en {elapsed:.2f} secondes")
    print(f"Statut: {result.get('status', 'unknown')}")
    
    # Afficher le résultat
    print("\n=== Résultat ===")
    if result.get('status') == 'success':
        print("Succès!")
        print(json.dumps(result.get('data', {}), indent=2))
    else:
        print("Échec!")
        print(f"Erreur: {result.get('error', 'Inconnue')}")
        
        # Afficher les détails des étapes
        if 'execution_info' in result and 'steps' in result['execution_info']:
            print("\n=== Détails des étapes ===")
            for step_id, step_info in result['execution_info']['steps'].items():
                status = step_info.get('status', 'unknown')
                print(f"Étape {step_id}: {status}")
                if status == 'failure':
                    print(f"  Erreur: {step_info.get('error', 'Inconnue')}")
    
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Teste une composition spécifique')
    parser.add_argument('comp_id', help='ID de la composition à tester')
    parser.add_argument('--params', default='{}', help='Paramètres JSON pour la composition')
    parser.add_argument('--config', default='/etc/albert/config.yaml', help='Fichier de configuration')
    
    args = parser.parse_args()
    
    # Valider le fichier de configuration
    if not os.path.isfile(args.config):
        print(f"Erreur: Le fichier de configuration {args.config} n'existe pas")
        sys.exit(1)
    
    # Charger et valider les paramètres JSON
    try:
        params = json.loads(args.params)
    except json.JSONDecodeError:
        print(f"Erreur: Paramètres JSON invalides: {args.params}")
        sys.exit(1)
    
    # Exécuter le test
    asyncio.run(test_composition(args.comp_id, params, args.config))
```

## Journalisation avancée

Pour un diagnostic plus approfondi, activez la journalisation avancée :

```yaml
# Dans config.yaml
logging:
  orchestrator:
    level: "DEBUG"
    file: "/var/log/albert/orchestrator.log"
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    max_size: 10485760  # 10 Mo
    backup_count: 5
    categories:
      execution: "DEBUG"  # Journalisation détaillée des exécutions
      learning: "DEBUG"   # Journalisation détaillée de l'apprentissage
      mapping: "DEBUG"    # Journalisation détaillée des mappings de données
      registry: "INFO"    # Opérations du registre de compositions
```

### Rotation des journaux

Configurez logrotate pour gérer les fichiers de journaux :

```
# /etc/logrotate.d/albert-orchestrator
/var/log/albert/orchestrator.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 albert albert
    postrotate
        systemctl kill -s HUP albert-tchapbot
    endscript
}
```

## Restauration et récupération

### Sauvegarde régulière

Configurez des sauvegardes régulières des compositions et de la base de connaissances :

```bash
#!/bin/bash
# /etc/cron.daily/backup-albert-orchestrator

BACKUP_DIR="/var/backups/albert/orchestrator"
DATE=$(date +%Y%m%d)

# Créer le répertoire de sauvegarde
mkdir -p "${BACKUP_DIR}"

# Sauvegarder les compositions
tar -czf "${BACKUP_DIR}/compositions_${DATE}.tar.gz" /data/albert/compositions

# Sauvegarder la base de connaissances (peut être volumineuse)
tar -czf "${BACKUP_DIR}/knowledge_base_${DATE}.tar.gz" /data/albert/knowledge_base

# Garder seulement les 7 dernières sauvegardes
find "${BACKUP_DIR}" -name "compositions_*.tar.gz" -mtime +7 -delete
find "${BACKUP_DIR}" -name "knowledge_base_*.tar.gz" -mtime +7 -delete
```

### Restauration de l'orchestrateur

En cas de corruption majeure, suivez cette procédure de restauration :

```bash
#!/bin/bash
# /opt/albert/scripts/restore_orchestrator.sh

if [ $# -ne 1 ]; then
    echo "Usage: $0 BACKUP_DATE (format: YYYYMMDD)"
    exit 1
fi

DATE=$1
BACKUP_DIR="/var/backups/albert/orchestrator"

# Vérifier que les fichiers de sauvegarde existent
if [ ! -f "${BACKUP_DIR}/compositions_${DATE}.tar.gz" ]; then
    echo "Erreur: Sauvegarde des compositions introuvable pour la date ${DATE}"
    exit 1
fi

if [ ! -f "${BACKUP_DIR}/knowledge_base_${DATE}.tar.gz" ]; then
    echo "Erreur: Sauvegarde de la base de connaissances introuvable pour la date ${DATE}"
    exit 1
fi

# Arrêter les services
echo "Arrêt des services..."
systemctl stop albert-tchapbot

# Sauvegarder l'état actuel avant restauration
echo "Sauvegarde de l'état actuel..."
mv /data/albert/compositions /data/albert/compositions.bak
mv /data/albert/knowledge_base /data/albert/knowledge_base.bak

# Restaurer depuis la sauvegarde
echo "Restauration des compositions..."
mkdir -p /data/albert/compositions
tar -xzf "${BACKUP_DIR}/compositions_${DATE}.tar.gz" -C /

echo "Restauration de la base de connaissances..."
mkdir -p /data/albert/knowledge_base
tar -xzf "${BACKUP_DIR}/knowledge_base_${DATE}.tar.gz" -C /

# Corriger les permissions
echo "Correction des permissions..."
chown -R albert:albert /data/albert/compositions
chown -R albert:albert /data/albert/knowledge_base
chmod -R 755 /data/albert/compositions
chmod -R 755 /data/albert/knowledge_base

# Redémarrer les services
echo "Redémarrage des services..."
systemctl start albert-tchapbot

echo "Restauration terminée. Vérifiez les journaux pour confirmer que tout fonctionne correctement."
```

## Optimisations et bonnes pratiques

### Optimisation des performances

Pour améliorer les performances de l'orchestrateur adaptatif :

1. **Optimisez le stockage**
   - Supprimez régulièrement les anciennes données d'exécution
   - Compressez les données historiques
   - Utilisez un stockage SSD pour la base de connaissances

2. **Optimisez la mémoire**
   - Limitez le nombre de compositions en mémoire
   - Utilisez la mise en cache des résultats fréquents
   - Augmentez la RAM allouée au service

3. **Optimisez les compositions**
   - Évitez les compositions avec trop d'étapes
   - Utilisez des timeouts appropriés par étape
   - Privilégiez les outils légers et rapides

### Bonnes pratiques de surveillance

1. **Surveillez proactivement**
   - Mettez en place des alertes sur les taux d'échec
   - Surveillez l'espace disque de la base de connaissances
   - Surveillez le temps de réponse moyen

2. **Visualisez les tendances**
   - Suivez l'évolution du nombre de compositions
   - Analysez les taux de succès dans le temps
   - Identifiez les modèles d'utilisation

3. **Mettez en place un tableau de bord**
   - Affichez les compositions les plus utilisées
   - Suivez les métriques de performance
   - Visualisez l'apprentissage du système

## Ressources supplémentaires

- [Documentation complète de l'orchestrateur adaptatif](/docs/MCP-ORCHESTRATION-ADAPTATIVE/README.md)
- [Guide d'intégration avec Albert](/docs/MCP-ORCHESTRATION-ADAPTATIVE/06-INTEGRATION-ALBERT.md)
- [Documentation de l'API MCP Registry](https://mcp-registry.readthedocs.io/)
- [Forum de support](https://forum.albert-tchapbot.com/category/mcp-orchestration)

---

*Ce guide de dépannage est régulièrement mis à jour avec les problèmes et solutions les plus courants rencontrés par les utilisateurs de l'orchestrateur adaptatif.* 