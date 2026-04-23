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

    # Task 3: per-day thinking is now populated
    assert len(r.thinking) == 7
    t0 = r.thinking[0]
    assert set(t0) >= {'date', 'reasoning', 'tool_calls', 'decisions'}
    assert t0['date'] == '2025-01-02'
    # Day 0 is a buy → decision recorded
    assert len(t0['decisions']) == 1
    assert t0['decisions'][0]['action'] == 'buy'
    assert 'outcome' in t0['decisions'][0]


def test_agent_runner_captures_thinking_per_day(observability_storage):
    """run_day 之后 last_thinking 包含 reasoning / tool_calls / decisions。"""
    from agents.runner import AgentRunner
    from llm.mock import MockLLM
    import storage

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-thk', initial_capital=1_000_000.0,
    )

    script = [
        {
            'text': 'strong consumer brand, low P/E',
            'tool_calls': [{
                'id': 'c1', 'name': 'place_decision',
                'input': {'action': 'buy', 'code': '600519.SH',
                          'qty': 100,
                          'reason': 'buy now',
                          'thinking': 'buying now'},
            }],
            'stop_reason': 'tool_use',
        },
    ]
    runner = AgentRunner(llm=MockLLM(script))
    runner.run_day(
        agent_id=agent.id, date='2025-01-03',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 100.0},
    )
    thk = runner.last_thinking
    assert thk is not None
    assert 'strong consumer' in thk['reasoning']
    assert len(thk['decisions']) == 1
    assert thk['decisions'][0]['action'] == 'buy'
    assert 'outcome' in thk['decisions'][0]
    assert isinstance(thk['tool_calls'], list)


def test_agent_runner_thinking_records_rejected_decisions(observability_storage):
    """Rejected decisions must still surface in last_thinking.decisions."""
    from agents.runner import AgentRunner
    from llm.mock import MockLLM
    import storage

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-rej', initial_capital=1_000_000.0,
    )

    # Portfolio already holds 200k of 600519 — existing value ≥ 15% cap →
    # position_max_pct rejects any additional buy.
    portfolio = {
        'cash': 800_000, 'equity': 1_000_000,
        'positions': {'600519.SH': {'shares': 2000, 'avg_price': 100.0}},
    }
    script = [
        {
            'text': 'want to add more',
            'tool_calls': [{
                'id': 'r1', 'name': 'place_decision',
                'input': {'action': 'buy', 'code': '600519.SH',
                          'qty': 100, 'reason': 'add more',
                          'thinking': 'buying'},
            }],
            'stop_reason': 'tool_use',
        },
    ]
    runner = AgentRunner(llm=MockLLM(script))
    executed = runner.run_day(
        agent_id=agent.id, date='2025-01-03',
        portfolio=portfolio, market_context={},
        mark_prices={'600519.SH': 100.0},
    )
    # Validation rejected → nothing executed
    assert executed == []
    # But thinking still records the rejected decision
    thk = runner.last_thinking
    assert len(thk['decisions']) == 1
    assert thk['decisions'][0]['action'] == 'buy'
    assert thk['decisions'][0]['outcome'] == 'rejected'


def test_agent_runner_thinking_cache_hit_uses_synthetic_entry(observability_storage):
    """Second identical run_day call hits cache → last_thinking has outcome='cached'."""
    from agents.runner import AgentRunner
    from llm.mock import MockLLM
    import storage

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-cache', initial_capital=1_000_000.0,
    )
    script = [
        {
            'text': 'deciding',
            'tool_calls': [{
                'id': 'c1', 'name': 'place_decision',
                'input': {'action': 'buy', 'code': '600519.SH',
                          'qty': 100, 'reason': 'buy',
                          'thinking': 'buy'},
            }],
            'stop_reason': 'tool_use',
        },
    ]
    # First call populates cache; consume the script's only entry
    runner = AgentRunner(llm=MockLLM(script))
    kwargs = dict(
        agent_id=agent.id, date='2025-01-03',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 100.0},
    )
    runner.run_day(**kwargs)
    live_thk = runner.last_thinking

    # Second call with same state → cache hit. Give MockLLM an empty script so
    # any accidental LLM call would raise loudly (proves cache was hit).
    runner2 = AgentRunner(llm=MockLLM([]))
    runner2.run_day(**kwargs)
    cached_thk = runner2.last_thinking

    assert cached_thk is not None
    assert cached_thk['reasoning'] == '(cached — no LLM call)'
    assert cached_thk['tool_calls'] == []
    assert len(cached_thk['decisions']) == 1
    assert cached_thk['decisions'][0]['outcome'] == 'cached'
    # Shape must match live-call entries (except reasoning text + outcome value)
    live_keys = set(live_thk['decisions'][0])
    cached_keys = set(cached_thk['decisions'][0])
    assert live_keys == cached_keys


def test_sqlite_backtests_roundtrips_observability_fields(observability_storage):
    """Insert a BacktestResult with observability fields; get() returns them intact."""
    import storage
    from backtest.base import BacktestResult, BacktestStats

    storage.backtests().create_session('s-rt', '2025-01-01', '2025-01-10', ['a1'])
    stats = BacktestStats(
        sharpe=1.2, max_drawdown_pct=-5.0, trade_count=4,
        win_rate=75.0, max_daily_loss_pct=-1.5,
        total_return_pct=8.0, final_equity=108_000.0,
    )
    result = BacktestResult(
        id='r-rt', session_id='s-rt', agent_id='a1',
        persona_id=None, model_id=None,
        start_date='2025-01-01', end_date='2025-01-10',
        initial_capital=100_000.0,
        stats=stats,
        zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        final_equity=108_000.0,
        daily_records=[{'date': '2025-01-02', 'equity': 100_500.0,
                        'cash': 50_000.0, 'pnl_pct': 0.5,
                        'trade_count': 1, 'won': 1}],
        trades=[{'date': '2025-01-02', 'code': '600519.SH',
                 'action': 'buy', 'shares': 100, 'price': 500.0,
                 'fee': 15.0}],
        thinking=[{'date': '2025-01-02', 'reasoning': 'strong brand',
                   'tool_calls': [], 'decisions': []}],
    )
    storage.backtests().insert(result)

    fetched = storage.backtests().get('r-rt')
    assert fetched is not None
    assert len(fetched.daily_records) == 1
    assert fetched.daily_records[0]['equity'] == 100_500.0
    assert fetched.daily_records[0]['cash'] == 50_000.0
    assert fetched.trades[0]['code'] == '600519.SH'
    assert fetched.trades[0]['shares'] == 100
    assert fetched.thinking[0]['reasoning'] == 'strong brand'


def test_sqlite_backtests_defaults_to_empty_lists_for_legacy_rows(observability_storage):
    """Row written without observability columns (simulating pre-P3A data)
    should still load with empty lists, not crash."""
    import sqlite3, json
    from dataclasses import asdict
    import storage
    from backtest.base import BacktestStats

    store = storage.backtests()
    db_path = store._db_path  # type: ignore[attr-defined]
    storage.backtests().create_session('s-leg', '2025-01-01', '2025-01-02', ['al'])
    stats = BacktestStats(sharpe=0, max_drawdown_pct=0, trade_count=0,
                          win_rate=0, max_daily_loss_pct=0,
                          total_return_pct=0, final_equity=100_000)
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            '''INSERT INTO backtest_results (id, session_id, agent_id,
                persona_id, model_id, start_date, end_date, initial_capital,
                final_equity, stats_json, zone_stats_json, quality_gate_label,
                quality_gate_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            ('r-leg', 's-leg', 'al', None, None, '2025-01-01', '2025-01-02',
             100_000.0, 100_000.0, json.dumps(asdict(stats)),
             '[]', 'pass', '{}'),
        )
        con.commit()
    finally:
        con.close()

    fetched = storage.backtests().get('r-leg')
    assert fetched is not None
    # Legacy row — new columns default to '[]' (via schema default), parse to []
    assert fetched.daily_records == []
    assert fetched.trades == []
    assert fetched.thinking == []


# ---------------------------------------------------------------------------
# Task 5: GET /api/backtests/:id/{nav,trades,thinking} endpoints
# ---------------------------------------------------------------------------

def _fresh_app():
    """Build a minimal Flask app with the api blueprint — avoids importing
    app.py (which pulls in tdx_service)."""
    from flask import Flask
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(observability_storage):
    """Flask test client. Depends on observability_storage so the app sees
    the wired-up storage singletons."""
    return _fresh_app().test_client()


def test_nav_endpoint_returns_daily_curves(observability_storage, client):
    """GET /api/backtests/:id/nav returns agent curve + (empty) baseline curves."""
    import storage
    from backtest.base import BacktestResult, BacktestStats
    r = BacktestResult(
        id='nav1', session_id='s-nav', agent_id='a1',
        persona_id=None, model_id=None,
        start_date='2025-01-02', end_date='2025-01-08',
        initial_capital=100_000.0,
        stats=BacktestStats(sharpe=1.0, max_drawdown_pct=-1.0,
                            trade_count=0, win_rate=0.0,
                            max_daily_loss_pct=0.0, total_return_pct=2.0,
                            final_equity=102_000.0),
        zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        daily_records=[
            {'date': '2025-01-02', 'equity': 100_000.0, 'cash': 100_000.0,
             'pnl_pct': 0.0, 'trade_count': 0, 'won': 0},
            {'date': '2025-01-03', 'equity': 101_000.0, 'cash': 0.0,
             'pnl_pct': 1.0, 'trade_count': 1, 'won': 0},
        ],
    )
    storage.backtests().create_session('s-nav', '2025-01-02', '2025-01-08', ['a1'])
    storage.backtests().insert(r)

    resp = client.get('/api/backtests/nav1/nav')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['result_id'] == 'nav1'
    assert 'agent' in data
    assert len(data['agent']) == 2
    assert data['agent'][0]['date'] == '2025-01-02'
    assert data['agent'][0]['equity'] == 100_000.0
    assert data['agent'][0]['cash'] == 100_000.0
    assert data['agent'][0]['pnl_pct'] == 0.0
    assert 'baselines' in data
    assert isinstance(data['baselines'], list)


def test_nav_endpoint_404_on_missing(observability_storage, client):
    resp = client.get('/api/backtests/nope/nav')
    assert resp.status_code == 404


def test_trades_endpoint_returns_fills(observability_storage, client):
    import storage
    from backtest.base import BacktestResult, BacktestStats
    r = BacktestResult(
        id='tr1', session_id='s-tr', agent_id='a1',
        persona_id=None, model_id=None,
        start_date='2025-01-02', end_date='2025-01-08',
        initial_capital=100_000.0,
        stats=BacktestStats(sharpe=0.0, max_drawdown_pct=0.0, trade_count=1,
                            win_rate=0.0, max_daily_loss_pct=0.0,
                            total_return_pct=0.0, final_equity=100_000.0),
        zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        trades=[{'date': '2025-01-03', 'code': '600519.SH',
                 'action': 'buy', 'shares': 100, 'price': 500.0, 'fee': 15.0}],
    )
    storage.backtests().create_session('s-tr', '2025-01-02', '2025-01-08', ['a1'])
    storage.backtests().insert(r)

    resp = client.get('/api/backtests/tr1/trades')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['result_id'] == 'tr1'
    assert 'trades' in data
    assert len(data['trades']) == 1
    assert data['trades'][0]['code'] == '600519.SH'
    assert data['trades'][0]['action'] == 'buy'


def test_trades_endpoint_404_on_missing(observability_storage, client):
    resp = client.get('/api/backtests/nope/trades')
    assert resp.status_code == 404


def test_thinking_endpoint_returns_per_day_reasoning(observability_storage, client):
    import storage
    from backtest.base import BacktestResult, BacktestStats
    r = BacktestResult(
        id='th1', session_id='s-th', agent_id='a1',
        persona_id=None, model_id=None,
        start_date='2025-01-02', end_date='2025-01-08',
        initial_capital=100_000.0,
        stats=BacktestStats(sharpe=0.0, max_drawdown_pct=0.0, trade_count=0,
                            win_rate=0.0, max_daily_loss_pct=0.0,
                            total_return_pct=0.0, final_equity=100_000.0),
        zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        thinking=[{'date': '2025-01-02',
                   'reasoning': 'strong consumer brand',
                   'tool_calls': [],
                   'decisions': [{'action': 'buy', 'code': '600519.SH',
                                  'shares': 100, 'price': 1000.0,
                                  'outcome': 'approved',
                                  'reasoning': 'buy'}]}],
    )
    storage.backtests().create_session('s-th', '2025-01-02', '2025-01-08', ['a1'])
    storage.backtests().insert(r)

    resp = client.get('/api/backtests/th1/thinking')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['result_id'] == 'th1'
    assert 'thinking' in data
    assert len(data['thinking']) == 1
    assert data['thinking'][0]['reasoning'] == 'strong consumer brand'
    assert data['thinking'][0]['decisions'][0]['action'] == 'buy'


def test_thinking_endpoint_404_on_missing(observability_storage, client):
    resp = client.get('/api/backtests/nope/thinking')
    assert resp.status_code == 404
