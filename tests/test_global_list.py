"""GET /api/backtests global list (spec §15.4)."""
from __future__ import annotations

import pytest


def _fresh_flask_app():
    from flask import Flask
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(observability_storage):
    app = _fresh_flask_app()
    with app.test_client() as c:
        yield c


def test_backtest_store_has_list_all_protocol_method():
    from storage.base import BacktestResultStore
    assert 'list_all' in dir(BacktestResultStore)


def test_list_all_returns_recent_results(observability_storage):
    """list_all returns most-recent-first across all agents."""
    import storage
    from backtest.base import BacktestResult, BacktestStats

    storage.backtests().create_session('s1', '2025-01-01', '2025-01-10', ['a'])
    storage.backtests().create_session('s2', '2025-01-01', '2025-01-10', ['b'])
    stats = BacktestStats(sharpe=0, max_drawdown_pct=0, trade_count=0,
                          win_rate=0, max_daily_loss_pct=0,
                          total_return_pct=0, final_equity=100_000)
    for i, agent_id in enumerate(['a-1', 'b-1', 'a-2']):
        r = BacktestResult(
            id=f'r{i}', session_id='s1', agent_id=agent_id,
            persona_id=None, model_id=None,
            start_date='2025-01-01', end_date='2025-01-10',
            initial_capital=100_000.0, stats=stats, zone_stats=[],
            quality_gate_label='pass', quality_gate_criteria={},
        )
        storage.backtests().insert(r)

    rows = storage.backtests().list_all(limit=10)
    assert len(rows) == 3
    # most recent first — last inserted should be first
    assert rows[0].id == 'r2'


def test_list_all_respects_limit(observability_storage):
    import storage
    from backtest.base import BacktestResult, BacktestStats
    storage.backtests().create_session('s', '2025-01-01', '2025-01-02', ['a'])
    stats = BacktestStats(sharpe=0, max_drawdown_pct=0, trade_count=0,
                          win_rate=0, max_daily_loss_pct=0,
                          total_return_pct=0, final_equity=100_000)
    for i in range(5):
        r = BacktestResult(
            id=f'rl{i}', session_id='s', agent_id=f'a{i}',
            persona_id=None, model_id=None,
            start_date='2025-01-01', end_date='2025-01-02',
            initial_capital=100_000.0, stats=stats, zone_stats=[],
            quality_gate_label='pass', quality_gate_criteria={},
        )
        storage.backtests().insert(r)
    assert len(storage.backtests().list_all(limit=2)) == 2


def test_get_api_backtests_no_filter_returns_global_list(observability_storage, client):
    """GET /api/backtests without agent_id should now return all (200), not 400."""
    import storage
    from backtest.base import BacktestResult, BacktestStats
    storage.backtests().create_session('s', '2025-01-01', '2025-01-10', ['a'])
    stats = BacktestStats(sharpe=0, max_drawdown_pct=0, trade_count=0,
                          win_rate=0, max_daily_loss_pct=0,
                          total_return_pct=0, final_equity=100_000)
    r = BacktestResult(
        id='rg1', session_id='s', agent_id='ag-1',
        persona_id=None, model_id=None,
        start_date='2025-01-01', end_date='2025-01-10',
        initial_capital=100_000.0, stats=stats, zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
    )
    storage.backtests().insert(r)

    resp = client.get('/api/backtests')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    ids = [d['id'] for d in data]
    assert 'rg1' in ids


def test_get_api_backtests_agent_id_filter_still_works(observability_storage, client):
    """Backward compat — ?agent_id= still filters."""
    import storage
    from backtest.base import BacktestResult, BacktestStats
    storage.backtests().create_session('s', '2025-01-01', '2025-01-10', ['x'])
    stats = BacktestStats(sharpe=0, max_drawdown_pct=0, trade_count=0,
                          win_rate=0, max_daily_loss_pct=0,
                          total_return_pct=0, final_equity=100_000)
    for i, aid in enumerate(['ag-X', 'ag-Y']):
        r = BacktestResult(
            id=f'rf{i}', session_id='s', agent_id=aid,
            persona_id=None, model_id=None,
            start_date='2025-01-01', end_date='2025-01-10',
            initial_capital=100_000.0, stats=stats, zone_stats=[],
            quality_gate_label='pass', quality_gate_criteria={},
        )
        storage.backtests().insert(r)
    resp = client.get('/api/backtests?agent_id=ag-Y')
    assert resp.status_code == 200
    data = resp.get_json()
    ids = [d['id'] for d in data]
    assert ids == ['rf1']  # only the matching one
