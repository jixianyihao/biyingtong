"""P3-A: observability endpoints — NAV, trades, thinking."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest


def test_backtest_results_schema_has_observability_columns(tmp_path):
    """新 schema 必须有 daily_records_json / trades_json / thinking_json。"""
    from data_schema.backtest_state import SCHEMA_BACKTEST_RESULTS
    con = sqlite3.connect(':memory:')
    con.executescript(SCHEMA_BACKTEST_RESULTS)
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    con.close()
    assert 'daily_records_json' in cols
    assert 'trades_json' in cols
    assert 'thinking_json' in cols


def test_ensure_observability_columns_migrates_old_schema(tmp_path):
    """旧 schema（只有 13 列）升级后必须有 16 列且旧数据保留。"""
    import sqlite3
    from data_schema.backtest_state import ensure_observability_columns

    db = tmp_path / 'test.db'
    con = sqlite3.connect(db)
    # 模拟旧表
    con.execute('''CREATE TABLE backtest_results (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL, agent_id TEXT NOT NULL,
        persona_id TEXT, model_id TEXT,
        start_date TEXT NOT NULL, end_date TEXT NOT NULL,
        initial_capital REAL NOT NULL, final_equity REAL,
        stats_json TEXT NOT NULL, zone_stats_json TEXT NOT NULL,
        quality_gate_label TEXT NOT NULL, quality_gate_json TEXT NOT NULL
    )''')
    con.execute(
        "INSERT INTO backtest_results VALUES "
        "('r1','s1','a1',null,null,'2025-01-01','2025-01-10',"
        "100000.0,null,'{}','[]','pass','{}')",
    )
    con.commit()

    ensure_observability_columns(con)
    ensure_observability_columns(con)  # idempotent

    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    assert 'daily_records_json' in cols
    assert 'trades_json' in cols
    assert 'thinking_json' in cols

    row = con.execute(
        'SELECT daily_records_json, trades_json, thinking_json '
        'FROM backtest_results WHERE id=?', ('r1',),
    ).fetchone()
    assert row == ('[]', '[]', '[]')
    con.close()


def test_backtest_result_observability_defaults_empty():
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
        quality_gate_label='warn', quality_gate_criteria={},
    )
    assert r.daily_records == []
    assert r.trades == []
    assert r.thinking == []


def test_book_records_fills_on_buy_and_sell():
    from datetime import date
    from backtest.book import Book
    from backtest.commission import FeeModel

    book = Book(cash=200_000.0, fee_model=FeeModel())
    d1 = date(2025, 1, 2)
    d2 = date(2025, 1, 3)
    fill1 = book.execute_buy('600519.SH', shares=100, price=1000.0, d=d1)
    fill2 = book.execute_sell('600519.SH', shares=50, price=1100.0, d=d2)

    assert fill1 is not None
    assert fill2 is not None
    assert len(book.fills) == 2
    f1, f2 = book.fills
    assert f1.side == 'buy'
    assert f1.shares == 100
    assert f1.date == d1
    assert f2.side == 'sell'
    assert f2.shares == 50
    assert f2.date == d2


def test_backtest_runner_populates_trades_and_daily_records(
    observability_storage, monkeypatch,
):
    """End-to-end: MockLLM buys then sells; result carries trades + daily_records."""
    from datetime import date, timedelta
    import storage
    from backtest.runner import BacktestRunner
    import backtest.runner as runner_mod
    from llm.mock import MockLLM

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-p3a', initial_capital=1_000_000.0,
    )

    # 7 trading days at a low, near-flat price so buys fit under position_max_pct
    # (15%) and lot-rounding (100 shares) is satisfied.
    days = [date(2025, 1, 2) + timedelta(days=i) for i in range(7)]
    bars = [(d, 100.0 + i * 0.2) for i, d in enumerate(days)]
    monkeypatch.setattr(runner_mod, '_load_daily_closes',
                        lambda code, start, end: bars)
    monkeypatch.setattr(runner_mod, '_trading_days',
                        lambda start, end: days)

    # MockLLM script (each element is one LLMResponse spec — see tests/test_backtest_runner.py)
    buy = {'tool_calls': [{'id': 'b1', 'name': 'place_decision',
                           'input': {'action': 'buy', 'code': '600519.SH',
                                     'qty': 100,
                                     'reason': 'buy day — quality name at a fair entry',
                                     'thinking': 'buying now'}}],
           'stop_reason': 'tool_use'}
    # T+1: sell cannot happen same day as buy. Hold day 2, sell day 3.
    sell = {'tool_calls': [{'id': 's1', 'name': 'place_decision',
                            'input': {'action': 'sell', 'code': '600519.SH',
                                      'qty': 100,
                                      'reason': 'locking gains, thesis played out',
                                      'thinking': 'selling now'}}],
            'stop_reason': 'tool_use'}
    hold = {'tool_calls': [{'id': 'h', 'name': 'place_decision',
                            'input': {'action': 'hold',
                                      'reason': 'waiting for a clearer setup today',
                                      'thinking': 'holding'}}],
            'stop_reason': 'tool_use'}
    # 7 days: buy, hold, sell, hold, hold, hold, hold
    llm = MockLLM([buy, hold, sell, hold, hold, hold, hold])

    r = BacktestRunner(llm=llm).run(
        session_id='s-p3a', agent_id=agent.id,
        start_date='2025-01-02', end_date='2025-01-08',
        universe=['600519.SH'],
    )
    # 7-day deterministic script → exactly 7 daily_records and 2 trades (1 buy + 1 sell)
    assert len(r.daily_records) == 7
    for rec in r.daily_records:
        assert set(rec) == {'date', 'equity', 'cash', 'pnl_pct',
                            'trade_count', 'won'}
    assert len(r.trades) == 2
    assert r.trades[0]['action'] == 'buy'
    assert r.trades[1]['action'] == 'sell'
    for t in r.trades:
        assert set(t) == {'date', 'code', 'action', 'shares', 'price', 'fee'}
