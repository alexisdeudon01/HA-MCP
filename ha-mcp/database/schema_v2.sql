-- ============================================================
-- HA-MCP Database v2 — Schéma modulaire
-- ============================================================
-- Tables :
--   capability    → catalogue des capacités pipeline
--   mcp           → registre des serveurs MCP
--   transport     → comment se connecter à chaque MCP
--   tool          → outils exposés par chaque MCP
--   tool_parameter→ paramètres de chaque outil
--   mcp_capability→ liaison MCP ↔ capability
--   tool_capability→ liaison tool ↔ capability
-- ============================================================

PRAGMA foreign_keys = ON;

-- ────────────────────────────────────────────────────────────
-- 1. CAPABILITY — catalogue des capacités pipeline
-- ────────────────────────────────────────────────────────────
CREATE TABLE capability (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,   -- web_search, raisonnement, ...
    description     TEXT    NOT NULL DEFAULT '',
    pipeline_stages TEXT    NOT NULL DEFAULT '[]'  -- JSON array ex: ["1.5","2.1"]
);

INSERT INTO capability (name, description, pipeline_stages) VALUES
('ingestion',      'Lecture et extraction de données (PDF, fichiers, Drive)',         '["1.1"]'),
('structuration',  'Normalisation et structuration des données brutes',               '["1.2"]'),
('enrichissement', 'Enrichissement par données externes (APIs, bases)',               '["1.5","2.1"]'),
('raisonnement',   'Analyse, comparaison et raisonnement (LLMs, sequential)',        '["1.3","2.2","2.4"]'),
('validation',     'Validation de schemas et conformité des données',                 '["1.4","2.3"]'),
('generation',     'Génération de rapports, code et artefacts',                      '["2.55","2.6"]'),
('nlp',            'Traitement du langage naturel (NER, sentiment, résumé)',         '["2.1"]'),
('web_search',     'Recherche web publique',                                          '["1.5"]'),
('web_scrape',     'Navigation et scraping de pages web dynamiques',                 '["1.5","2.1"]'),
('file_read',      'Lecture de fichiers locaux',                                      '["1.1","1.6"]'),
('file_write',     'Écriture de fichiers locaux',                                     '["1.6","2.6"]'),
('storage',        'Stockage et récupération de données persistantes',               '["2.6"]');

-- ────────────────────────────────────────────────────────────
-- 2. MCP — registre des serveurs
-- ────────────────────────────────────────────────────────────
CREATE TABLE mcp (
    mcp_id            TEXT    PRIMARY KEY,
    name              TEXT    NOT NULL,
    version           TEXT    NOT NULL DEFAULT '1.0.0',
    description       TEXT    NOT NULL DEFAULT '',

    -- Plug & Play (logique is_plug_and_play)
    plug_and_play     INTEGER NOT NULL DEFAULT 0,  -- 1 = aucune clé requise

    -- Auth (détecté après transport)
    requires_auth     INTEGER NOT NULL DEFAULT 0,
    auth_type         TEXT    NOT NULL DEFAULT 'none'
                      CHECK (auth_type IN ('none','api_key','oauth','bearer_token','basic')),
    auth_key_name     TEXT,                         -- ex: ANTHROPIC_API_KEY

    -- Origine
    source            TEXT    NOT NULL DEFAULT 'discovered'
                      CHECK (source IN ('local','anthropic_registry','community','discovered')),
    registry_category TEXT,                         -- catégorie Anthropic (productivity, code...)
    discovered_from   TEXT,                         -- mcp_id qui a référencé ce MCP
    discovered_at     TEXT,

    -- Méta
    homepage_url      TEXT,
    docs_url          TEXT,
    rpm_limit         INTEGER,                      -- rate limit req/min
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ────────────────────────────────────────────────────────────
-- 3. TRANSPORT — comment se connecter à un MCP
-- ────────────────────────────────────────────────────────────
CREATE TABLE transport (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mcp_id      TEXT    NOT NULL,

    -- Type de transport
    type        TEXT    NOT NULL
                CHECK (type IN ('stdio','streamable-http','sse')),

    -- stdio : exécution locale
    executor    TEXT    CHECK (executor IN ('npx','uvx','node','python','docker', NULL)),
    command     TEXT,                    -- ex: npx
    args_json   TEXT    DEFAULT '[]',    -- JSON array ex: ["-y","duckduckgo-mcp-server"]

    -- HTTP distant
    url         TEXT,                    -- ex: https://mcp.blockscout.com/mcp

    -- Statut du dernier probe
    last_probe_at     TEXT,
    last_probe_ok     INTEGER DEFAULT 0,
    last_probe_error  TEXT,

    FOREIGN KEY (mcp_id) REFERENCES mcp(mcp_id) ON DELETE CASCADE,
    UNIQUE (mcp_id, type)
);

-- ────────────────────────────────────────────────────────────
-- 4. TOOL — outils exposés par chaque MCP
-- ────────────────────────────────────────────────────────────
CREATE TABLE tool (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mcp_id      TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    timeout_ms  INTEGER NOT NULL DEFAULT 10000,

    FOREIGN KEY (mcp_id) REFERENCES mcp(mcp_id) ON DELETE CASCADE,
    UNIQUE (mcp_id, name)
);

-- ────────────────────────────────────────────────────────────
-- 5. TOOL_PARAMETER — paramètres d'entrée de chaque outil
-- ────────────────────────────────────────────────────────────
CREATE TABLE tool_parameter (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id       INTEGER NOT NULL,
    name          TEXT    NOT NULL,
    type          TEXT    NOT NULL
                  CHECK (type IN ('string','integer','number','boolean','array','object')),
    description   TEXT    NOT NULL DEFAULT '',
    required      INTEGER NOT NULL DEFAULT 0,
    default_value TEXT,             -- JSON string
    enum_values   TEXT,             -- JSON array
    min_value     REAL,
    max_value     REAL,
    max_length    INTEGER,
    position      INTEGER NOT NULL DEFAULT 0,

    FOREIGN KEY (tool_id) REFERENCES tool(id) ON DELETE CASCADE
);

-- ────────────────────────────────────────────────────────────
-- 6. MCP_CAPABILITY — liaison MCP ↔ capability
-- ────────────────────────────────────────────────────────────
CREATE TABLE mcp_capability (
    mcp_id  TEXT    NOT NULL,
    cap_id  INTEGER NOT NULL,
    PRIMARY KEY (mcp_id, cap_id),
    FOREIGN KEY (mcp_id) REFERENCES mcp(mcp_id)      ON DELETE CASCADE,
    FOREIGN KEY (cap_id) REFERENCES capability(id)    ON DELETE CASCADE
);

-- ────────────────────────────────────────────────────────────
-- 7. TOOL_CAPABILITY — liaison tool ↔ capability
-- ────────────────────────────────────────────────────────────
CREATE TABLE tool_capability (
    tool_id INTEGER NOT NULL,
    cap_id  INTEGER NOT NULL,
    PRIMARY KEY (tool_id, cap_id),
    FOREIGN KEY (tool_id) REFERENCES tool(id)         ON DELETE CASCADE,
    FOREIGN KEY (cap_id)  REFERENCES capability(id)   ON DELETE CASCADE
);

-- ────────────────────────────────────────────────────────────
-- INDEXES
-- ────────────────────────────────────────────────────────────
CREATE INDEX idx_transport_mcp_id   ON transport(mcp_id);
CREATE INDEX idx_transport_type     ON transport(type);
CREATE INDEX idx_tool_mcp_id        ON tool(mcp_id);
CREATE INDEX idx_tool_param_tool_id ON tool_parameter(tool_id);
CREATE INDEX idx_mcp_cap_mcp        ON mcp_capability(mcp_id);
CREATE INDEX idx_mcp_cap_cap        ON mcp_capability(cap_id);
CREATE INDEX idx_tool_cap_tool      ON tool_capability(tool_id);
CREATE INDEX idx_tool_cap_cap       ON tool_capability(cap_id);
CREATE INDEX idx_mcp_plug_play      ON mcp(plug_and_play);
CREATE INDEX idx_mcp_requires_auth  ON mcp(requires_auth);
