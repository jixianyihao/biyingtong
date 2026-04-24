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
    id           TEXT PRIMARY KEY,
    agent_id     TEXT NOT NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decision_at  DATETIME NOT NULL,
    action       TEXT NOT NULL,
    code         TEXT,
    shares       INTEGER,
    price        REAL,
    reason       TEXT,
    thinking     TEXT,
    status       TEXT NOT NULL,
    decided_by   TEXT,
    decided_at   DATETIME
);
CREATE INDEX IF NOT EXISTS proposals_by_status ON trade_proposals(status, created_at DESC);
CREATE INDEX IF NOT EXISTS proposals_by_agent  ON trade_proposals(agent_id, created_at DESC);
'''
