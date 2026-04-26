"""GET /api/backtests/sessions returns recent sessions with counts."""
import pytest


def _fresh_app():
    from flask import Flask
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def wired(tmp_path):
    import storage
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    for cls, setter in [
        (SQLiteBacktestResultStore, 'set_backtests'),
        (SQLiteBaselineResultStore, 'set_baselines'),
    ]:
        inst = cls(tmp_path=tmp_path); inst.init_schema()
        getattr(storage, setter)(inst)
    return storage


@pytest.fixture
def client(wired):
    return _fresh_app().test_client()


def test_empty_sessions(client):
    resp = client.get('/api/backtests/sessions')
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_sessions_populated(client, wired):
    from backtest.base import BacktestStats, BacktestResult
    from backtest.baselines.base import BaselineResult
    wired.backtests().create_session('s1', '2025-11-17', '2025-11-28',
                                     ['a1', 'a2'], notes='head-to-head')
    wired.backtests().create_session('s2', '2025-11-01', '2025-11-10',
                                     ['a1'])
    # Insert results so counts > 0
    stats = BacktestStats(sharpe=1.0, max_drawdown_pct=-5.0, trade_count=3,
                          win_rate=66.7, max_daily_loss_pct=-1.2,
                          total_return_pct=2.5, final_equity=1_025_000)
    wired.backtests().insert(BacktestResult(
        id='r1', session_id='s1', agent_id='a1',
        persona_id='quant_neutral', model_id='claude-opus-4-7',
        start_date='2025-11-17', end_date='2025-11-28',
        initial_capital=1_000_000, stats=stats, zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        final_equity=1_025_000,
    ))
    wired.baselines().insert(BaselineResult(
        id='b1', session_id='s1', name='buy_and_hold',
        start_date='2025-11-17', end_date='2025-11-28',
        initial_capital=1_000_000, stats=stats, final_equity=985_000,
    ))

    resp = client.get('/api/backtests/sessions')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    # Most recent first
    assert data[0]['session_id'] in ('s1', 's2')
    # Find s1
    s1 = next(d for d in data if d['session_id'] == 's1')
    assert s1['agent_count'] == 1
    assert s1['baseline_count'] == 1
    assert s1['agent_ids'] == ['a1', 'a2']
    assert s1['notes'] == 'head-to-head'
