"""DDL sanity for baseline_results."""
import sqlite3


def test_schema_creates_table(tmp_path):
    from data_schema.baseline_state import SCHEMA_BASELINE_RESULTS
    db = tmp_path / 'x.db'
    con = sqlite3.connect(db)
    try:
        con.executescript(SCHEMA_BASELINE_RESULTS)
        names = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    finally:
        con.close()
    assert 'baseline_results' in names


def test_indexes_present():
    from data_schema.baseline_state import SCHEMA_BASELINE_RESULTS
    assert 'baselines_by_session' in SCHEMA_BASELINE_RESULTS
