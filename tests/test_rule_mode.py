"""P3-C Rule mode backtest — strategies, runner, endpoint."""
from __future__ import annotations

import sqlite3
import pytest


def test_backtest_results_schema_has_kind_column():
    from data_schema.backtest_state import SCHEMA_BACKTEST_RESULTS
    con = sqlite3.connect(':memory:')
    con.executescript(SCHEMA_BACKTEST_RESULTS)
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    con.close()
    assert 'kind_str' in cols


def test_ensure_kind_column_migrates_old_schema(tmp_path):
    import sqlite3
    from data_schema.backtest_state import ensure_kind_column
    db = tmp_path / 'legacy.db'
    con = sqlite3.connect(db)
    con.execute('''CREATE TABLE backtest_results (
        id TEXT PRIMARY KEY, session_id TEXT NOT NULL, agent_id TEXT NOT NULL,
        persona_id TEXT, model_id TEXT,
        start_date TEXT NOT NULL, end_date TEXT NOT NULL,
        initial_capital REAL NOT NULL, final_equity REAL,
        stats_json TEXT NOT NULL, zone_stats_json TEXT NOT NULL,
        quality_gate_label TEXT NOT NULL, quality_gate_json TEXT NOT NULL
    )''')
    con.execute(
        "INSERT INTO backtest_results VALUES "
        "('r1','s1','a1',null,null,'2025-01-01','2025-01-02',"
        "100000.0,null,'{}','[]','pass','{}')",
    )
    con.commit()

    ensure_kind_column(con)
    ensure_kind_column(con)  # idempotent

    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    assert 'kind_str' in cols
    row = con.execute(
        "SELECT kind_str FROM backtest_results WHERE id=?", ('r1',),
    ).fetchone()
    assert row == ('agent',)  # default
    con.close()


def test_backtest_result_kind_defaults_agent():
    from backtest.base import BacktestResult, BacktestStats
    r = BacktestResult(
        id='r', session_id='s', agent_id='a',
        persona_id=None, model_id=None,
        start_date='2025-01-01', end_date='2025-01-10',
        initial_capital=100_000.0,
        stats=BacktestStats(
            sharpe=0.0, max_drawdown_pct=0.0, trade_count=0,
            win_rate=0.0, max_daily_loss_pct=0.0,
            total_return_pct=0.0, final_equity=100_000.0,
        ),
        zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
    )
    assert r.kind == 'agent'


def test_backtest_result_kind_rule():
    from backtest.base import BacktestResult, BacktestStats
    r = BacktestResult(
        id='r', session_id='s', agent_id='',
        persona_id=None, model_id=None,
        start_date='2025-01-01', end_date='2025-01-10',
        initial_capital=100_000.0,
        stats=BacktestStats(
            sharpe=0.0, max_drawdown_pct=0.0, trade_count=0,
            win_rate=0.0, max_daily_loss_pct=0.0,
            total_return_pct=0.0, final_equity=100_000.0,
        ),
        zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        kind='rule',
    )
    assert r.kind == 'rule'
