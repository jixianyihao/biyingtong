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


# ─── edge cases: monthly returns ──────────────────────────────────────────

def test_compute_monthly_returns_zero_equity_first_day():
    """First-of-month equity == 0 → return_pct defaults to 0, no ZeroDivisionError."""
    from backtest.stats import compute_monthly_returns
    records = [
        {'date': '2025-03-03', 'equity': 0.0},       # first in bucket
        {'date': '2025-03-10', 'equity': 50_000.0},  # non-zero later
        {'date': '2025-03-28', 'equity': 75_000.0},  # last in bucket
    ]
    out = compute_monthly_returns(records)
    assert len(out) == 1
    # first_equity == 0 → guard clause returns 0.0 instead of dividing
    assert out[0]['return_pct'] == 0.0
    assert out[0]['days'] == 3


def test_compute_monthly_returns_out_of_order_input_still_groups():
    """Input records not in date order still bucket by (year, month).

    Note the docstring says "Monthly return = (last / first - 1) * 100" where
    first = first record seen in the bucket (not the chronologically earliest).
    We verify grouping is correct regardless of input order.
    """
    from backtest.stats import compute_monthly_returns
    records = [
        {'date': '2025-01-31', 'equity': 110_000.0},
        {'date': '2025-01-02', 'equity': 100_000.0},  # out of order
        {'date': '2025-01-15', 'equity': 105_000.0},
    ]
    out = compute_monthly_returns(records)
    assert len(out) == 1
    assert out[0]['year'] == 2025
    assert out[0]['month'] == 1
    assert out[0]['days'] == 3


def test_compute_monthly_returns_unsorted_input():
    """Out-of-order daily_records should still give chronologically-correct monthly returns.

    Regression guard — previously first_equity_of_month was set by first-seen-in-bucket
    order, not by actual calendar date. When records arrive unsorted (parallel multi-agent
    runs, or reconstruction from SQLite without ORDER BY), this produced wrong return_pct.
    """
    from backtest.stats import compute_monthly_returns
    records = [
        # Deliberately out-of-order: Feb-15 before Feb-01
        {'date': '2025-02-15', 'equity': 105_000.0},
        {'date': '2025-02-01', 'equity': 100_000.0},  # chronological first
        {'date': '2025-02-28', 'equity': 110_000.0},  # chronological last
    ]
    out = compute_monthly_returns(records)
    assert len(out) == 1
    # Correct = (110_000 / 100_000 - 1) * 100 = 10.0
    # Buggy would = (110_000 / 105_000 - 1) * 100 ≈ 4.76
    assert abs(out[0]['return_pct'] - 10.0) < 0.01
    assert out[0]['days'] == 3


# ─── edge cases: cancel semantics ─────────────────────────────────────────

def test_cancel_job_returns_false_for_failed_state():
    """cancel() on a job in 'failed' terminal state returns False."""
    from backtest.jobs import JobStatus, _jobs, _lock, cancel
    s = JobStatus(session_id='s-cancel-failed', state='failed')
    with _lock:
        _jobs['s-cancel-failed'] = s
    try:
        assert cancel('s-cancel-failed') is False
        # cancel_requested must not be flipped on a terminal job
        assert s.cancel_requested is False
    finally:
        with _lock:
            _jobs.pop('s-cancel-failed', None)


def test_cancel_job_idempotent_on_already_cancelled():
    """cancel() on a job already in 'cancelled' state returns False (terminal)."""
    from backtest.jobs import JobStatus, _jobs, _lock, cancel
    s = JobStatus(session_id='s-cancel-dup', state='cancelled')
    with _lock:
        _jobs['s-cancel-dup'] = s
    try:
        assert cancel('s-cancel-dup') is False
    finally:
        with _lock:
            _jobs.pop('s-cancel-dup', None)


# ─── edge cases: delete leaves siblings intact ────────────────────────────

def test_delete_one_of_two_results_in_same_session_leaves_other(
    observability_storage,
):
    """Delete one backtest in a multi-agent session; siblings still queryable
    via list_for_session()."""
    import storage
    from backtest.base import BacktestResult, BacktestStats
    storage.backtests().create_session(
        's-pair', '2025-01-01', '2025-01-10', ['a1', 'a2'],
    )
    stats = BacktestStats(sharpe=0, max_drawdown_pct=0, trade_count=0,
                          win_rate=0, max_daily_loss_pct=0,
                          total_return_pct=0, final_equity=100_000)
    for rid, aid in [('r-pair-1', 'a1'), ('r-pair-2', 'a2')]:
        storage.backtests().insert(BacktestResult(
            id=rid, session_id='s-pair', agent_id=aid,
            persona_id=None, model_id=None,
            start_date='2025-01-01', end_date='2025-01-10',
            initial_capital=100_000.0, stats=stats, zone_stats=[],
            quality_gate_label='pass', quality_gate_criteria={},
        ))
    assert len(storage.backtests().list_for_session('s-pair')) == 2

    assert storage.backtests().delete('r-pair-1') is True

    remaining = storage.backtests().list_for_session('s-pair')
    assert len(remaining) == 1
    assert remaining[0].id == 'r-pair-2'
    # And direct-get still works for the survivor
    assert storage.backtests().get('r-pair-2') is not None
    assert storage.backtests().get('r-pair-1') is None


# ─── edge case: cancel_check mid-flight produces partial daily_records ────

def test_backtest_runner_cancel_check_produces_partial_daily_records(
    observability_storage, monkeypatch,
):
    """BacktestRunner honours cancel_check — loop aborts after current day and
    the result carries a *partial* daily_records list (not empty, not full).

    Note: this test exercises the runner's cancel_check parameter directly;
    it does NOT go through the jobs.py worker thread.
    """
    from datetime import date, timedelta
    import storage
    from backtest.runner import BacktestRunner
    import backtest.runner as runner_mod
    from llm.mock import MockLLM

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-cancel', initial_capital=1_000_000.0,
    )

    days = [date(2025, 1, 2) + timedelta(days=i) for i in range(7)]
    bars = [(d, 100.0 + i * 0.2) for i, d in enumerate(days)]
    monkeypatch.setattr(runner_mod, '_load_daily_closes',
                        lambda code, start, end: bars)
    monkeypatch.setattr(runner_mod, '_trading_days',
                        lambda start, end: days)

    # Hold every day — the loop will break on cancel before all 7 days run.
    hold = {'tool_calls': [{'id': 'h', 'name': 'place_decision',
                            'input': {'action': 'hold',
                                      'reason': 'holding for clarity today',
                                      'thinking': 'holding'}}],
            'stop_reason': 'tool_use'}
    llm = MockLLM([hold] * 7)

    calls = {'n': 0}
    def _cancel_after_2():
        # Called at end of each iteration. Flip to True after the 2nd check.
        calls['n'] += 1
        return calls['n'] >= 2

    r = BacktestRunner(llm=llm).run(
        session_id='s-cancel-mid', agent_id=agent.id,
        start_date='2025-01-02', end_date='2025-01-08',
        universe=['600519.SH'],
        cancel_check=_cancel_after_2,
    )
    # Loop breaks mid-flight → strictly fewer records than the 7-day window.
    assert 0 < len(r.daily_records) < 7
    # First partial record is still well-formed
    rec0 = r.daily_records[0]
    assert 'date' in rec0 and 'equity' in rec0
