# Exemples d'utilisation

Ce document présente des exemples concrets d'utilisation du système d'orchestration adaptative MCP dans différents contextes. Ces exemples illustrent comment l'orchestrateur détecte les intentions, compose les outils et apprend au fil du temps.

## Exemple 1 : Gestion documentaire

### Scénario
L'utilisateur souhaite rechercher des documents sur un sujet spécifique, les organiser et créer un résumé.

### Interaction utilisateur

```
Utilisateur: Peux-tu chercher tous nos documents sur le projet Alpha, les organiser par date et me faire un résumé des points clés ?
```

### Analyse par l'orchestrateur

1. **Détection d'intention** : L'orchestrateur identifie une intention de type "recherche_documents" avec le paramètre "sujet" = "projet Alpha"
2. **Recherche de composition** : Aucune composition existante ne correspond exactement à cette demande complexe
3. **Décomposition** : L'orchestrateur décompose la demande en trois sous-tâches :
   - Recherche de documents
   - Organisation chronologique
   - Génération de résumé

### Composition créée

```json
{
  "id": "comp_doc_search_organize_summarize_123",
  "name": "Recherche, organisation et résumé de documents",
  "description": "Recherche des documents sur un sujet, les organise chronologiquement et génère un résumé des points clés",
  "intent_type": "recherche_documents",
  "version": 1,
  "created_at": "2023-09-15T10:23:45Z",
  "status": "learning",
  "steps": [
    {
      "id": "step1",
      "server_id": "filesystem",
      "tool_id": "search_documents",
      "description": "Recherche des documents correspondant au sujet",
      "input_mapping": {
        "query": "$.sujet",
        "max_results": 20
      },
      "output_mapping": {
        "documents": "$.result.files"
      },
      "required": true
    },
    {
      "id": "step2",
      "server_id": "document",
      "tool_id": "sort_documents",
      "description": "Trie les documents par date",
      "input_mapping": {
        "documents": "$.step1.documents",
        "sort_by": "date",
        "order": "desc"
      },
      "output_mapping": {
        "sorted_documents": "$.result.sorted_files"
      },
      "required": true
    },
    {
      "id": "step3",
      "server_id": "document",
      "tool_id": "extract_content",
      "description": "Extrait le contenu des documents",
      "input_mapping": {
        "documents": "$.step2.sorted_documents",
        "max_documents": 10
      },
      "output_mapping": {
        "contents": "$.result.contents"
      },
      "required": true
    },
    {
      "id": "step4",
      "server_id": "llm",
      "tool_id": "generate_summary",
      "description": "Génère un résumé des points clés",
      "input_mapping": {
        "texts": "$.step3.contents",
        "max_length": 1000,
        "focus": "points clés"
      },
      "output_mapping": {
        "summary": "$.result.summary"
      },
      "required": true
    }
  ],
  "input_schema": {
    "type": "object",
    "properties": {
      "sujet": {
        "type": "string",
        "description": "Sujet de recherche pour les documents"
      }
    },
    "required": ["sujet"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "documents": {
        "type": "array",
        "description": "Liste des documents trouvés"
      },
      "summary": {
        "type": "string",
        "description": "Résumé des points clés"
      }
    }
  }
}
```

### Résultat d'exécution

```
J'ai trouvé 17 documents relatifs au projet Alpha et voici un résumé des points clés :

Résumé du Projet Alpha :

1. Objectifs principaux :
   - Développement d'une plateforme de gestion de données client intégrée
   - Implémentation d'analyses prédictives pour le comportement utilisateur
   - Migration de l'infrastructure vers un environnement cloud sécurisé

2. Progression actuelle :
   - Phase 1 (Architecture) : Terminée le 15/06/2023 
   - Phase 2 (Développement backend) : En cours - 75% complétée
   - Phase 3 (Interface utilisateur) : Démarrage prévu le 01/10/2023

3. Points d'attention :
   - Retard de 2 semaines sur le module d'authentification
   - Problèmes de performance identifiés dans le traitement de grandes quantités de données
   - Besoin de ressources supplémentaires pour la phase 3

Documents les plus récents :
1. "Rapport d'avancement - Août 2023.pdf" (01/09/2023)
2. "Spécifications UI - v2.3.docx" (28/08/2023)
3. "Analyse de performance - Backend.xlsx" (15/08/2023)

Voulez-vous que je vous envoie certains de ces documents ?
```

### Apprentissage

Après plusieurs utilisations réussies, cette composition passe du statut "learning" à "validated" et devient disponible comme un outil de haut niveau pour des requêtes futures similaires.

## Exemple 2 : Analyse de données structurées

### Scénario
L'utilisateur souhaite analyser les données de ventes d'un trimestre spécifique et générer un rapport visuel.

### Interaction utilisateur

```
Utilisateur: Analyse les ventes du Q2 2023 et génère un rapport visuel montrant les tendances par région et par catégorie de produit
```

### Analyse par l'orchestrateur

1. **Détection d'intention** : L'orchestrateur identifie une intention de type "analyse_donnees" avec les paramètres "periode" = "Q2 2023" et "type_analyse" = "ventes"
2. **Recherche de composition** : L'orchestrateur trouve une composition similaire qui analyse les ventes, mais doit l'adapter pour le reporting visuel

### Exécution et adaptation

L'orchestrateur exécute une composition en 5 étapes :
1. Connexion à la source de données (Grist)
2. Extraction des données de ventes pour Q2 2023
3. Transformation et agrégation des données
4. Génération de visualisations
5. Compilation d'un rapport PDF

### Code d'exécution

```python
# Exemple d'exécution par l'orchestrateur

async def execute_sales_analysis(params):
    # Étape 1: Connexion à Grist
    grist_connection = await mcp_registry.execute_tool(
        "grist", "connect_database",
        {"doc_id": "sales_database"}
    )
    
    # Étape 2: Extraction des données de ventes
    sales_data = await mcp_registry.execute_tool(
        "grist", "execute_sql_query",
        {
            "doc_id": grist_connection["doc_id"],
            "sql_query": """
                SELECT date, region, product_category, product_name, 
                       quantity, unit_price, quantity * unit_price as revenue
                FROM sales
                WHERE date BETWEEN '2023-04-01' AND '2023-06-30'
                ORDER BY date
            """
        }
    )
    
    # Étape 3: Agrégation des données
    aggregated_data = await mcp_registry.execute_tool(
        "data_processing", "aggregate_data",
        {
            "data": sales_data["result"],
            "group_by": ["region", "product_category"],
            "metrics": [
                {"field": "revenue", "operation": "sum"},
                {"field": "quantity", "operation": "sum"}
            ]
        }
    )
    
    # Étape 4: Génération de visualisations
    visualizations = await mcp_registry.execute_tool(
        "visualization", "generate_charts",
        {
            "data": aggregated_data["result"],
            "charts": [
                {
                    "type": "bar",
                    "x": "region",
                    "y": "sum_revenue",
                    "title": "Ventes par région - Q2 2023"
                },
                {
                    "type": "pie",
                    "labels": "product_category",
                    "values": "sum_revenue",
                    "title": "Répartition des ventes par catégorie"
                },
                {
                    "type": "line",
                    "data": sales_data["result"],
                    "x": "date",
                    "y": "revenue",
                    "group": "region",
                    "title": "Évolution des ventes par région"
                }
            ]
        }
    )
    
    # Étape 5: Génération du rapport PDF
    report = await mcp_registry.execute_tool(
        "document", "generate_report",
        {
            "title": "Analyse des ventes - Q2 2023",
            "sections": [
                {
                    "title": "Résumé",
                    "content": f"Analyse des ventes pour la période du 01/04/2023 au 30/06/2023. Total des ventes: {aggregated_data['total_revenue']:,.2f} €"
                },
                {
                    "title": "Visualisations",
                    "charts": visualizations["charts"]
                },
                {
                    "title": "Données détaillées",
                    "tables": [
                        {
                            "title": "Ventes par région et catégorie",
                            "data": aggregated_data["result"]
                        }
                    ]
                }
            ],
            "format": "pdf"
        }
    )
    
    return {
        "report_url": report["file_url"],
        "summary": report["summary"],
        "charts": visualizations["charts"]
    }
```

### Résultat

```
Voici l'analyse des ventes pour le Q2 2023 :

📊 Principales tendances :

1. Régions :
   - Europe : 3,2M€ (+12% vs Q1)
   - Amérique du Nord : 2,8M€ (+8%)
   - Asie-Pacifique : 1,5M€ (+15%)
   - Amérique Latine : 0,8M€ (-3%)

2. Catégories de produits :
   - Solutions Cloud : 4,1M€ (48% du total)
   - Services professionnels : 2,3M€ (27%)
   - Licences logicielles : 1,9M€ (22%)
   - Formation : 0,3M€ (3%)

3. Tendances notables :
   - Forte croissance des solutions cloud en Asie-Pacifique (+23%)
   - Baisse des services professionnels en Amérique Latine (-8%)
   - Les ventes de licences logicielles se stabilisent en Europe

J'ai généré un rapport complet avec toutes les visualisations ici : [Rapport des ventes Q2 2023](/files/sales_report_q2_2023.pdf)

Souhaitez-vous une analyse plus détaillée sur une région ou catégorie spécifique ?
```

## Exemple 3 : Automatisation multi-étapes avec apprentissage

### Scénario
L'utilisateur souhaite automatiser le processus d'onboarding d'un nouveau client, qui implique plusieurs systèmes et étapes.

### Interaction utilisateur initiale

```
Utilisateur: Lance le processus d'onboarding pour le nouveau client Technova. Leurs informations sont dans l'email que j'ai reçu hier de Marc Bernard.
```

### Première exécution (apprentissage)

Lors de la première exécution, l'orchestrateur n'a pas de composition existante pour ce type de demande. Il décompose donc le processus en étapes individuelles :

1. Extraction des informations de l'email
2. Création du client dans le CRM
3. Création d'un espace de stockage pour les documents
4. Génération du contrat à partir du modèle
5. Envoi d'un email de bienvenue

Certaines étapes échouent lors de cette première exécution, et l'orchestrateur doit s'adapter :

```
Étape 3 : Échec - Outil filesystem/create_storage_space renvoie une erreur d'autorisation
Alternative : Utilisation de l'outil storage/create_client_folder qui fonctionne
```

### Composition améliorée

Après plusieurs exécutions et ajustements, l'orchestrateur finalise une composition optimisée :

```json
{
  "id": "comp_client_onboarding_456",
  "name": "Processus d'onboarding client",
  "description": "Automatise l'ensemble du processus d'onboarding d'un nouveau client",
  "intent_type": "onboarding_client",
  "version": 3,
  "created_at": "2023-08-10T15:32:10Z",
  "updated_at": "2023-09-20T09:17:45Z",
  "status": "validated",
  "stats": {
    "usage_count": 12,
    "success_rate": 0.92,
    "avg_execution_time": 45.3
  },
  "steps": [
    {
      "id": "step1",
      "server_id": "email",
      "tool_id": "extract_email_info",
      "description": "Extrait les informations du client depuis l'email",
      "input_mapping": {
        "sender": "$.email_expediteur",
        "subject_contains": "$.client_name",
        "max_days_ago": 7
      },
      "output_mapping": {
        "client_info": "$.result.extracted_info"
      },
      "required": true
    },
    {
      "id": "step2",
      "server_id": "crm",
      "tool_id": "create_client",
      "description": "Crée le client dans le CRM",
      "input_mapping": {
        "name": "$.client_info.company_name",
        "contact": "$.client_info.contact_name",
        "email": "$.client_info.email",
        "phone": "$.client_info.phone",
        "address": "$.client_info.address",
        "type": "$.client_info.company_type"
      },
      "output_mapping": {
        "client_id": "$.result.client_id",
        "crm_url": "$.result.client_url"
      },
      "required": true
    },
    {
      "id": "step3",
      "server_id": "storage",
      "tool_id": "create_client_folder",
      "description": "Crée un dossier de stockage pour le client",
      "input_mapping": {
        "client_name": "$.client_info.company_name",
        "client_id": "$.step2.client_id"
      },
      "output_mapping": {
        "folder_id": "$.result.folder_id",
        "folder_url": "$.result.folder_url"
      },
      "required": true
    },
    {
      "id": "step4",
      "server_id": "document",
      "tool_id": "generate_contract",
      "description": "Génère le contrat à partir du modèle",
      "input_mapping": {
        "template_id": "contract_template_standard",
        "client_name": "$.client_info.company_name",
        "client_address": "$.client_info.address",
        "start_date": "$.current_date",
        "client_type": "$.client_info.company_type"
      },
      "output_mapping": {
        "contract_id": "$.result.document_id",
        "contract_url": "$.result.document_url"
      },
      "required": true
    },
    {
      "id": "step5",
      "server_id": "storage",
      "tool_id": "upload_file",
      "description": "Télécharge le contrat dans le dossier client",
      "input_mapping": {
        "folder_id": "$.step3.folder_id",
        "file_url": "$.step4.contract_url",
        "file_name": "Contrat_{{client_info.company_name}}.pdf"
      },
      "output_mapping": {
        "stored_file_url": "$.result.file_url"
      },
      "required": true
    },
    {
      "id": "step6",
      "server_id": "email",
      "tool_id": "send_template_email",
      "description": "Envoie l'email de bienvenue au client",
      "input_mapping": {
        "template_id": "welcome_email_template",
        "to": "$.client_info.email",
        "cc": "$.user_email",
        "variables": {
          "client_name": "$.client_info.company_name",
          "contact_name": "$.client_info.contact_name",
          "crm_url": "$.step2.crm_url",
          "folder_url": "$.step3.folder_url",
          "contract_url": "$.step5.stored_file_url"
        }
      },
      "output_mapping": {
        "email_sent": "$.result.success",
        "email_id": "$.result.email_id"
      },
      "required": true
    }
  ],
  "optimization_history": [
    {
      "timestamp": "2023-08-25T14:12:30Z",
      "changes": [
        {
          "type": "replace_step",
          "step_id": "step3",
          "original": {
            "server_id": "filesystem",
            "tool_id": "create_storage_space"
          },
          "new": {
            "server_id": "storage",
            "tool_id": "create_client_folder"
          }
        }
      ]
    },
    {
      "timestamp": "2023-09-20T09:17:45Z",
      "changes": [
        {
          "type": "add_step",
          "step_id": "step5",
          "after": "step4"
        }
      ]
    }
  ]
}
```

### Résultat final après optimisation

```
J'ai terminé le processus d'onboarding pour Technova :

✅ Extraction des informations depuis l'email de Marc Bernard
   → Contact principal : Sophie Dubois (sophie.dubois@technova.com)
   → Type d'entreprise : Tech B2B, ~150 employés

✅ Création du profil client dans le CRM
   → ID: TECH-2023-094
   → Fiche client : https://crm.votresociete.com/clients/TECH-2023-094

✅ Création de l'espace de stockage
   → Dossier : https://drive.votresociete.com/clients/technova/

✅ Génération du contrat standard
   → Le contrat a été personnalisé et placé dans l'espace client
   → URL: https://drive.votresociete.com/clients/technova/Contrat_Technova.pdf

✅ Email de bienvenue envoyé
   → Destinataire: sophie.dubois@technova.com
   → Vous avez été mis en copie de cet email

Prochaines étapes recommandées :
1. Planifier la réunion de kickoff (voulez-vous que je le fasse ?)
2. Assigner un chef de projet
3. Configurer les accès à la plateforme pour le client

Le processus complet a été documenté dans le CRM pour référence future.
```

## Exemple 4 : Intégration de données entre systèmes

### Scénario
L'utilisateur souhaite synchroniser des données entre Grist et un autre système, en appliquant des transformations.

### Requête utilisateur

```
Utilisateur: Synchronise les données clients du document Grist "clients_database" vers notre CRM. Assure-toi de mettre à jour uniquement les clients modifiés depuis la dernière synchronisation.
```

### Composition créée et exécutée

L'orchestrateur crée une composition qui :
1. Récupère les données de la dernière synchronisation
2. Extrait les clients modifiés depuis cette date
3. Transforme les données au format du CRM
4. Met à jour les enregistrements dans le CRM
5. Enregistre les détails de synchronisation

### Code Python utilisé pour la transformation des données

```python
# Exemple de transformateur personnalisé utilisé dans la composition

@register_transformer("grist_to_crm_client")
class GristToCRMClientTransformer(DataTransformer):
    """Transforme les données client du format Grist vers le format CRM"""
    
    def transform(self, input_data, config=None):
        """
        Transforme un client du format Grist vers le format CRM
        
        Args:
            input_data: Données du client au format Grist (dict)
            config: Configuration optionnelle
            
        Returns:
            Données du client au format CRM (dict)
        """
        if not input_data:
            return None
            
        # Mappage des champs
        crm_data = {
            "name": input_data.get("company_name", ""),
            "company_type": input_data.get("type", "Other"),
            "status": self._map_status(input_data.get("status", "")),
            "contacts": [],
            "addresses": [],
            "custom_fields": {}
        }
        
        # Transformer le contact principal
        if input_data.get("contact_name"):
            names = input_data.get("contact_name", "").split(" ", 1)
            first_name = names[0] if names else ""
            last_name = names[1] if len(names) > 1 else ""
            
            crm_data["contacts"].append({
                "type": "primary",
                "first_name": first_name,
                "last_name": last_name,
                "email": input_data.get("email", ""),
                "phone": input_data.get("phone", ""),
                "job_title": input_data.get("contact_title", "")
            })
        
        # Transformer l'adresse
        if input_data.get("address"):
            address_parts = self._parse_address(input_data.get("address", ""))
            
            crm_data["addresses"].append({
                "type": "billing",
                "street": address_parts.get("street", ""),
                "city": address_parts.get("city", ""),
                "postal_code": address_parts.get("postal_code", ""),
                "country": address_parts.get("country", "")
            })
        
        # Champs personnalisés
        crm_data["custom_fields"] = {
            "industry": input_data.get("industry", ""),
            "revenue": input_data.get("annual_revenue", 0),
            "employee_count": input_data.get("employees", 0),
            "grist_id": input_data.get("id", 0),
            "last_updated": input_data.get("updated_at", "")
        }
        
        return crm_data
        
    def _map_status(self, grist_status):
        """Mappe les statuts Grist vers les statuts CRM"""
        status_map = {
            "active": "Active",
            "lead": "Prospect",
            "inactive": "Inactive",
            "churned": "Former Customer"
        }
        return status_map.get(grist_status.lower(), "Other")
        
    def _parse_address(self, address_string):
        """Analyse une adresse en texte brut et la divise en composants"""
        # Logique simplifiée - en production, utilisez une bibliothèque d'analyse d'adresse
        parts = {}
        lines = address_string.split(',')
        
        if len(lines) >= 3:
            parts["street"] = lines[0].strip()
            
            city_zip = lines[1].strip().split(' ')
            if len(city_zip) > 1:
                parts["postal_code"] = city_zip[-1]
                parts["city"] = ' '.join(city_zip[:-1])
            else:
                parts["city"] = lines[1].strip()
                
            parts["country"] = lines[2].strip()
        else:
            parts["street"] = address_string
            
        return parts
```

### Résultat de synchronisation

```
Synchronisation terminée avec succès :

✅ 37 clients extraits de Grist "clients_database"
✅ 12 clients modifiés depuis la dernière synchronisation (15/09/2023)
✅ 12 clients mis à jour dans le CRM

Détails des mises à jour :
- 8 clients avec informations de contact modifiées
- 3 clients avec changement de statut
- 1 client avec nouvelle adresse

Tous les enregistrements ont été mis à jour avec succès. La prochaine synchronisation automatique est prévue pour demain à 08:00.

Voulez-vous voir la liste des clients mis à jour ?
```

## Exemple 5 : Composition qui s'améliore avec le temps

Cet exemple montre comment une composition s'améliore progressivement grâce au module d'apprentissage.

### Version initiale (v1)

Composition initiale pour rechercher et résumer un sujet :

```
Étapes :
1. Recherche web (moteur de recherche) -> résultats bruts
2. Extraction de contenu -> textes des pages
3. Génération de résumé -> résumé final
```

### Problème détecté

Après plusieurs utilisations, le module d'apprentissage détecte que l'étape 1 échoue souvent avec des timeouts, et que les résumés manquent de structure.

### Version améliorée (v2)

```
Étapes :
1. Recherche web (API optimisée) -> résultats avec meilleur filtrage
2. Extraction de contenu avec vérification de pertinence
3. Catégorisation des informations
4. Génération de résumé structuré
```

### Version finale (v3)

Après plus d'apprentissage, la composition intègre maintenant des sources multiples et une meilleure organisation :

```
Étapes :
1. Recherche web parallélisée sur plusieurs sources
2. Extraction de contenu avec filtrage des doublons
3. Vérification de la fraîcheur des informations
4. Catégorisation et hiérarchisation des informations
5. Génération de résumé structuré avec points clés
6. Ajout de sources et références
```

### Comparaison des résultats

**Version 1** (Score qualité : 0.65)
```
Voici un résumé sur l'intelligence artificielle : L'IA est un domaine informatique qui simule l'intelligence humaine. Elle inclut l'apprentissage automatique et les réseaux de neurones. Ses applications incluent la reconnaissance d'images, le traitement du langage naturel et les véhicules autonomes.
```

**Version 3** (Score qualité : 0.92)
```
# Intelligence Artificielle : Vue d'ensemble 2023

## Définition et portée
L'IA désigne les systèmes informatiques capables de réaliser des tâches nécessitant traditionnellement l'intelligence humaine. Elle englobe plusieurs sous-domaines comme l'apprentissage automatique, l'apprentissage profond et le raisonnement automatique.

## Technologies clés actuelles
- **Réseaux neuronaux transformers** : Fondement des modèles de langage avancés
- **Apprentissage par renforcement** : Utilisé dans la robotique et les jeux
- **Systèmes multimodaux** : Combinant texte, images et son

## Applications majeures
1. **Santé** : Diagnostic assisté, découverte de médicaments
2. **Finance** : Détection de fraude, trading algorithmique
3. **Transport** : Véhicules autonomes, optimisation logistique

## Enjeux éthiques et sociétaux
- Biais algorithmiques et équité
- Vie privée et surveillance
- Impact sur l'emploi et transformation du travail

## Tendances futures
Les modèles génératifs, l'IA explicable et l'intelligence artificielle générale représentent les principaux axes de développement pour les prochaines années.

Sources: MIT Technology Review (2023), Nature AI Review (2023), Stanford AI Index (2023)
```

## Exemple 6 : Récupération après échec

Cet exemple montre comment l'orchestrateur gère les échecs et apprend à récupérer automatiquement.

### Scénario
L'utilisateur demande de générer un rapport basé sur des données d'une application qui est temporairement indisponible.

### Première tentative (échec)

```
Étape 2: Connexion à l'API de données -> ÉCHEC (Service indisponible)
Message d'erreur: "Cannot connect to data service: Connection timeout"
```

### Analyse du module d'apprentissage

Le module d'apprentissage analyse l'erreur et remarque que des données similaires sont disponibles via une autre source (sauvegarde locale).

### Tentative adaptée (succès)

```
Nouvelle étape 2: Recherche de données en cache local -> SUCCÈS
Nouvelle étape 2.1: Vérification de fraîcheur des données -> SUCCÈS (données de moins de 24h)
Continuation du processus...
```

### Mémorisation pour le futur

L'orchestrateur enregistre cette stratégie de contournement et l'appliquera automatiquement dans des situations similaires.

## Résumé des patterns d'usage

Les exemples ci-dessus illustrent plusieurs patterns d'utilisation courants du système d'orchestration adaptative :

1. **Décomposition de tâches complexes** en sous-tâches gérables
2. **Adaptation aux erreurs** avec des solutions alternatives
3. **Amélioration progressive** des compositions grâce à l'apprentissage
4. **Intégration de systèmes hétérogènes** via des transformateurs de données
5. **Automatisation de processus métier** multi-étapes
6. **Récupération après échec** avec des stratégies de contournement

Ces exemples démontrent comment l'orchestrateur adaptatif peut significativement améliorer l'efficacité et la robustesse des interactions avec Albert Tchapbot, tout en réduisant la charge cognitive sur le modèle LLM sous-jacent. 