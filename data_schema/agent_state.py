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

# Future P2 tables (personas, agents, backtest_results, audit_log, redlines)
# will be added here.
