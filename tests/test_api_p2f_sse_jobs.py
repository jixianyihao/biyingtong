"""SSE stream for backtest jobs — basic shape + done event."""
import time
import pytest


def _fresh_app():
    from flask import Flask
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture(autouse=True)
def _clear_jobs():
    from backtest import jobs
    with jobs._lock:
        jobs._jobs.clear()
    yield
    with jobs._lock:
        jobs._jobs.clear()


@pytest.fixture
def client():
    return _fresh_app().test_client()


def test_stream_notfound_emits_event(client):
    """Unknown session_id streams a notfound event and closes."""
    resp = client.get('/api/backtests/jobs/nonexistent/stream')
    assert resp.status_code == 200
    assert 'text/event-stream' in resp.content_type
    body = b''.join(resp.response).decode('utf-8', errors='replace')
    assert 'event: notfound' in body


def test_stream_emits_initial_state_then_done(client):
    """Create a pre-completed job then stream — should see state then done event."""
    from backtest.jobs import JobStatus, _jobs, _lock
    status = JobStatus(
        session_id='s-done', state='complete', progress='finished',
        agent_ids=['a1'], agent_result_ids=['r1'],
    )
    status.started_at = time.time() - 60
    status.finished_at = time.time()
    with _lock:
        _jobs['s-done'] = status
    resp = client.get('/api/backtests/jobs/s-done/stream')
    body = b''.join(resp.response).decode('utf-8', errors='replace')
    assert 'data:' in body
    assert 'complete' in body
    assert 'event: done' in body
