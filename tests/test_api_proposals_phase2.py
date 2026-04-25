"""P3-F Phase 2 Task 6 — approve endpoint dispatches to ExecutionAdapter."""
from __future__ import annotations

import importlib

import pytest
from flask import Flask


def _fresh_flask_app():
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def deploy_storage(tmp_path):
    """tmp_path-scoped proposals + deployed_agents stores. Mirrors
    tests/test_p3f_phase1.py::deploy_storage but without the full
    observability fixture dependency (not needed for Phase 2)."""
    import storage
    from storage.sqlite_proposals import SQLiteTradeProposalStore
    from storage.sqlite_deployed_agents import SQLiteDeployedAgentStore

    storage.reset()
    p = SQLiteTradeProposalStore(tmp_path=tmp_path)
    p.init_schema()
    storage.set_proposals(p)

    d = SQLiteDeployedAgentStore(tmp_path=tmp_path)
    d.init_schema()
    storage.set_deployed_agents(d)
    return tmp_path


@pytest.fixture
def client(deploy_storage):
    app = _fresh_flask_app()
    with app.test_client() as c:
        yield c


@pytest.fixture
def seeded_pending_proposal(deploy_storage):
    import storage
    from storage.base import TradeProposal
    p = TradeProposal(
        id='p2-1', agent_id='a-1',
        decision_at='2026-04-24T09:30:00', action='buy',
        code='600519.SH', shares=100, price=237.5,
        reason='r', thinking='t', status='pending',
    )
    storage.proposals().insert(p)
    return p


# ─── approve dispatches to adapter ─────────────────────────────────────


def test_approve_dry_run_mode_persists_execution_result(
    client, monkeypatch, seeded_pending_proposal,
):
    # Default env (no BIYINGTONG_EXECUTION_MODE) → dry_run
    monkeypatch.delenv('BIYINGTONG_EXECUTION_MODE', raising=False)
    import execution
    importlib.reload(execution)

    resp = client.post(f'/api/proposals/{seeded_pending_proposal.id}/approve')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['status'] == 'approved'
    assert body['decided_by'] == 'user'
    assert body['execution_mode'] == 'dry_run'
    assert body['execution_order_id'] is not None
    assert body['execution_order_id'].startswith('mock-')
    assert body['filled_qty'] == seeded_pending_proposal.shares
    assert body['filled_price'] == seeded_pending_proposal.price
    assert body['execution_error'] is None
    assert body['executed_at'] is not None


def test_approve_live_mode_calls_tdx(client, monkeypatch, seeded_pending_proposal):
    import tdx_service
    monkeypatch.setenv('BIYINGTONG_EXECUTION_MODE', 'live')
    calls = []

    def _fake_place(**kw):
        calls.append(kw)
        return {'order_id': 'tdx-999'}

    monkeypatch.setattr(tdx_service.tdx, 'place_order', _fake_place)
    import execution
    importlib.reload(execution)

    resp = client.post(f'/api/proposals/{seeded_pending_proposal.id}/approve')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['status'] == 'approved'
    assert body['execution_mode'] == 'live'
    assert body['execution_order_id'] == 'tdx-999'
    assert body['execution_error'] is None
    assert len(calls) == 1
    # verify adapter forwarded proposal fields
    assert calls[0]['stock_code'] == '600519.SH'
    assert calls[0]['side'] == 'buy'
    assert calls[0]['qty'] == 100
    assert calls[0]['price'] == 237.5


def test_approve_live_mode_handles_tdx_error(
    client, monkeypatch, seeded_pending_proposal,
):
    import tdx_service
    monkeypatch.setenv('BIYINGTONG_EXECUTION_MODE', 'live')
    monkeypatch.setattr(tdx_service.tdx, 'place_order',
                        lambda **kw: {'error': 'insufficient funds'})
    import execution
    importlib.reload(execution)

    resp = client.post(f'/api/proposals/{seeded_pending_proposal.id}/approve')
    # approved + execution failed — still 200; UI surfaces the error
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['status'] == 'approved'
    assert body['execution_mode'] == 'live'
    assert body['execution_error'] == 'insufficient funds'
    assert body['execution_order_id'] is None
    assert body['filled_qty'] == 0


def test_approve_already_decided_returns_409(client, seeded_pending_proposal):
    # first approve: 200
    r1 = client.post(f'/api/proposals/{seeded_pending_proposal.id}/approve')
    assert r1.status_code == 200
    # second approve on same proposal: 409
    r2 = client.post(f'/api/proposals/{seeded_pending_proposal.id}/approve')
    assert r2.status_code == 409


# ─── poll_status + cancel (Phase 25 polish) ────────────────────────────


@pytest.fixture
def seeded_approved_proposal(deploy_storage):
    """Approved proposal already through dry-run execution dispatch."""
    import storage
    from storage.base import TradeProposal
    p = TradeProposal(
        id='p2-approved-1', agent_id='a-1',
        decision_at='2026-04-24T09:30:00', action='buy',
        code='600519.SH', shares=100, price=237.5,
        reason='r', thinking='t', status='approved',
        decided_by='user', decided_at='2026-04-24T09:31:00',
    )
    storage.proposals().insert(p)
    storage.proposals().update_status('p2-approved-1', 'approved',
                                      decided_by='user')
    storage.proposals().update_execution(
        'p2-approved-1',
        execution_mode='dry_run',
        execution_order_id='mock-abc123def456',
        execution_error=None,
        filled_qty=100,
        filled_price=237.5,
        executed_at='2026-04-24T09:31:01',
    )
    return storage.proposals().get('p2-approved-1')


def test_poll_status_updates_execution_fields(
    client, monkeypatch, seeded_approved_proposal,
):
    monkeypatch.delenv('BIYINGTONG_EXECUTION_MODE', raising=False)
    import execution
    importlib.reload(execution)

    resp = client.post(
        f'/api/proposals/{seeded_approved_proposal.id}/poll_status'
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['status'] == 'approved'
    assert body['execution_mode'] == 'dry_run'
    # Mock echoes existing order_id
    assert body['execution_order_id'] == 'mock-abc123def456'
    assert body['filled_qty'] == 100
    assert body['filled_price'] == 237.5
    assert body['execution_error'] is None
    # executed_at should refresh (different from the seeded value)
    assert body['executed_at'] is not None


def test_poll_status_404_on_unknown(client):
    resp = client.post('/api/proposals/does-not-exist/poll_status')
    assert resp.status_code == 404


def test_poll_status_409_when_pending(client, seeded_pending_proposal):
    resp = client.post(
        f'/api/proposals/{seeded_pending_proposal.id}/poll_status'
    )
    assert resp.status_code == 409
    body = resp.get_json()
    assert 'pending' in body.get('error', '').lower()


def test_cancel_updates_execution_with_cancelled_prefix(
    client, monkeypatch, seeded_approved_proposal,
):
    monkeypatch.delenv('BIYINGTONG_EXECUTION_MODE', raising=False)
    import execution
    importlib.reload(execution)

    resp = client.post(f'/api/proposals/{seeded_approved_proposal.id}/cancel')
    assert resp.status_code == 200
    body = resp.get_json()
    # status stays 'approved' (the *proposal* wasn't reverted)
    assert body['status'] == 'approved'
    assert body['execution_mode'] == 'dry_run'
    assert body['execution_order_id'] == 'cancelled-mock-abc123def456'
    assert body['filled_qty'] == 0
    assert body['filled_price'] == 0.0
    assert body['execution_error'] is None


def test_cancel_409_when_pending(client, seeded_pending_proposal):
    resp = client.post(f'/api/proposals/{seeded_pending_proposal.id}/cancel')
    assert resp.status_code == 409


def test_cancel_404_on_unknown(client):
    resp = client.post('/api/proposals/no-such-id/cancel')
    assert resp.status_code == 404


# ─── GET /api/execution/mode ───────────────────────────────────────────


def test_execution_mode_endpoint(client, monkeypatch):
    monkeypatch.delenv('BIYINGTONG_EXECUTION_MODE', raising=False)
    import execution
    importlib.reload(execution)
    resp = client.get('/api/execution/mode')
    assert resp.status_code == 200
    assert resp.get_json() == {'mode': 'dry_run'}

    monkeypatch.setenv('BIYINGTONG_EXECUTION_MODE', 'live')
    importlib.reload(execution)
    resp = client.get('/api/execution/mode')
    assert resp.status_code == 200
    assert resp.get_json() == {'mode': 'live'}
