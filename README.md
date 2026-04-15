# HA-MCP

**HA-MCP** est un add-on Home Assistant qui analyse automatiquement des candidatures (offre d'emploi + CV) via un pipeline IA en deux étapes, orchestré dynamiquement par des serveurs MCP (Model Context Protocol).

Il extrait, structure, enrichit et analyse les documents PDF, puis génère un rapport de recommandation complet.

---

## Fonctionnalités

- Upload d'un **PDF offre d'emploi** et d'un **PDF CV**
- Pipeline en **2 stages**, 14 étapes, entièrement piloté par Claude
- **Sélection dynamique des MCPs** : Claude choisit lui-même quels outils activer selon le contexte
- Recherche web automatique (DuckDuckGo) : infos entreprise, compétences, données marché
- Génération d'un **Grand Meta Schema** (7 catégories d'analyse)
- Rapport final en Markdown + données structurées JSON
- Dashboard web live avec SSE (Server-Sent Events) pour suivre la progression
- Gestion des clés API depuis le dashboard
- Historique des sessions

---

## Stack technique

| Composant | Technologie |
|---|---|
| Serveur web | Flask 3.x |
| LLM principal | Anthropic Claude (Sonnet) |
| Extraction PDF | PyMuPDF (fitz) / pdfplumber (fallback) |
| Recherche web | DuckDuckGo Search (ddgs) |
| Dashboard | HTML/CSS/JS vanilla + D3.js |
| Déploiement | Docker (Home Assistant Add-on) |
| Storage | Fichiers JSON sur `/share/ha-mcp` |

---

## Installation (Home Assistant)

1. Ajouter le dépôt dans Home Assistant → Add-on Store → Repositories :
   ```
   https://github.com/alexisdeudon01/HA-MCP
   ```
2. Installer l'add-on **HA-MCP**
3. Configurer les clés API dans le dashboard (`API Keys`)
4. Démarrer l'add-on — le dashboard est accessible via Ingress

---

## Utilisation

1. Ouvrir le dashboard → onglet **Analyze**
2. Uploader l'offre d'emploi (PDF) et le CV (PDF)
3. Cliquer **Analyze** — le pipeline se lance
4. Suivre la progression en temps réel dans l'onglet **Pipeline**
5. Consulter le rapport final dans l'onglet **Report**
6. Retrouver les sessions passées dans **History**

---

## Variables d'environnement

| Variable | Défaut | Description |
|---|---|---|
| `HA_MCP_LOG_LEVEL` | `info` | Niveau de log (debug/info/warning/error) |
| `HA_MCP_STORAGE_PATH` | `/share/ha-mcp` | Dossier de stockage persistant |
| `HA_MCP_INGRESS_ENTRY` | `` | Préfixe URL pour l'ingress HA |

---

## Clés API supportées

| Clé | Service | Usage |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude | Structuration, analyse, NLP, génération — **requis** |
| `OPENAI_API_KEY` | GPT | LLM alternatif |
| `GOOGLE_API_KEY` | Gemini | LLM alternatif |
| `MISTRAL_API_KEY` | Mistral | LLM européen alternatif |
| `HF_API_KEY` | Hugging Face | NER / classification |
| `NOTION_API_KEY` | Notion | Stockage des analyses |
| `GOOGLE_DRIVE_TOKEN` | Google Drive | Ingestion PDFs depuis Drive |

---

## Structure du projet

```
ha-mcp/
├── app/
│   ├── server.py                  # Flask app + routes API
│   ├── pipeline/
│   │   ├── engine.py              # Pipeline 2 stages, 14 étapes
│   │   ├── llm.py                 # Appels Claude (structure, analyse, rapport)
│   │   ├── enrichment.py          # Recherche web DuckDuckGo
│   │   ├── grand_meta_builder.py  # Construction du Grand Meta Schema
│   │   └── state.py               # State machine de la session
│   ├── mcp_orchestrator/
│   │   ├── orchestrator.py        # Coordinateur central MCPs
│   │   ├── mcp_manager.py         # Lifecycle MCPs (add/test/remove)
│   │   ├── discovery.py           # Découverte et classification MCPs
│   │   ├── capability.py          # Carte des capacités disponibles
│   │   └── planner.py             # Planificateur d'exécution
│   ├── schema_registry/
│   │   ├── registry.py            # Chargement des schemas JSON
│   │   └── validator.py           # Validation des données
│   ├── templates/
│   │   └── dashboard.html         # Dashboard web complet
│   └── interface/
│       ├── ingestion.py
│       └── results.py
├── schemas/                       # Schemas JSON par objet métier
├── config/
│   ├── mcp_discovery.json         # Config découverte MCP
│   └── runtime.json               # Config runtime
├── Dockerfile
├── build.yaml
├── config.yaml
└── requirements.txt
```

---

## API REST

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Dashboard web |
| `GET` | `/api/health` | Healthcheck |
| `POST` | `/api/analyze` | Lancer une analyse (multipart: offer_pdf + cv_pdf) |
| `GET` | `/api/events/<session_id>` | SSE — suivi live du pipeline |
| `GET` | `/api/results/<session_id>` | Résultats d'une session |
| `GET` | `/api/sessions` | Liste des sessions passées |
| `GET` | `/api/schemas` | Schemas chargés |
| `GET` | `/api/mcps` | Catalogue MCPs + statuts |
| `GET` | `/api/mcps/dynamic` | MCPs sélectionnés dynamiquement |
| `GET/POST` | `/api/keys` | Lecture/écriture clés API |
| `DELETE` | `/api/keys/<key_name>` | Suppression d'une clé |
| `GET` | `/api/resources` | Ressources découvertes |
