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
