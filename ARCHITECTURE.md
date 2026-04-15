# Architecture — HA-MCP

## Vue d'ensemble

HA-MCP est un système d'analyse de candidatures piloté par IA. Le cœur du système est un **pipeline en 2 stages** où Claude (LLM) orchestre dynamiquement des serveurs MCP externes pour enrichir et analyser les données avant de générer un rapport.

```
PDF Offre + PDF CV
        │
        ▼
  ┌─────────────┐
  │  Flask API  │  POST /api/analyze
  └──────┬──────┘
         │
         ▼
  ┌─────────────────────┐
  │   MCPOrchestrator   │  init session + load schemas
  └──────┬──────────────┘
         │
         ▼
  ┌─────────────────────┐
  │   PipelineEngine    │  14 étapes séquentielles
  │                     │
  │  STAGE 1 — Discovery│
  │  1.0 init           │
  │  1.1 ingest PDF     │
  │  1.2 structure LLM  │
  │  1.3 mcp_select     │◄── Claude choisit les MCPs
  │  1.4 mcp_test       │
  │  1.5 resource_disc  │◄── DuckDuckGo web search
  │  1.6 resource_reg   │
  │                     │
  │  STAGE 2 — Analysis │
  │  2.1 resource_consult│◄── Claude NLP sur ressources
  │  2.2 mcp_select     │◄── Claude choisit MCPs analyse
  │  2.3 mcp_test       │
  │  2.4 analysis_exec  │◄── Claude analyse candidature
  │  2.5 combine        │
  │  2.55 grand_meta    │◄── 7 catégories via Claude
  │  2.6 generate       │◄── Rapport Markdown final
  └─────────────────────┘
         │
         ▼
  JSON résultats + Markdown rapport
```

---

## Composants principaux

### 1. Flask Server (`server.py`)

Point d'entrée HTTP. Gère :
- Le rendu du dashboard (`dashboard.html` via Jinja2)
- Les routes REST (`/api/analyze`, `/api/keys`, `/api/mcps`, etc.)
- Le streaming SSE (`/api/events/<session_id>`) pour le suivi live
- Le catalogue statique des MCPs disponibles (`MCP_CATALOG`)
- La persistance des clés API (`api_keys.json`)

### 2. MCPOrchestrator (`mcp_orchestrator/orchestrator.py`)

Coordinateur central. Responsabilités :
- Chargement des schemas JSON via `SchemaRegistry`
- Initialisation de la session (UUID)
- Délégation de la découverte des MCPs à `MCPDiscovery`
- Construction de la `CapabilityMap` (carte des capacités disponibles)
- Création du plan d'exécution via `ExecutionPlanner`
- Validation des données intermédiaires contre les schemas
- Traçabilité complète (log de chaque action)

### 3. PipelineEngine (`pipeline/engine.py`)

Moteur d'exécution séquentiel. Caractéristiques :
- 14 étapes définies sous forme de liste `(step_id, step_name, handler)`
- Chaque étape est une méthode `_step_*` qui lit/écrit dans `PipelineState`
- Émission d'événements SSE à chaque transition (`step_start`, `step_complete`, `step_failed`)
- Arrêt sur première erreur (`break` sur exception)
- Persistance des résultats intermédiaires et finaux dans `/share/ha-mcp/outputs/`

### 4. MCPManager (`mcp_orchestrator/mcp_manager.py`)

Gestionnaire du cycle de vie des MCPs dynamiques :

```
suggest (Claude) → add → test → active
                              └─→ failed → remove
                              └─→ excluded (auth manquante)
```

- `ask_claude_for_mcps()` : Claude lit le job/CV et choisit les MCPs pertinents
- `add_mcp()` : ajoute un MCP en statut `testing` dans `mcp_config.json`
- `test_mcp()` : vérifie la disponibilité via `_probe_tool()` (pattern matching)
- `test_all_pending()` : teste tous les MCPs en attente
- `register_resources()` : stocke les ressources découvertes dans `resources.json`

### 5. LLM Layer (`pipeline/llm.py`)

Appels Claude via l'API Anthropic :
- `structure_job_offer()` → extrait titre, entreprise, compétences requises
- `structure_candidate_cv()` → extrait identité, expériences, compétences
- `analyze_candidacy()` → compare job vs. candidat, score global, alignements/écarts
- `generate_report()` → rapport Markdown complet
- `call_claude()` → fonction bas niveau (système, prompt, modèle, max_tokens)

### 6. Grand Meta Builder (`pipeline/grand_meta_builder.py`)

Construit le **Grand Meta Schema** en 7 catégories via Claude :
1. `candidate_profile` — profil complet du candidat
2. `job_position` — poste et exigences
3. `company_context` — contexte entreprise
4. `skill_alignment` — alignement des compétences
5. `experience_match` — adéquation expériences
6. `cultural_fit` — fit culture/valeurs
7. `match_synthesis` — synthèse globale (score, recommandation, forces, risques, questions entretien)

### 7. Schema Registry (`schema_registry/`)

Système de validation basé sur JSON Schema :
- `SchemaRegistry` charge les fichiers `.json` depuis `/schemas/`
- `SchemaValidator` valide les données métier contre leur schema
- Schemas disponibles : `job`, `candidate`, `analysis`, `generation`, `grand_meta`, `pipeline`, `resource`, `search`, `extraction`, `web`, `mcp_config`, `claude_api`
- Chaque objet métier possède un `meta` block : `session_id`, `object_id`, `schema_version`, `confidence`, `validation_status`, `lineage`, `mcp_sources`

### 8. Dashboard (`templates/dashboard.html`)

SPA (Single Page Application) en HTML/CSS/JS vanilla :

| Onglet | Contenu |
|---|---|
| Overview | Stats globales, capability coverage, infos système |
| Pipeline | Visualisation live des 14 étapes (SSE), log console |
| MCPs | Cartes des MCPs actifs/exclus avec leurs outils |
| Resources | Ressources découvertes (entreprise, skills, marché) |
| API Keys | Formulaire de saisie/suppression des clés API |
| Analyze | Upload PDF + déclenchement analyse |
| Report | Rapport final + Grand Meta (7 catégories, radar chart D3.js) |
| History | Sessions passées + rechargement |

---

## Flux de données complet

```
1. POST /api/analyze (offer.pdf + cv.pdf)
        │
        ├─ 1.1 PyMuPDF → texte brut
        │
        ├─ 1.2 Claude → job_data (JSON) + candidate_data (JSON)
        │
        ├─ 1.3 Claude → sélection MCPs stage 1
        │         └─ [duckduckgo, playwright, sequential-thinking, ...]
        │
        ├─ 1.4 Probe tools → MCPs active/failed
        │
        ├─ 1.5 DuckDuckGo → ressources web
        │         ├─ infos entreprise (company_profile, culture, news)
        │         ├─ références skills (skill_reference)
        │         └─ données marché (job_market_data)
        │
        ├─ 1.6 → resources.json (avec dependency graph)
        │
        ├─ 2.1 Claude NLP → summary + entities par ressource
        │
        ├─ 2.2 Claude → sélection MCPs analyse
        │
        ├─ 2.4 Claude → analysis_data
        │         ├─ alignments[]  (forces)
        │         ├─ gaps[]        (écarts, criticité)
        │         ├─ signals[]     (signaux positifs/négatifs)
        │         ├─ uncertainties[]
        │         ├─ overall_score (0.0–1.0)
        │         └─ recommendation (strong_match / good_match / partial_match / no_match)
        │
        ├─ 2.55 Claude → grand_meta (7 catégories)
        │
        └─ 2.6 Claude → rapport Markdown + generation_obj JSON
                  └─ artifacts: [detailed_report.md, summary.json, grand_meta.json]
```

---

## Persistance

```
/share/ha-mcp/
├── api_keys.json           # Clés API chiffrées (masquées à l'affichage)
├── mcp_config.json         # MCPs sélectionnés dynamiquement
├── resources.json          # Toutes les ressources découvertes
├── inputs/
│   └── <session_id>/
│       ├── offer_*.pdf
│       └── cv_*.pdf
├── outputs/
│   ├── result_<sid>.json       # Résultat complet pipeline
│   ├── generation_<sid>.json   # Artifacts (rapport + données)
│   ├── grand_meta_<sid>.json   # Grand Meta Schema
│   └── report_<sid>.md         # Rapport Markdown standalone
└── logs/
    └── pipeline_<sid>.json     # Event stream SSE
```

---

## MCPs supportés

| ID | Nom | Catégorie | Auth |
|---|---|---|---|
| `local_filesystem` | Filesystem Local | ingestion | Non |
| `local_pdf` | PDF Extractor | ingestion | Non |
| `local_reasoning` | Raisonnement Local | raisonnement | Non |
| `local_validation` | Schema Validator | validation | Non |
| `local_generation` | Générateur Local | génération | Non |
| `duckduckgo` | DuckDuckGo Search | enrichissement | Non |
| `sequential-thinking` | Sequential Thinking | raisonnement | Non |
| `anthropic_claude` | Claude API | raisonnement | `ANTHROPIC_API_KEY` |
| `openai_gpt` | OpenAI GPT | raisonnement | `OPENAI_API_KEY` |
| `google_gemini` | Google Gemini | raisonnement | `GOOGLE_API_KEY` |
| `mistral_ai` | Mistral AI | raisonnement | `MISTRAL_API_KEY` |
| `huggingface` | Hugging Face | structuration | `HF_API_KEY` |
| `notion_api` | Notion | enrichissement | `NOTION_API_KEY` |
| `google_drive` | Google Drive | ingestion | `GOOGLE_DRIVE_TOKEN` |

---

## Déploiement (Home Assistant Add-on)

```
Dockerfile
  └─ Base: python:3.12-slim
  └─ pip install -r requirements.txt
  └─ COPY app/ schemas/ config/
  └─ EXPOSE 8099
  └─ CMD python -m app

rootfs/etc/services.d/ha-mcp/run   → s6-overlay service runner
```

Le serveur écoute sur `0.0.0.0:8099`. L'ingress HA proxifie le trafic via `HA_MCP_INGRESS_ENTRY`.
