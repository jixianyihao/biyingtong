"""POST /api/backtests — engine='legacy' | 'vnpy' routing.

Covers Batch B Task 5/7:
- Default engine is 'legacy' (existing behavior preserved).
- engine='vnpy' returns 202 (accepted, not rejected).
- engine='<unknown>' returns 400.
"""
from __future__ import annotations

import time

import pytest


def _fresh_app():
    from flask import Flask
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(observability_storage):
    """Flask test client wired to seeded storage."""
    from backtest import jobs
    with jobs._lock:
        jobs._jobs.clear()
    return _fresh_app().test_client()


def test_submit_backtest_defaults_to_legacy(observability_storage, monkeypatch):
    """Default engine is 'legacy' — run_multi path is hit, vnpy path is not."""
    from backtest.jobs import submit_backtest
    captured: dict = {}

    def _fake_run_multi(**kwargs):
        captured['engine'] = 'legacy'
        captured['kwargs'] = kwargs
        return []

    import backtest.multi_agent_runner as mar
    monkeypatch.setattr(mar, 'run_multi', _fake_run_multi)
    import backtest.baselines.runner as bl
    monkeypatch.setattr(bl, 'run_all', lambda *a, **k: [])
    from llm import factory
    monkeypatch.setattr(factory, 'build_llm', lambda mid: object())

    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='eng-legacy', initial_capital=1_000_000.0,
    )

    submit_backtest(
        session_id='s-legacy', agent_ids=[agent.id],
        start_date='2025-01-01', end_date='2025-01-05',
        initial_capital=1_000_000.0, universe=['600519.SH'],
        include_baselines=False,
    )
    # Wait briefly for worker
    for _ in range(50):
        if captured:
            break
        time.sleep(0.1)
    assert captured.get('engine') == 'legacy'


def test_submit_backtest_vnpy_skips_run_multi(observability_storage, monkeypatch):
    """engine='vnpy' routes through VnpyBacktestRunner, never calls run_multi."""
    from backtest.jobs import submit_backtest
    tracker: dict = {'run_multi_called': False, 'vnpy_called': False}

    def _fake_run_multi(**kwargs):
        tracker['run_multi_called'] = True
        return []

    import backtest.multi_agent_runner as mar
    monkeypatch.setattr(mar, 'run_multi', _fake_run_multi)
    import backtest.baselines.runner as bl
    monkeypatch.setattr(bl, 'run_all', lambda *a, **k: [])
    from llm import factory
    monkeypatch.setattr(factory, 'build_llm', lambda mid: object())

    class _FakeVnpyResult:
        id = 'vr-1'

    class _FakeVnpyRunner:
        def __init__(self, *, llm):
            self._llm = llm

        def run(self, **kwargs):
            tracker['vnpy_called'] = True
            tracker['vnpy_kwargs'] = kwargs
            return _FakeVnpyResult()

    import backtest.vnpy_runner as vr
    monkeypatch.setattr(vr, 'VnpyBacktestRunner', _FakeVnpyRunner)

    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='eng-vnpy-sub', initial_capital=1_000_000.0,
    )

    submit_backtest(
        session_id='s-vnpy-sub', agent_ids=[agent.id],
        start_date='2025-01-01', end_date='2025-01-05',
        initial_capital=1_000_000.0, universe=['600519.SH'],
        include_baselines=False,
        engine='vnpy',
    )
    for _ in range(50):
        if tracker['vnpy_called']:
            break
        time.sleep(0.1)
    assert tracker['vnpy_called'] is True
    assert tracker['run_multi_called'] is False


def test_post_backtests_engine_vnpy_accepted(observability_storage, client, monkeypatch):
    """POST /api/backtests with engine='vnpy' returns 202 (routed, not rejected).

    The worker path is stubbed so the job runs to completion without touching
    real vnpy infrastructure.
    """
    from llm import factory
    monkeypatch.setattr(factory, 'build_llm', lambda mid: object())

    class _FakeVnpyResult:
        id = 'vr-accept'

    class _FakeVnpyRunner:
        def __init__(self, *, llm):
            pass

        def run(self, **kwargs):
            return _FakeVnpyResult()

    import backtest.vnpy_runner as vr
    monkeypatch.setattr(vr, 'VnpyBacktestRunner', _FakeVnpyRunner)

    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='eng-vnpy', initial_capital=1_000_000.0,
    )
    resp = client.post('/api/backtests', json={
        'agent_ids': [agent.id],
        'start_date': '2025-01-01', 'end_date': '2025-01-05',
        'initial_capital': 1_000_000.0, 'universe': ['600519.SH'],
        'include_baselines': False,
        'engine': 'vnpy',
    })
    assert resp.status_code == 202
    body = resp.get_json()
    assert 'session_id' in body


def test_post_backtests_engine_bad_rejected(observability_storage, client):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='eng-bad', initial_capital=1_000_000.0,
    )
    resp = client.post('/api/backtests', json={
        'agent_ids': [agent.id],
        'start_date': '2025-01-01', 'end_date': '2025-01-05',
        'initial_capital': 1_000_000.0, 'universe': ['600519.SH'],
        'engine': 'rocketship',
    })
    assert resp.status_code == 400
    body = resp.get_json()
    assert 'rocketship' in body.get('error', '')
