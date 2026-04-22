"""DDL sanity checks for P2c backtest tables."""
import sqlite3


def test_schemas_create_expected_tables(tmp_path):
    from data_schema.backtest_state import (
        SCHEMA_BACKTEST_SESSIONS, SCHEMA_BACKTEST_RESULTS,
        SCHEMA_LLM_DECISION_CACHE,
    )
    db = tmp_path / 'x.db'
    con = sqlite3.connect(db)
    try:
        con.executescript(SCHEMA_BACKTEST_SESSIONS)
        con.executescript(SCHEMA_BACKTEST_RESULTS)
        con.executescript(SCHEMA_LLM_DECISION_CACHE)
        names = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    finally:
        con.close()
    assert {'backtest_sessions', 'backtest_results',
            'llm_decision_cache'} <= names


def test_backtest_results_has_session_fk_column():
    from data_schema.backtest_state import SCHEMA_BACKTEST_RESULTS
    assert 'session_id' in SCHEMA_BACKTEST_RESULTS


def test_llm_cache_uses_composite_key():
    from data_schema.backtest_state import SCHEMA_LLM_DECISION_CACHE
    assert 'PRIMARY KEY' in SCHEMA_LLM_DECISION_CACHE
    assert 'cache_key' in SCHEMA_LLM_DECISION_CACHE


def test_indexes_present():
    from data_schema.backtest_state import SCHEMA_BACKTEST_RESULTS
    assert 'results_by_session' in SCHEMA_BACKTEST_RESULTS
    assert 'results_by_agent' in SCHEMA_BACKTEST_RESULTS
