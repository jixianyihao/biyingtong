"""DDL for baseline_results (P2d)."""

SCHEMA_BASELINE_RESULTS = '''
CREATE TABLE IF NOT EXISTS baseline_results (
    id                TEXT PRIMARY KEY,
    session_id        TEXT NOT NULL,
    name              TEXT NOT NULL,
    start_date        TEXT NOT NULL,
    end_date          TEXT NOT NULL,
    initial_capital   REAL NOT NULL,
    final_equity      REAL,
    stats_json        TEXT NOT NULL,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS baselines_by_session
    ON baseline_results(session_id);
'''
