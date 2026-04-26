"""DDL for P2c backtest + LLM decision cache tables."""

SCHEMA_BACKTEST_SESSIONS = '''
CREATE TABLE IF NOT EXISTS backtest_sessions (
    id           TEXT PRIMARY KEY,
    start_date   TEXT NOT NULL,
    end_date     TEXT NOT NULL,
    agent_ids    TEXT NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes        TEXT
);
'''

SCHEMA_BACKTEST_RESULTS = '''
CREATE TABLE IF NOT EXISTS backtest_results (
    id                   TEXT PRIMARY KEY,
    session_id           TEXT NOT NULL,
    agent_id             TEXT NOT NULL,
    persona_id           TEXT,
    model_id             TEXT,
    start_date           TEXT NOT NULL,
    end_date             TEXT NOT NULL,
    initial_capital      REAL NOT NULL,
    final_equity         REAL,
    stats_json           TEXT NOT NULL,
    zone_stats_json      TEXT NOT NULL,
    quality_gate_label   TEXT NOT NULL,
    quality_gate_json    TEXT NOT NULL,
    daily_records_json   TEXT NOT NULL DEFAULT '[]',
    trades_json          TEXT NOT NULL DEFAULT '[]',
    thinking_json        TEXT NOT NULL DEFAULT '[]',
    universe_json        TEXT NOT NULL DEFAULT '[]',
    kind_str             TEXT NOT NULL DEFAULT 'agent',
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS results_by_session ON backtest_results(session_id);
CREATE INDEX IF NOT EXISTS results_by_agent   ON backtest_results(agent_id, created_at DESC);
'''

SCHEMA_LLM_DECISION_CACHE = '''
CREATE TABLE IF NOT EXISTS llm_decision_cache (
    cache_key        TEXT PRIMARY KEY,
    agent_id         TEXT NOT NULL,
    date             TEXT NOT NULL,
    response_json    TEXT NOT NULL,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS cache_by_agent_date
    ON llm_decision_cache(agent_id, date);
'''


def ensure_observability_columns(con):
    """Add the 3 P3-A columns to an existing backtest_results table.
    Idempotent: safe to call on a fresh schema."""
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    if 'daily_records_json' not in cols:
        con.execute("ALTER TABLE backtest_results ADD COLUMN "
                    "daily_records_json TEXT NOT NULL DEFAULT '[]'")
    if 'trades_json' not in cols:
        con.execute("ALTER TABLE backtest_results ADD COLUMN "
                    "trades_json TEXT NOT NULL DEFAULT '[]'")
    if 'thinking_json' not in cols:
        con.execute("ALTER TABLE backtest_results ADD COLUMN "
                    "thinking_json TEXT NOT NULL DEFAULT '[]'")


def ensure_kind_column(con):
    """Add kind_str to existing backtest_results if absent. Idempotent."""
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    if 'kind_str' not in cols:
        con.execute("ALTER TABLE backtest_results ADD COLUMN "
                    "kind_str TEXT NOT NULL DEFAULT 'agent'")


def ensure_persona_model_columns(con):
    """Add persona_id + model_id to legacy backtest_results tables.

    Phase 2.5 regression guard: pre-P2c databases were created without these
    columns, so even though SCHEMA_BACKTEST_RESULTS now declares them,
    `CREATE TABLE IF NOT EXISTS` is a no-op on the existing table and
    INSERTs would silently drop the values. Idempotent.
    """
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    if 'persona_id' not in cols:
        con.execute('ALTER TABLE backtest_results ADD COLUMN persona_id TEXT')
    if 'model_id' not in cols:
        con.execute('ALTER TABLE backtest_results ADD COLUMN model_id TEXT')


def ensure_universe_column(con):
    """Add universe_json column (2026-04-26 — input ticker pool persisted so
    the UI K-line grid can show ALL stocks in the universe, not only the
    ones actually traded). Idempotent."""
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    if 'universe_json' not in cols:
        con.execute("ALTER TABLE backtest_results ADD COLUMN "
                    "universe_json TEXT NOT NULL DEFAULT '[]'")
