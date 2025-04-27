# Guide d'installation des workflows n8n pour Albert-Tchap

Ce guide vous accompagne dans la configuration des workflows n8n nécessaires pour l'intégration avec Albert-Tchap.

## Prérequis

- n8n version 1.88.0 ou supérieure
- Un token API n8n pour l'authentification

## 1. Workflow "Catalogue Complet"

Ce workflow expose un endpoint pour récupérer tous les outils disponibles.

1. **Créer un nouveau workflow**
   - Nom : "Catalogue-Tools"
   - Tags : "expose"

2. **Ajouter un nœud Webhook**
   - Méthode : GET
   - Chemin : /catalog/all
   - Authentification : Bearer Token
   - Token : [Votre token pour Albert]

3. **Ajouter un nœud n8n**
   - Opération : Workflows (Get Many)
   - Filtrer avec le tag : "expose"

4. **Ajouter un nœud Code** avec le contenu suivant :

```javascript
// Code à placer dans le nœud Code
const workflows = items[0].json.data;

// Extraire les webhooks
const catalogItems = [];

for (const workflow of workflows) {
  // Chercher les nœuds Webhook dans chaque workflow
  const webhookNodes = workflow.nodes.filter(node => 
    node.type === 'n8n-nodes-base.webhook' || 
    node.type === 'n8n-nodes-langchain.mcptrigger'
  );
  
  for (const node of webhookNodes) {
    if (node.type === 'n8n-nodes-base.webhook') {
      catalogItems.push({
        id: `${workflow.id}_${node.name}`,
        name: node.parameters.path.replace('/', ''),
        type: "webhook",
        category: workflow.tags[0] || "general",
        description: workflow.name,
        url: `${$node["Webhook"].json.webhookFullUrl.replace('/catalog/all', '')}${node.parameters.path}`,
        parameters: node.parameters.options?.bodyParametersUi?.parameters || []
      });
    } else if (node.type === 'n8n-nodes-langchain.mcptrigger') {
      // Ajouter référence au serveur MCP
      catalogItems.push({
        id: `${workflow.id}_mcp`,
        name: "mcp_tools",
        type: "mcp",
        category: "tools",
        description: "Serveur d'outils MCP",
        url: `${$node["Webhook"].json.webhookFullUrl.replace('/catalog/all', '/mcp')}`,
        schema_url: `${$node["Webhook"].json.webhookFullUrl.replace('/catalog/all', '/mcp/schema')}`
      });
    }
  }
}

return [{ json: { tools: catalogItems } }];
```

5. **Ajouter un nœud "Respond to Webhook"** pour renvoyer le résultat formaté

6. **Activer le workflow**

## 2. Workflow "MCP Hub" 

Ce workflow expose un serveur MCP pour les outils n8n.

1. **Créer un nouveau workflow**
   - Nom : "MCP-Hub"
   - Tags : "expose"

2. **Ajouter un nœud "MCP Server Trigger"**
   - Path : /mcp
   - Authentication : Bearer Token
   - Token : [Votre token pour Albert]

3. **Ajouter des "Custom n8n Workflow Tool"** pour exposer vos workflows :
   - Exemple 1 :
     - Nom : send_email
     - Description : "Envoie un email aux destinataires spécifiés"
     - Workflow : [Sélectionner votre workflow d'envoi d'email]
     - Paramètres : destinataire, sujet, contenu

4. **Activer le workflow**

## 3. Configuration d'Albert-Tchap

1. **Modifier le fichier .env d'Albert-Tchap** :

```
N8N_ENABLED=True
N8N_BASE_URL=https://votre-instance-n8n.fr
N8N_AUTH_TOKEN=votre-token-bearer
N8N_MCP_URL=https://votre-instance-n8n.fr/webhook/mcp
N8N_TOOLS_CACHE_TTL=300
```

2. **Redémarrer Albert-Tchap**

## 4. Test des commandes

Dans un salon avec Albert-Tchap, testez les commandes suivantes :

```
!tools
!tools email
!run send_email destinataire="test@example.com" sujet="Test" contenu="Ceci est un test"
```

## Dépannage

- Si les commandes ne fonctionnent pas, vérifiez les logs d'Albert-Tchap et de n8n
- Assurez-vous que les tokens d'authentification sont correctement configurés
- Vérifiez que les workflows sont bien activés dans n8n 