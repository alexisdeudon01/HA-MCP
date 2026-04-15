-- ============================================================
-- Migration 001 — Anthropic MCP Registry
-- Source : https://api.anthropic.com/mcp-registry/v0/servers
-- Date   : 2026-04-15
-- ============================================================

-- ---- Ajout colonnes manquantes sur mcp ----
ALTER TABLE mcp ADD COLUMN mcp_endpoint_url  TEXT;       -- URL du serveur MCP distant
ALTER TABLE mcp ADD COLUMN registry_category TEXT;       -- catégorie Anthropic (productivity, code, ...)
ALTER TABLE mcp ADD COLUMN transport         TEXT DEFAULT 'stdio' CHECK (transport IN ('stdio','sse','http'));
ALTER TABLE mcp ADD COLUMN source            TEXT DEFAULT 'local' CHECK (source IN ('local','anthropic_registry','community'));

-- Mise à jour des MCPs existants
UPDATE mcp SET source = 'local' WHERE source IS NULL;

-- ============================================================
-- INSERT MCPs depuis le registre Anthropic
-- ============================================================

INSERT OR IGNORE INTO mcp
  (mcp_id, name, version, description, category, is_local, is_free, homepage_url, docs_url, mcp_endpoint_url, registry_category, transport, source)
VALUES

('ticket-tailor',   'Ticket Tailor',               '1.0.0',
 'Event ticketing platform — manage tickets, orders, discounts, products',
 'enrichissement', 0, 0,
 'https://www.tickettailor.com/',
 'https://help.tickettailor.com/en/articles/11892797-how-to-connect-ticket-tailor-to-your-favourite-ai-agent',
 'https://mcp.tickettailor.ai/mcp',
 'financial-services', 'http', 'anthropic_registry'),

('linear',          'Linear',                       '1.0.0',
 'Manage issues, projects, and team workflows in Linear with natural language',
 'enrichissement', 0, 0,
 'https://linear.app',
 'https://linear.app/docs/mcp',
 'https://mcp.linear.app/mcp',
 'productivity', 'http', 'anthropic_registry'),

('hugging-face',    'Hugging Face Hub',             '1.0.0',
 'Access Hugging Face Hub — models, datasets, papers, Spaces, Gradio apps',
 'raisonnement', 0, 0,
 'https://huggingface.co/',
 'https://huggingface.co/settings/mcp',
 'https://huggingface.co/mcp',
 'code', 'http', 'anthropic_registry'),

('amplitude',       'Amplitude',                    '1.0.0',
 'Search and get insights on Amplitude behavior analytics data',
 'enrichissement', 0, 0,
 'https://amplitude.com/',
 'https://amplitude.com/docs/analytics/amplitude-mcp',
 'https://mcp.amplitude.com/mcp',
 'sales-and-marketing', 'http', 'anthropic_registry'),

('atlassian',       'Atlassian Rovo',               '1.0.0',
 'Permission-aware access to Jira and Confluence from Claude',
 'enrichissement', 0, 0,
 'https://atlassian.com',
 'https://community.atlassian.com/forums/Atlassian-Platform-articles/Using-the-Atlassian-Remote-MCP-Server-beta/ba-p/3005104',
 'https://mcp.atlassian.com/v1/mcp',
 'productivity', 'http', 'anthropic_registry'),

('blockscout',      'Blockscout',                   '1.0.0',
 'Multichain blockchain data — balances, tokens, NFTs, transactions',
 'enrichissement', 0, 1,
 'https://www.blockscout.com/',
 'https://github.com/blockscout/mcp-server',
 'https://mcp.blockscout.com/mcp',
 'financial-services', 'http', 'anthropic_registry'),

('close',           'Close CRM',                    '1.0.0',
 'Connect to Close CRM — access and act on sales data, leads, opportunities',
 'enrichissement', 0, 0,
 'https://www.close.com/',
 'https://help.close.com/v1/docs/en/mcp-server',
 'https://mcp.close.com/mcp',
 'sales-and-marketing', 'http', 'anthropic_registry'),

('cloudflare',      'Cloudflare Developer Platform','1.0.0',
 'Build with compute, storage, AI on Cloudflare Workers — KV, R2, D1, Workers',
 'generation', 0, 0,
 'https://cloudflare.com',
 'https://www.support.cloudflare.com/',
 'https://bindings.mcp.cloudflare.com/mcp',
 'code', 'http', 'anthropic_registry'),

('egnyte',          'Egnyte',                       '1.0.0',
 'Search, retrieve and analyze content stored in Egnyte domains',
 'ingestion', 0, 0,
 'https://www.egnyte.com',
 'https://developers.egnyte.com/docs/Remote_MCP_Server',
 'https://mcp-server.egnyte.com/mcp',
 'financial-services', 'http', 'anthropic_registry'),

('figma',           'Figma',                        '1.0.0',
 'Generate diagrams and higher-quality code from Figma design context',
 'generation', 0, 0,
 'https://www.figma.com',
 'https://help.figma.com/hc/en-us/articles/32132100833559',
 'https://mcp.figma.com/mcp',
 'design', 'http', 'anthropic_registry'),

('guru',            'Guru',                         '1.0.0',
 'Search and interact with company trusted knowledge layer',
 'enrichissement', 0, 0,
 'https://www.getguru.com',
 'https://help.getguru.com/docs/connecting-gurus-mcp-server',
 'https://mcp.api.getguru.com/mcp',
 'productivity', 'http', 'anthropic_registry'),

('jotform',         'Jotform',                      '1.0.0',
 'Create and edit forms, access and analyze form submissions',
 'enrichissement', 0, 0,
 'https://www.jotform.com/',
 'https://www.jotform.com/developers/mcp/',
 'https://mcp.jotform.com/mcp-app',
 'productivity', 'http', 'anthropic_registry'),

('mermaid-chart',   'Mermaid Chart',                '1.0.0',
 'Validates Mermaid syntax and renders diagrams as interactive SVG',
 'generation', 0, 1,
 'https://www.mermaidchart.com',
 'https://docs.mermaidchart.com/ai/mcp-server',
 'https://chatgpt.mermaid.ai/anthropic/mcp',
 'design', 'http', 'anthropic_registry'),

('monday',          'monday.com',                   '1.0.0',
 'Manage projects, boards, items and workflows in monday.com',
 'enrichissement', 0, 0,
 'https://monday.com/',
 'https://developer.monday.com/apps/docs/mondaycom-mcp-integration',
 'https://mcp.monday.com/mcp',
 'productivity', 'http', 'anthropic_registry'),

('notion-registry', 'Notion (Registry)',            '1.0.0',
 'Create, edit, search and organize Notion content directly from Claude',
 'enrichissement', 0, 0,
 'https://notion.com',
 'https://developers.notion.com/docs/mcp',
 'https://mcp.notion.com/mcp',
 'productivity', 'http', 'anthropic_registry'),

('paypal',          'PayPal',                       '1.0.0',
 'Access PayPal payments platform — transactions, invoices, subscriptions',
 'enrichissement', 0, 0,
 'https://paypal.com',
 'https://mcp.paypal.com/',
 'https://mcp.paypal.com/mcp',
 'financial-services', 'http', 'anthropic_registry'),

('stripe',          'Stripe',                       '1.0.0',
 'Payment processing and financial infrastructure via Stripe API',
 'enrichissement', 0, 0,
 'https://stripe.com',
 'https://docs.stripe.com/mcp',
 'https://mcp.stripe.com',
 'financial-services', 'http', 'anthropic_registry'),

('supabase',        'Supabase',                     '1.0.0',
 'Manage databases, authentication, edge functions and storage on Supabase',
 'generation', 0, 0,
 'https://supabase.com/',
 'https://supabase.com/docs/guides/getting-started/mcp',
 'https://mcp.supabase.com/mcp',
 'code', 'http', 'anthropic_registry'),

('vercel',          'Vercel',                       '1.0.0',
 'Analyze, debug and manage Vercel projects and deployments',
 'generation', 0, 0,
 'https://vercel.com/',
 'https://vercel.com/docs/mcp/vercel-mcp',
 'https://mcp.vercel.com/',
 'code', 'http', 'anthropic_registry'),

('wix',             'Wix',                          '1.0.0',
 'Manage and build sites and apps on Wix platform',
 'generation', 0, 0,
 'https://www.wix.com',
 'https://dev.wix.com/docs/sdk/articles/use-the-wix-mcp/about-the-wix-mcp',
 'https://mcp.wix.com/mcp',
 'productivity', 'http', 'anthropic_registry'),

('coupler-io',      'Coupler.io',                   '1.0.0',
 'Access business data from hundreds of sources for analysis',
 'enrichissement', 0, 0,
 'https://coupler.io',
 'https://help.coupler.io/article/592-coupler-local-mcp-server',
 'https://mcp.coupler.io/mcp/',
 'sales-and-marketing', 'http', 'anthropic_registry'),

('dice',            'Dice',                         '1.0.0',
 'Find active tech jobs across disciplines from AI/ML to cybersecurity',
 'enrichissement', 0, 1,
 'https://www.dice.com/',
 'https://www.dice.com/about/mcp',
 'https://mcp.dice.com/mcp',
 'productivity', 'http', 'anthropic_registry');

-- ============================================================
-- INSERT tools depuis le registre Anthropic
-- ============================================================

-- ticket-tailor (65 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('ticket-tailor','bundle_create',                  'Create ticket bundle',              'enrichissement', 10000),
('ticket-tailor','bundle_delete',                  'Delete ticket bundle',              'enrichissement', 10000),
('ticket-tailor','bundle_update',                  'Update ticket bundle',              'enrichissement', 10000),
('ticket-tailor','check_in_create',                'Create check-in',                   'enrichissement', 10000),
('ticket-tailor','check_ins_get',                  'Get check-ins',                     'enrichissement', 10000),
('ticket-tailor','discount_create',                'Create discount code',              'enrichissement', 10000),
('ticket-tailor','discount_delete',                'Delete discount code',              'enrichissement', 10000),
('ticket-tailor','discount_update',                'Update discount code',              'enrichissement', 10000),
('ticket-tailor','discounts_get',                  'List discounts',                    'enrichissement', 10000),
('ticket-tailor','event_by_id_get',                'Get event by ID',                   'enrichissement', 10000),
('ticket-tailor','event_series_create',            'Create event series',               'enrichissement', 10000),
('ticket-tailor','event_series_get',               'List event series',                 'enrichissement', 10000),
('ticket-tailor','events_get',                     'List events',                       'enrichissement', 10000),
('ticket-tailor','issued_ticket_create',           'Issue a ticket',                    'enrichissement', 10000),
('ticket-tailor','issued_tickets_get',             'List issued tickets',               'enrichissement', 10000),
('ticket-tailor','order_by_id_get',                'Get order by ID',                   'enrichissement', 10000),
('ticket-tailor','orders_get',                     'List orders',                       'enrichissement', 10000),
('ticket-tailor','overview_get',                   'Get account overview',              'enrichissement', 10000),
('ticket-tailor','product_create',                 'Create product',                    'enrichissement', 10000),
('ticket-tailor','products_get',                   'List products',                     'enrichissement', 10000),
('ticket-tailor','store_list',                     'List stores',                       'enrichissement', 10000);

-- linear (21 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('linear','list_issues',       'List issues in Linear',                'enrichissement', 10000),
('linear','get_issue',         'Get a specific Linear issue',          'enrichissement', 10000),
('linear','create_issue',      'Create a new Linear issue',            'enrichissement', 10000),
('linear','update_issue',      'Update a Linear issue',                'enrichissement', 10000),
('linear','list_projects',     'List Linear projects',                 'enrichissement', 10000),
('linear','get_project',       'Get a specific Linear project',        'enrichissement', 10000),
('linear','create_project',    'Create a new Linear project',          'enrichissement', 10000),
('linear','update_project',    'Update a Linear project',              'enrichissement', 10000),
('linear','list_teams',        'List Linear teams',                    'enrichissement', 10000),
('linear','get_team',          'Get a specific Linear team',           'enrichissement', 10000),
('linear','list_users',        'List Linear users',                    'enrichissement', 10000),
('linear','create_comment',    'Create a comment on a Linear issue',   'enrichissement', 10000),
('linear','list_comments',     'List comments on a Linear issue',      'enrichissement', 10000),
('linear','list_cycles',       'List Linear cycles/sprints',           'enrichissement', 10000),
('linear','search_documentation','Search Linear documentation',        'enrichissement', 10000);

-- hugging-face (9 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('hugging-face','hf_whoami',       'Get authenticated HuggingFace user info',    'raisonnement', 10000),
('hugging-face','space_search',    'Search Hugging Face Spaces',                 'web_search',   10000),
('hugging-face','model_search',    'Search Hugging Face models',                 'web_search',   10000),
('hugging-face','model_details',   'Get details about a specific HF model',      'raisonnement', 10000),
('hugging-face','paper_search',    'Search research papers on HF',               'web_search',   10000),
('hugging-face','dataset_search',  'Search Hugging Face datasets',               'web_search',   10000),
('hugging-face','dataset_details', 'Get details about a specific HF dataset',    'raisonnement', 10000),
('hugging-face','hf_doc_search',   'Search Hugging Face documentation',          'web_search',   10000);

-- amplitude (15 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('amplitude','get_charts',          'Get Amplitude charts',                    'enrichissement', 10000),
('amplitude','get_dashboard',       'Get an Amplitude dashboard',              'enrichissement', 10000),
('amplitude','query_dataset',       'Query an Amplitude dataset',              'enrichissement', 15000),
('amplitude','query_charts',        'Query Amplitude charts',                  'enrichissement', 15000),
('amplitude','query_metric',        'Query a specific Amplitude metric',       'enrichissement', 15000),
('amplitude','search',              'Search across Amplitude',                 'web_search',     10000),
('amplitude','get_events',          'Get Amplitude events',                    'enrichissement', 10000),
('amplitude','get_event_properties','Get event properties',                    'enrichissement', 10000),
('amplitude','get_user_properties', 'Get user properties',                     'enrichissement', 10000),
('amplitude','get_flags',           'Get feature flags',                       'enrichissement', 10000);

-- atlassian (28 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('atlassian','getConfluencePage',           'Get a Confluence page',              'enrichissement', 10000),
('atlassian','createConfluencePage',        'Create a Confluence page',           'generation',     10000),
('atlassian','updateConfluencePage',        'Update a Confluence page',           'generation',     10000),
('atlassian','searchConfluenceUsingCql',    'Search Confluence with CQL',         'web_search',     10000),
('atlassian','getJiraIssue',               'Get a Jira issue',                   'enrichissement', 10000),
('atlassian','createJiraIssue',            'Create a Jira issue',                'generation',     10000),
('atlassian','editJiraIssue',              'Edit a Jira issue',                  'generation',     10000),
('atlassian','transitionJiraIssue',        'Transition a Jira issue status',     'enrichissement', 10000),
('atlassian','searchJiraIssuesUsingJql',   'Search Jira issues with JQL',        'web_search',     10000),
('atlassian','addCommentToJiraIssue',      'Add comment to Jira issue',          'generation',     10000),
('atlassian','getVisibleJiraProjects',     'List visible Jira projects',         'enrichissement', 10000),
('atlassian','atlassianUserInfo',          'Get current Atlassian user info',    'enrichissement', 10000);

-- blockscout (14 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('blockscout','get_chains_list',             'List supported blockchains',              'enrichissement', 10000),
('blockscout','get_address_info',            'Get address info on blockchain',          'enrichissement', 10000),
('blockscout','get_tokens_by_address',       'Get tokens held by address',              'enrichissement', 10000),
('blockscout','get_transactions_by_address', 'Get transactions for address',            'enrichissement', 10000),
('blockscout','transaction_summary',         'Summarize a blockchain transaction',      'enrichissement', 10000),
('blockscout','nft_tokens_by_address',       'Get NFTs owned by address',               'enrichissement', 10000),
('blockscout','get_transaction_info',        'Get info about a transaction',            'enrichissement', 10000),
('blockscout','get_contract_abi',            'Get ABI of a smart contract',             'enrichissement', 10000),
('blockscout','read_contract',               'Read from a smart contract',              'enrichissement', 10000),
('blockscout','get_latest_block',            'Get latest block info',                   'enrichissement', 10000);

-- figma (9 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('figma','get_design_context',      'Get Figma design context for a file',    'ingestion',   15000),
('figma','get_screenshot',          'Get screenshot of a Figma frame',        'ingestion',   15000),
('figma','get_metadata',            'Get Figma file metadata',                'ingestion',   10000),
('figma','generate_diagram',        'Generate diagram from Figma design',     'generation',  15000),
('figma','create_design_system_rules','Create design system rules from Figma','generation',  15000),
('figma','get_variable_defs',       'Get Figma variable definitions',         'enrichissement',10000),
('figma','get_code_connect_map',    'Get Figma code connect mapping',         'enrichissement',10000),
('figma','whoami',                  'Get current Figma user info',            'enrichissement',10000);

-- mermaid-chart (1 tool)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('mermaid-chart','validate_and_render_mermaid_diagram',
 'Validate Mermaid syntax and render as interactive SVG', 'generation', 15000);

-- stripe (21 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('stripe','search_documentation',    'Search Stripe API documentation',      'web_search',     10000),
('stripe','get_stripe_account_info', 'Get Stripe account information',       'enrichissement', 10000),
('stripe','create_customer',         'Create a Stripe customer',             'generation',     10000),
('stripe','list_customers',          'List Stripe customers',                'enrichissement', 10000),
('stripe','create_product',          'Create a Stripe product',              'generation',     10000),
('stripe','list_products',           'List Stripe products',                 'enrichissement', 10000),
('stripe','create_price',            'Create a Stripe price',                'generation',     10000),
('stripe','create_payment_link',     'Create a Stripe payment link',         'generation',     10000),
('stripe','create_invoice',          'Create a Stripe invoice',              'generation',     10000),
('stripe','list_invoices',           'List Stripe invoices',                 'enrichissement', 10000),
('stripe','retrieve_balance',        'Retrieve Stripe account balance',      'enrichissement', 10000),
('stripe','create_refund',           'Create a refund in Stripe',            'generation',     10000),
('stripe','list_payment_intents',    'List Stripe payment intents',          'enrichissement', 10000),
('stripe','list_subscriptions',      'List Stripe subscriptions',            'enrichissement', 10000),
('stripe','cancel_subscription',     'Cancel a Stripe subscription',         'enrichissement', 10000);

-- supabase (27 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('supabase','list_projects',          'List Supabase projects',              'enrichissement', 10000),
('supabase','get_project',            'Get a specific Supabase project',     'enrichissement', 10000),
('supabase','create_project',         'Create a new Supabase project',       'generation',     30000),
('supabase','pause_project',          'Pause a Supabase project',            'enrichissement', 10000),
('supabase','list_tables',            'List tables in a Supabase database',  'enrichissement', 10000),
('supabase','execute_sql',            'Execute SQL on Supabase database',    'enrichissement', 15000),
('supabase','apply_migration',        'Apply a database migration',          'generation',     15000),
('supabase','get_logs',               'Get Supabase project logs',           'enrichissement', 10000),
('supabase','generate_typescript_types','Generate TypeScript types from schema','generation', 10000),
('supabase','search_docs',            'Search Supabase documentation',       'web_search',     10000),
('supabase','list_storage_buckets',   'List storage buckets',                'enrichissement', 10000),
('supabase','deploy_edge_function',   'Deploy an edge function',             'generation',     30000),
('supabase','create_branch',          'Create a database branch',            'generation',     15000),
('supabase','list_organizations',     'List Supabase organizations',         'enrichissement', 10000);

-- vercel (7 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('vercel','search_vercel_documentation','Search Vercel documentation',      'web_search',     10000),
('vercel','list_projects',            'List Vercel projects',                'enrichissement', 10000),
('vercel','get_project',              'Get a specific Vercel project',       'enrichissement', 10000),
('vercel','list_deployments',         'List Vercel deployments',             'enrichissement', 10000),
('vercel','get_deployment',           'Get a specific Vercel deployment',    'enrichissement', 10000),
('vercel','get_deployment_events',    'Get deployment event logs',           'enrichissement', 10000),
('vercel','list_teams',               'List Vercel teams',                   'enrichissement', 10000);

-- cloudflare (21 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('cloudflare','accounts_list',         'List Cloudflare accounts',           'enrichissement', 10000),
('cloudflare','workers_list',          'List Cloudflare Workers',            'enrichissement', 10000),
('cloudflare','workers_get_worker',    'Get a specific Worker',              'enrichissement', 10000),
('cloudflare','kv_namespaces_list',    'List KV namespaces',                 'enrichissement', 10000),
('cloudflare','kv_namespace_create',   'Create a KV namespace',              'generation',     10000),
('cloudflare','r2_buckets_list',       'List R2 storage buckets',            'enrichissement', 10000),
('cloudflare','r2_bucket_create',      'Create an R2 bucket',                'generation',     10000),
('cloudflare','d1_databases_list',     'List D1 databases',                  'enrichissement', 10000),
('cloudflare','d1_database_create',    'Create a D1 database',               'generation',     10000),
('cloudflare','d1_database_query',     'Query a D1 database',                'enrichissement', 15000),
('cloudflare','hyperdrive_configs_list','List Hyperdrive configs',            'enrichissement', 10000);

-- dice (1 tool)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('dice','search_jobs', 'Search active tech jobs on Dice.com', 'web_search', 10000);

-- notion-registry (13 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('notion-registry','search',         'Search Notion workspace',            'web_search',     10000),
('notion-registry','fetch',          'Fetch a Notion page or block',       'ingestion',      10000),
('notion-registry','create-pages',   'Create new Notion pages',            'generation',     10000),
('notion-registry','update-page',    'Update a Notion page',               'generation',     10000),
('notion-registry','move-pages',     'Move Notion pages',                  'enrichissement', 10000),
('notion-registry','duplicate-page', 'Duplicate a Notion page',            'generation',     10000),
('notion-registry','create-database','Create a Notion database',           'generation',     10000),
('notion-registry','create-comment', 'Create a comment in Notion',         'generation',     10000),
('notion-registry','get-comments',   'Get comments from Notion',           'enrichissement', 10000),
('notion-registry','get-users',      'Get Notion workspace users',         'enrichissement', 10000);

-- monday (16 tools)
INSERT INTO tool (mcp_id, name, description, capability, timeout_ms) VALUES
('monday','get_board_items_by_name', 'Get board items by name',            'enrichissement', 10000),
('monday','create_item',             'Create an item on a board',          'generation',     10000),
('monday','delete_item',             'Delete an item from a board',        'enrichissement', 10000),
('monday','create_update',           'Create an update/comment on item',   'generation',     10000),
('monday','get_board_schema',        'Get board schema/structure',         'enrichissement', 10000),
('monday','change_item_column_values','Update item column values',         'enrichissement', 10000),
('monday','create_board',            'Create a new board',                 'generation',     10000),
('monday','create_column',           'Create a column on a board',         'generation',     10000),
('monday','all_monday_api',          'Generic monday.com API call',        'enrichissement', 15000),
('monday','workspace_info',          'Get monday.com workspace info',      'enrichissement', 10000);

-- ============================================================
-- INSERT auth pour les nouveaux MCPs
-- ============================================================
INSERT OR IGNORE INTO mcp_auth (mcp_id, required, auth_type, key_name) VALUES
('ticket-tailor',   1, 'api_key', 'TICKET_TAILOR_API_KEY'),
('linear',          1, 'oauth',   'LINEAR_TOKEN'),
('hugging-face',    1, 'api_key', 'HF_API_KEY'),
('amplitude',       1, 'api_key', 'AMPLITUDE_API_KEY'),
('atlassian',       1, 'oauth',   'ATLASSIAN_TOKEN'),
('blockscout',      0, 'none',    NULL),
('close',           1, 'api_key', 'CLOSE_API_KEY'),
('cloudflare',      1, 'api_key', 'CLOUDFLARE_API_KEY'),
('egnyte',          1, 'oauth',   'EGNYTE_TOKEN'),
('figma',           1, 'oauth',   'FIGMA_TOKEN'),
('guru',            1, 'api_key', 'GURU_API_KEY'),
('jotform',         1, 'api_key', 'JOTFORM_API_KEY'),
('mermaid-chart',   0, 'none',    NULL),
('monday',          1, 'oauth',   'MONDAY_TOKEN'),
('notion-registry', 1, 'oauth',   'NOTION_TOKEN'),
('paypal',          1, 'oauth',   'PAYPAL_TOKEN'),
('stripe',          1, 'api_key', 'STRIPE_API_KEY'),
('supabase',        1, 'oauth',   'SUPABASE_TOKEN'),
('vercel',          1, 'oauth',   'VERCEL_TOKEN'),
('wix',             1, 'oauth',   'WIX_TOKEN'),
('coupler-io',      1, 'api_key', 'COUPLER_API_KEY'),
('dice',            0, 'none',    NULL);

-- ============================================================
-- INSERT error policies pour les nouveaux MCPs
-- ============================================================
INSERT OR IGNORE INTO mcp_error_policy
  (mcp_id, retry, max_retries, retry_delay_ms, on_failure, degradation_message)
SELECT mcp_id, 1, 2, 1000, 'degrade',
       name || ' indisponible — fonctionnalité désactivée pour cette session'
FROM mcp WHERE source = 'anthropic_registry';

-- ============================================================
-- VÉRIFICATION
-- ============================================================
SELECT
  source,
  COUNT(*)            AS mcp_count,
  SUM(is_free)        AS free_count,
  COUNT(DISTINCT registry_category) AS categories
FROM mcp
GROUP BY source;
