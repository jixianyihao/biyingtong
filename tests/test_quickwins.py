"""P3-finish quickwins: monthly returns + cancel job + delete backtest."""
from __future__ import annotations

import pytest


# ─── monthly returns ──────────────────────────────────────────────────────

def test_compute_monthly_returns_empty():
    from backtest.stats import compute_monthly_returns
    assert compute_monthly_returns([]) == []


def test_compute_monthly_returns_single_month():
    from backtest.stats import compute_monthly_returns
    records = [
        {'date': '2025-01-02', 'equity': 100_000.0},
        {'date': '2025-01-15', 'equity': 105_000.0},
        {'date': '2025-01-31', 'equity': 110_000.0},
    ]
    out = compute_monthly_returns(records)
    assert len(out) == 1
    assert out[0]['year'] == 2025
    assert out[0]['month'] == 1
    assert abs(out[0]['return_pct'] - 10.0) < 0.01
    assert out[0]['days'] == 3


def test_compute_monthly_returns_multi_month_sorted():
    from backtest.stats import compute_monthly_returns
    records = [
        {'date': '2025-01-02', 'equity': 100_000.0},
        {'date': '2025-01-31', 'equity': 110_000.0},
        {'date': '2025-02-03', 'equity': 110_000.0},
        {'date': '2025-02-28', 'equity': 99_000.0},  # -10%
    ]
    out = compute_monthly_returns(records)
    assert len(out) == 2
    assert out[0]['year'] == 2025 and out[0]['month'] == 1
    assert abs(out[0]['return_pct'] - 10.0) < 0.01
    assert out[1]['year'] == 2025 and out[1]['month'] == 2
    assert abs(out[1]['return_pct'] - (-10.0)) < 0.01


# ─── delete backtest ──────────────────────────────────────────────────────

def test_backtest_store_delete_removes_row(observability_storage):
    import storage
    from backtest.base import BacktestResult, BacktestStats
    storage.backtests().create_session('s', '2025-01-01', '2025-01-10', ['a'])
    stats = BacktestStats(sharpe=0, max_drawdown_pct=0, trade_count=0,
                          win_rate=0, max_daily_loss_pct=0,
                          total_return_pct=0, final_equity=100_000)
    r = BacktestResult(
        id='rdel', session_id='s', agent_id='a',
        persona_id=None, model_id=None,
        start_date='2025-01-01', end_date='2025-01-10',
        initial_capital=100_000.0, stats=stats, zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
    )
    storage.backtests().insert(r)
    assert storage.backtests().delete('rdel') is True
    assert storage.backtests().get('rdel') is None


def test_backtest_store_delete_nonexistent_returns_false(observability_storage):
    import storage
    assert storage.backtests().delete('nope') is False


# ─── HTTP endpoints ───────────────────────────────────────────────────────

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


def test_get_monthly_returns_endpoint(observability_storage, client):
    import storage
    from backtest.base import BacktestResult, BacktestStats
    storage.backtests().create_session('s-mr', '2025-01-01', '2025-02-28', ['a'])
    stats = BacktestStats(sharpe=0, max_drawdown_pct=0, trade_count=0,
                          win_rate=0, max_daily_loss_pct=0,
                          total_return_pct=0, final_equity=110_000)
    r = BacktestResult(
        id='rmr', session_id='s-mr', agent_id='a',
        persona_id=None, model_id=None,
        start_date='2025-01-01', end_date='2025-02-28',
        initial_capital=100_000.0, stats=stats, zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        daily_records=[
            {'date': '2025-01-02', 'equity': 100_000.0},
            {'date': '2025-01-31', 'equity': 110_000.0},
            {'date': '2025-02-28', 'equity': 99_000.0},
        ],
    )
    storage.backtests().insert(r)
    resp = client.get('/api/backtests/rmr/monthly_returns')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['result_id'] == 'rmr'
    assert len(data['monthly_returns']) == 2


def test_get_monthly_returns_404(observability_storage, client):
    resp = client.get('/api/backtests/nope/monthly_returns')
    assert resp.status_code == 404


def test_delete_backtest_endpoint(observability_storage, client):
    import storage
    from backtest.base import BacktestResult, BacktestStats
    storage.backtests().create_session('s-d', '2025-01-01', '2025-01-10', ['a'])
    stats = BacktestStats(sharpe=0, max_drawdown_pct=0, trade_count=0,
                          win_rate=0, max_daily_loss_pct=0,
                          total_return_pct=0, final_equity=100_000)
    r = BacktestResult(
        id='rd-api', session_id='s-d', agent_id='a',
        persona_id=None, model_id=None,
        start_date='2025-01-01', end_date='2025-01-10',
        initial_capital=100_000.0, stats=stats, zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
    )
    storage.backtests().insert(r)
    resp = client.delete('/api/backtests/rd-api')
    assert resp.status_code == 204
    assert storage.backtests().get('rd-api') is None


def test_delete_backtest_404(observability_storage, client):
    resp = client.delete('/api/backtests/nope')
    assert resp.status_code == 404


def test_cancel_job_marks_cancel_requested():
    """jobs.cancel(sid) sets cancel_requested + returns True."""
    from backtest.jobs import JobStatus, _jobs, _lock, cancel
    s = JobStatus(session_id='s-cancel-1', state='running')
    with _lock:
        _jobs['s-cancel-1'] = s
    assert cancel('s-cancel-1') is True
    assert s.cancel_requested is True
    # Cleanup
    with _lock:
        _jobs.pop('s-cancel-1', None)


def test_cancel_job_returns_false_for_terminal_state():
    from backtest.jobs import JobStatus, _jobs, _lock, cancel
    s = JobStatus(session_id='s-cancel-2', state='complete')
    with _lock:
        _jobs['s-cancel-2'] = s
    assert cancel('s-cancel-2') is False
    with _lock:
        _jobs.pop('s-cancel-2', None)


def test_cancel_endpoint(observability_storage, client):
    from backtest.jobs import JobStatus, _jobs, _lock
    s = JobStatus(session_id='s-cancel-api', state='running')
    with _lock:
        _jobs['s-cancel-api'] = s
    try:
        resp = client.post('/api/backtests/jobs/s-cancel-api/cancel')
        assert resp.status_code == 200
        assert s.cancel_requested is True
    finally:
        with _lock:
            _jobs.pop('s-cancel-api', None)


def test_cancel_endpoint_404(observability_storage, client):
    resp = client.post('/api/backtests/jobs/nope/cancel')
    assert resp.status_code == 404
