"""SQL DDL for validation/audit tables (P2b)."""

SCHEMA_REDLINES = '''
CREATE TABLE IF NOT EXISTS redlines (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    values_json TEXT    NOT NULL,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
'''

SCHEMA_STOCK_STATUS = '''
CREATE TABLE IF NOT EXISTS stock_status (
    code         TEXT PRIMARY KEY,
    name         TEXT,
    is_st        INTEGER NOT NULL DEFAULT 0,
    is_suspended INTEGER NOT NULL DEFAULT 0,
    is_delisted  INTEGER NOT NULL DEFAULT 0,
    listing_date TEXT,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS stock_status_st ON stock_status(is_st);
'''

SCHEMA_AUDIT_LOG = '''
CREATE TABLE IF NOT EXISTS audit_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      DATETIME DEFAULT CURRENT_TIMESTAMP,
    kind           TEXT NOT NULL,
    agent_id       TEXT,
    persona_id     TEXT,
    model_id       TEXT,
    prompt_version INTEGER,
    details        TEXT
);
CREATE INDEX IF NOT EXISTS audit_by_agent ON audit_log(agent_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS audit_by_kind  ON audit_log(kind, timestamp DESC);
'''
