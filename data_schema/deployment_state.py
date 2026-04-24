"""DDL for P3-F Phase 1 deployment + trade proposal tables."""

SCHEMA_DEPLOYED_AGENTS = '''
CREATE TABLE IF NOT EXISTS deployed_agents (
    agent_id     TEXT PRIMARY KEY,
    pid          INTEGER NOT NULL,
    started_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status       TEXT NOT NULL,
    schedule     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS deployed_by_status ON deployed_agents(status);
'''

SCHEMA_TRADE_PROPOSALS = '''
CREATE TABLE IF NOT EXISTS trade_proposals (
    id                   TEXT PRIMARY KEY,
    agent_id             TEXT NOT NULL,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decision_at          DATETIME NOT NULL,
    action               TEXT NOT NULL,
    code                 TEXT,
    shares               INTEGER,
    price                REAL,
    reason               TEXT,
    thinking             TEXT,
    status               TEXT NOT NULL,
    decided_by           TEXT,
    decided_at           DATETIME,
    execution_mode       TEXT,
    execution_order_id   TEXT,
    execution_error      TEXT,
    executed_at          DATETIME,
    filled_qty           INTEGER,
    filled_price         REAL
);
CREATE INDEX IF NOT EXISTS proposals_by_status ON trade_proposals(status, created_at DESC);
CREATE INDEX IF NOT EXISTS proposals_by_agent  ON trade_proposals(agent_id, created_at DESC);
'''

# Phase 2 migration: ALTERs run idempotently from init_schema() so Phase 1
# databases already in the wild pick up the new columns on next startup.
# Each ALTER is expected to raise sqlite3.OperationalError "duplicate column
# name" on subsequent runs; callers must swallow that specific error.
TRADE_PROPOSALS_PHASE2_ALTERS = [
    'ALTER TABLE trade_proposals ADD COLUMN execution_mode TEXT',
    'ALTER TABLE trade_proposals ADD COLUMN execution_order_id TEXT',
    'ALTER TABLE trade_proposals ADD COLUMN execution_error TEXT',
    'ALTER TABLE trade_proposals ADD COLUMN executed_at DATETIME',
    'ALTER TABLE trade_proposals ADD COLUMN filled_qty INTEGER',
    'ALTER TABLE trade_proposals ADD COLUMN filled_price REAL',
]
