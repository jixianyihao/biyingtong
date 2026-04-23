"""Async backtest job tracker."""
import time
import pytest


@pytest.fixture(autouse=True)
def _clear_jobs():
    from backtest import jobs
    with jobs._lock:
        jobs._jobs.clear()
    yield
    with jobs._lock:
        jobs._jobs.clear()


def test_unknown_session_returns_none():
    from backtest.jobs import get_status
    assert get_status('nope') is None


def test_submit_tracks_status(monkeypatch):
    from backtest import jobs

    # Stub run_multi + run_all so the thread returns fast
    class _FakeResult:
        def __init__(self, id): self.id = id

    def fake_run_multi(**kw):
        return [_FakeResult(f'r-{aid}') for aid in [c['agent_id'] for c in kw['agent_configs']]]

    def fake_run_all(**kw):
        return [_FakeResult('b1'), _FakeResult('b2'), _FakeResult('b3')]

    from backtest import multi_agent_runner as mar
    from backtest.baselines import runner as brun
    monkeypatch.setattr(mar, 'run_multi', fake_run_multi)
    monkeypatch.setattr(brun, 'run_all', fake_run_all)

    # Stub build_llm — no env vars in tests
    from llm import factory
    monkeypatch.setattr(factory, 'build_llm', lambda mid: object())

    # Stub agents().get — return something with .model_id
    import storage
    class _FakeAgent:
        def __init__(self, mid): self.model_id = mid
    class _FakeStore:
        def get(self, aid):
            return _FakeAgent('mock-model')
    storage.set_agents(_FakeStore())

    st = jobs.submit_backtest(
        session_id='s1', agent_ids=['a1', 'a2'],
        start_date='2025-11-17', end_date='2025-11-28',
        initial_capital=1_000_000.0, universe=['X.SH'],
    )
    assert st.state in ('queued', 'running')

    # Wait up to 5s for completion
    for _ in range(50):
        s = jobs.get_status('s1')
        if s.state in ('complete', 'failed'):
            break
        time.sleep(0.1)

    final = jobs.get_status('s1')
    assert final.state == 'complete', f'error: {final.error}'
    assert len(final.agent_result_ids) == 2
    assert len(final.baseline_result_ids) == 3


def test_submit_failure_captured(monkeypatch):
    from backtest import jobs
    from llm import factory

    def boom(mid):
        raise RuntimeError('no llm configured')
    monkeypatch.setattr(factory, 'build_llm', boom)

    import storage
    class _FakeAgent:
        model_id = 'm'
    class _FakeStore:
        def get(self, aid): return _FakeAgent()
    storage.set_agents(_FakeStore())

    jobs.submit_backtest(
        session_id='s2', agent_ids=['a1'],
        start_date='2025-11-17', end_date='2025-11-28',
        initial_capital=1_000_000.0, universe=['X.SH'],
    )
    for _ in range(50):
        s = jobs.get_status('s2')
        if s.state in ('complete', 'failed'):
            break
        time.sleep(0.1)
    final = jobs.get_status('s2')
    assert final.state == 'failed'
    assert 'no llm configured' in (final.error or '')


def test_list_jobs(monkeypatch):
    from backtest import jobs

    import storage
    class _FakeAgent:
        model_id = 'm'
    class _FakeStore:
        def get(self, aid): return _FakeAgent()
    storage.set_agents(_FakeStore())

    class _FakeResult:
        def __init__(self, id): self.id = id
    from backtest import multi_agent_runner as mar
    from backtest.baselines import runner as brun
    from llm import factory
    monkeypatch.setattr(factory, 'build_llm', lambda mid: object())
    monkeypatch.setattr(mar, 'run_multi', lambda **kw: [_FakeResult('r1')])
    monkeypatch.setattr(brun, 'run_all', lambda **kw: [])

    jobs.submit_backtest(session_id='a', agent_ids=['a1'],
                         start_date='2025-11-17', end_date='2025-11-20',
                         initial_capital=1_000_000.0, universe=['X.SH'])
    jobs.submit_backtest(session_id='b', agent_ids=['a2'],
                         start_date='2025-11-17', end_date='2025-11-20',
                         initial_capital=1_000_000.0, universe=['X.SH'])
    time.sleep(0.5)
    all_jobs = jobs.list_jobs()
    assert len(all_jobs) == 2
    assert {j.session_id for j in all_jobs} == {'a', 'b'}
