"""POST /api/backtests async kickoff + status polling."""
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
def wired(tmp_path):
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.sqlite_audit import SQLiteAuditStore
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    from storage.sqlite_personas import SQLitePersonaStore
    from storage.sqlite_agents import SQLiteAgentStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    from storage.sqlite_models import SQLiteModelStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    for cls, setter in [
        (SQLiteRedLineStore, 'set_redline'),
        (SQLiteStockStatusStore, 'set_stock_status'),
        (SQLiteAuditStore, 'set_audit'),
        (SQLiteLLMDecisionCache, 'set_llm_cache'),
        (SQLitePersonaStore, 'set_personas'),
        (SQLiteAgentStore, 'set_agents'),
        (SQLitePromptVersionStore, 'set_prompt_versions'),
        (SQLiteModelStore, 'set_models'),
        (SQLiteBacktestResultStore, 'set_backtests'),
        (SQLiteBaselineResultStore, 'set_baselines'),
    ]:
        inst = cls(tmp_path=tmp_path); inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()
    from personas import seed as seed_personas
    seed_personas()
    from backtest import jobs
    with jobs._lock:
        jobs._jobs.clear()
    return storage


@pytest.fixture
def client(wired):
    return _fresh_app().test_client()


@pytest.fixture
def agent(wired):
    return wired.agents().create_from_persona(
        persona_id='quant_neutral', model_id='claude-opus-4-7',
        display_name='Async-Test',
    )


def test_post_backtest_requires_fields(client):
    resp = client.post('/api/backtests', json={})
    assert resp.status_code == 400


def test_post_backtest_unknown_agent(client):
    resp = client.post('/api/backtests', json={
        'agent_ids': ['nope'],
        'start_date': '2025-11-17', 'end_date': '2025-11-28',
        'initial_capital': 1_000_000.0, 'universe': ['X.SH'],
    })
    assert resp.status_code == 404


def test_post_backtest_returns_accepted(client, agent, monkeypatch):
    """Posting succeeds with 202 and a session_id; job then runs to failure
    because no LLM env vars — that's expected in CI."""
    resp = client.post('/api/backtests', json={
        'agent_ids': [agent.id],
        'start_date': '2025-11-17', 'end_date': '2025-11-28',
        'initial_capital': 1_000_000.0, 'universe': ['600519.SH'],
        'include_baselines': False,
    })
    assert resp.status_code == 202
    body = resp.get_json()
    assert 'session_id' in body
    assert body['state'] in ('queued', 'running', 'failed', 'complete')


def test_get_job_not_found(client):
    resp = client.get('/api/backtests/jobs/nope')
    assert resp.status_code == 404


def test_job_status_polling(client, agent, monkeypatch):
    """Kick off a job with mocked-out runner + LLM, then poll until done."""
    # Stub build_llm
    from llm import factory
    monkeypatch.setattr(factory, 'build_llm', lambda mid: object())

    # Stub run_multi + run_all so the job completes fast
    class _FakeResult:
        def __init__(self, id): self.id = id

    from backtest import multi_agent_runner as mar
    from backtest.baselines import runner as brun
    monkeypatch.setattr(mar, 'run_multi',
                        lambda **kw: [_FakeResult(f'r-{aid}')
                                      for aid in [c['agent_id']
                                                  for c in kw['agent_configs']]])
    monkeypatch.setattr(brun, 'run_all',
                        lambda **kw: [_FakeResult('b1'), _FakeResult('b2'),
                                      _FakeResult('b3')])

    resp = client.post('/api/backtests', json={
        'agent_ids': [agent.id],
        'start_date': '2025-11-17', 'end_date': '2025-11-20',
        'initial_capital': 1_000_000.0, 'universe': ['600519.SH'],
    })
    session_id = resp.get_json()['session_id']

    for _ in range(50):
        pr = client.get(f'/api/backtests/jobs/{session_id}')
        data = pr.get_json()
        if data['state'] in ('complete', 'failed'):
            break
        time.sleep(0.1)

    final = client.get(f'/api/backtests/jobs/{session_id}').get_json()
    assert final['state'] == 'complete', f'error: {final.get("error")}'
    assert len(final['agent_result_ids']) == 1
    assert len(final['baseline_result_ids']) == 3


def test_list_jobs(client, agent, monkeypatch):
    from llm import factory
    from backtest import multi_agent_runner as mar
    from backtest.baselines import runner as brun

    class _FakeResult:
        def __init__(self, id): self.id = id

    monkeypatch.setattr(factory, 'build_llm', lambda mid: object())
    monkeypatch.setattr(mar, 'run_multi', lambda **kw: [_FakeResult('r1')])
    monkeypatch.setattr(brun, 'run_all', lambda **kw: [])

    client.post('/api/backtests', json={
        'agent_ids': [agent.id], 'start_date': '2025-11-17',
        'end_date': '2025-11-20', 'initial_capital': 1_000_000.0,
        'universe': ['X.SH'], 'include_baselines': False,
    })
    resp = client.get('/api/backtests/jobs')
    assert resp.status_code == 200
    jobs_list = resp.get_json()
    assert len(jobs_list) >= 1
