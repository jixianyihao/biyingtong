"""SQL DDL for agent_state.db tables.

Centralized so storage/sqlite_* modules can share exact-match schema.
"""

SCHEMA_LLM_MODELS = '''
CREATE TABLE IF NOT EXISTS llm_models (
    id                TEXT PRIMARY KEY,
    provider          TEXT NOT NULL,
    display_name      TEXT NOT NULL,
    api_model_id      TEXT NOT NULL,
    training_cutoff   DATE NOT NULL,
    supports_tool_use INTEGER DEFAULT 1,
    max_tokens_out    INTEGER DEFAULT 4096,
    enabled           INTEGER DEFAULT 1
);
'''

# --- Added in P2a ---

SCHEMA_PERSONAS = '''
CREATE TABLE IF NOT EXISTS personas (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    style_desc       TEXT,
    system_prompt    TEXT NOT NULL,
    default_pool     TEXT NOT NULL,
    pool_filter      TEXT,
    default_schedule TEXT NOT NULL,
    default_rules    TEXT NOT NULL,
    allowed_tools    TEXT NOT NULL,
    is_builtin       INTEGER DEFAULT 0,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);
'''

SCHEMA_AGENTS = '''
CREATE TABLE IF NOT EXISTS agents (
    id                        TEXT PRIMARY KEY,
    persona_id                TEXT NOT NULL REFERENCES personas(id),
    model_id                  TEXT NOT NULL REFERENCES llm_models(id),
    display_name              TEXT NOT NULL,
    rules_override            TEXT NOT NULL,
    initial_capital           REAL NOT NULL,
    status                    TEXT DEFAULT 'created',
    subprocess_pid            INTEGER,
    health_score              INTEGER DEFAULT 100,
    trust_rating              TEXT DEFAULT 'A',
    current_prompt_version_id INTEGER,
    created_at                DATETIME DEFAULT CURRENT_TIMESTAMP
);
'''

SCHEMA_PROMPT_VERSIONS = '''
CREATE TABLE IF NOT EXISTS prompt_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    version_number  INTEGER NOT NULL,
    system_prompt   TEXT NOT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    note            TEXT,
    UNIQUE(agent_id, version_number)
);
'''

SCHEMA_PROMPT_VERSION_INDEX = '''
CREATE INDEX IF NOT EXISTS prompt_by_agent
  ON prompt_versions(agent_id, version_number DESC);
'''
