"""DDL for baseline_results (P2d + P3A)."""

SCHEMA_BASELINE_RESULTS = '''
CREATE TABLE IF NOT EXISTS baseline_results (
    id                  TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL,
    name                TEXT NOT NULL,
    start_date          TEXT NOT NULL,
    end_date            TEXT NOT NULL,
    initial_capital     REAL NOT NULL,
    final_equity        REAL,
    stats_json          TEXT NOT NULL,
    daily_records_json  TEXT NOT NULL DEFAULT '[]',
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS baselines_by_session
    ON baseline_results(session_id);
'''


def ensure_baseline_observability_column(con):
    """Idempotent migration: add daily_records_json to baseline_results if
    the table predates P3-A."""
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(baseline_results)').fetchall()}
    if 'daily_records_json' not in cols:
        con.execute("ALTER TABLE baseline_results ADD COLUMN "
                    "daily_records_json TEXT NOT NULL DEFAULT '[]'")
