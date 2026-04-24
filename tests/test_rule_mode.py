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


def test_ma_crossover_buys_on_golden_cross():
    from datetime import date
    from backtest.strategies.ma_crossover import MACrossover

    s = MACrossover(params={'fast': 3, 'slow': 5, 'position_pct': 0.3})
    # fast (last 3) > slow (last 5), after prev day fast <= slow
    d = date(2025, 1, 8)
    close_history = {
        '600519.SH': [
            (date(2025, 1, 2), 100.0),
            (date(2025, 1, 3), 105.0),
            (date(2025, 1, 4), 108.0),
            (date(2025, 1, 5), 110.0),
            (date(2025, 1, 6), 115.0),
            (date(2025, 1, 7), 118.0),
            (date(2025, 1, 8), 120.0),
        ],
    }
    portfolio = {'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}}
    decisions = s.on_day(date=d, close_history=close_history, portfolio=portfolio)
    assert len(decisions) == 1
    assert decisions[0]['action'] == 'buy'
    assert decisions[0]['code'] == '600519.SH'
    assert decisions[0]['shares'] > 0


def test_ma_crossover_sells_on_death_cross():
    from datetime import date
    from backtest.strategies.ma_crossover import MACrossover

    s = MACrossover(params={'fast': 3, 'slow': 5})
    d = date(2025, 1, 8)
    close_history = {
        '600519.SH': [
            (date(2025, 1, 2), 120.0),
            (date(2025, 1, 3), 115.0),
            (date(2025, 1, 4), 110.0),
            (date(2025, 1, 5), 108.0),
            (date(2025, 1, 6), 105.0),
            (date(2025, 1, 7), 100.0),
            (date(2025, 1, 8), 95.0),
        ],
    }
    portfolio = {
        'cash': 500_000, 'equity': 500_000 + 100 * 95,
        'positions': {'600519.SH': {'shares': 100, 'avg_price': 110.0}},
    }
    decisions = s.on_day(date=d, close_history=close_history, portfolio=portfolio)
    assert any(d['action'] == 'sell' and d['code'] == '600519.SH' for d in decisions)


def test_ma_crossover_insufficient_history_returns_empty():
    from datetime import date
    from backtest.strategies.ma_crossover import MACrossover
    s = MACrossover(params={'fast': 5, 'slow': 20})
    decisions = s.on_day(
        date=date(2025, 1, 3),
        close_history={'600519.SH': [(date(2025, 1, 2), 100.0)]},
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
    )
    assert decisions == []


def test_strategies_registry_has_ma_crossover():
    from backtest.strategies import list_all, get, build
    names = [d.name for d in list_all()]
    assert 'ma_crossover' in names
    entry = get('ma_crossover')
    assert entry is not None
    instance = build('ma_crossover')
    assert instance.name == 'ma_crossover'
    # Default params are populated
    assert 'fast' in instance.params
    assert 'slow' in instance.params


def test_rsi_breakout_buys_when_rsi_below_30():
    from datetime import date
    from backtest.strategies.rsi_breakout import RSIBreakout

    s = RSIBreakout(params={'period': 14, 'oversold': 30, 'overbought': 70,
                            'position_pct': 0.3})
    # 15-day continuously falling price → Wilder's RSI ~0 (all losses, no gains)
    dates = [date(2025, 1, d) for d in range(2, 17)]
    series = list(zip(dates, [100.0 - i * 2 for i in range(15)]))
    portfolio = {'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}}
    decisions = s.on_day(
        date=dates[-1], close_history={'600519.SH': series},
        portfolio=portfolio,
    )
    assert any(d['action'] == 'buy' for d in decisions)


def test_rsi_breakout_sells_when_rsi_above_70():
    from datetime import date
    from backtest.strategies.rsi_breakout import RSIBreakout

    s = RSIBreakout(params={'period': 14, 'oversold': 30, 'overbought': 70})
    dates = [date(2025, 1, d) for d in range(2, 17)]
    series = list(zip(dates, [100.0 + i * 2 for i in range(15)]))
    portfolio = {
        'cash': 500_000, 'equity': 500_000 + 100 * 128,
        'positions': {'600519.SH': {'shares': 100, 'avg_price': 100.0}},
    }
    decisions = s.on_day(
        date=dates[-1], close_history={'600519.SH': series},
        portfolio=portfolio,
    )
    assert any(d['action'] == 'sell' for d in decisions)


def test_rsi_breakout_insufficient_history_returns_empty():
    from datetime import date
    from backtest.strategies.rsi_breakout import RSIBreakout
    s = RSIBreakout(params={'period': 14})
    decisions = s.on_day(
        date=date(2025, 1, 3),
        close_history={'600519.SH': [(date(2025, 1, 2), 100.0)]},
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
    )
    assert decisions == []


def test_macd_divergence_buys_on_bullish_cross():
    from datetime import date, timedelta
    from backtest.strategies.macd_divergence import MACDDivergence

    s = MACDDivergence(params={'fast': 12, 'slow': 26, 'signal': 9,
                               'position_pct': 0.3})
    # 40-day uptrend — in steady uptrend MACD line stays above signal → histogram > 0
    d = date(2025, 1, 2)
    dates = []
    for _ in range(40):
        dates.append(d)
        d = d + timedelta(days=1)
    prices = [100.0]
    for _ in range(39):
        prices.append(prices[-1] * 1.02)
    series = list(zip(dates, prices))
    portfolio = {'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}}
    decisions = s.on_day(
        date=dates[-1], close_history={'600519.SH': series},
        portfolio=portfolio,
    )
    assert any(d['action'] == 'buy' for d in decisions)


def test_macd_divergence_sells_on_bearish_cross():
    """Downtrend → histogram < 0 → sell."""
    from datetime import date, timedelta
    from backtest.strategies.macd_divergence import MACDDivergence

    s = MACDDivergence(params={'fast': 12, 'slow': 26, 'signal': 9})
    d = date(2025, 1, 2)
    dates = []
    for _ in range(40):
        dates.append(d)
        d = d + timedelta(days=1)
    prices = [100.0]
    for _ in range(39):
        prices.append(prices[-1] * 0.98)
    series = list(zip(dates, prices))
    portfolio = {
        'cash': 500_000, 'equity': 500_000 + 100 * prices[-1],
        'positions': {'600519.SH': {'shares': 100, 'avg_price': 100.0}},
    }
    decisions = s.on_day(
        date=dates[-1], close_history={'600519.SH': series},
        portfolio=portfolio,
    )
    assert any(d['action'] == 'sell' for d in decisions)


def test_macd_divergence_insufficient_history_returns_empty():
    from datetime import date
    from backtest.strategies.macd_divergence import MACDDivergence
    s = MACDDivergence()
    decisions = s.on_day(
        date=date(2025, 1, 3),
        close_history={'600519.SH': [(date(2025, 1, 2), 100.0)]},
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
    )
    assert decisions == []


def test_strategies_registry_lists_all_three():
    from backtest.strategies import list_all
    names = [d.name for d in list_all()]
    assert 'ma_crossover' in names
    assert 'rsi_breakout' in names
    assert 'macd_divergence' in names
