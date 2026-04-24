"""P3-F Phase 1 — deploy/proposal infrastructure (NO real-money execution)."""
from __future__ import annotations

import sqlite3
import pytest


def test_deployed_agents_schema_creates_table():
    from data_schema.deployment_state import SCHEMA_DEPLOYED_AGENTS
    con = sqlite3.connect(':memory:')
    con.executescript(SCHEMA_DEPLOYED_AGENTS)
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(deployed_agents)').fetchall()}
    con.close()
    assert cols == {'agent_id', 'pid', 'started_at', 'status', 'schedule'}


def test_trade_proposals_schema_creates_table():
    from data_schema.deployment_state import SCHEMA_TRADE_PROPOSALS
    con = sqlite3.connect(':memory:')
    con.executescript(SCHEMA_TRADE_PROPOSALS)
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(trade_proposals)').fetchall()}
    con.close()
    expected = {
        'id', 'agent_id', 'created_at', 'decision_at',
        'action', 'code', 'shares', 'price',
        'reason', 'thinking', 'status', 'decided_by', 'decided_at',
        # Phase 2 execution fields
        'execution_mode', 'execution_order_id', 'execution_error',
        'executed_at', 'filled_qty', 'filled_price',
    }
    assert cols == expected


def test_trade_proposal_dataclass_minimal():
    from storage.base import TradeProposal
    p = TradeProposal(
        id='p1', agent_id='a1',
        decision_at='2026-04-23T10:00:00',
        action='buy', status='pending',
    )
    assert p.id == 'p1'
    assert p.code is None
    assert p.shares is None
    assert p.status == 'pending'


def test_trade_proposal_dataclass_full():
    from storage.base import TradeProposal
    p = TradeProposal(
        id='p2', agent_id='a1',
        decision_at='2026-04-23T10:00:00',
        action='buy', status='pending',
        code='600519.SH', shares=100, price=1700.0,
        reason='value pick', thinking='thesis...',
    )
    assert p.code == '600519.SH'
    assert p.shares == 100
    assert p.price == 1700.0


def test_deployed_agent_dataclass():
    from storage.base import DeployedAgent
    d = DeployedAgent(
        agent_id='a1', pid=12345,
        started_at='2026-04-23T10:00:00',
        status='running', schedule='daily',
    )
    assert d.pid == 12345
    assert d.status == 'running'


def test_trade_proposal_store_protocol_methods_present():
    from storage.base import TradeProposalStore
    for m in ('init_schema', 'insert', 'get', 'list_pending',
              'list_for_agent', 'update_status'):
        assert m in dir(TradeProposalStore)


def test_deployed_agent_store_protocol_methods_present():
    from storage.base import DeployedAgentStore
    for m in ('init_schema', 'upsert', 'get', 'list_running',
              'mark_stopped', 'mark_crashed'):
        assert m in dir(DeployedAgentStore)


def test_sqlite_proposal_store_roundtrip(tmp_path):
    from storage.sqlite_proposals import SQLiteTradeProposalStore
    from storage.base import TradeProposal

    store = SQLiteTradeProposalStore(tmp_path=tmp_path)
    store.init_schema()
    p = TradeProposal(
        id='p1', agent_id='a1',
        decision_at='2026-04-23T10:00:00',
        action='buy', code='600519.SH', shares=100, price=1700.0,
        reason='x', thinking='y', status='pending',
    )
    store.insert(p)
    got = store.get('p1')
    assert got is not None
    assert got.id == 'p1'
    assert got.agent_id == 'a1'
    assert got.action == 'buy'
    assert got.shares == 100
    assert got.price == 1700.0


def test_sqlite_proposal_list_pending_filters_status(tmp_path):
    from storage.sqlite_proposals import SQLiteTradeProposalStore
    from storage.base import TradeProposal

    store = SQLiteTradeProposalStore(tmp_path=tmp_path)
    store.init_schema()
    for i, status in enumerate(['pending', 'pending', 'approved', 'rejected']):
        store.insert(TradeProposal(
            id=f'p{i}', agent_id='a1',
            decision_at='2026-04-23T10:00:00',
            action='buy', status=status,
        ))
    pending = store.list_pending()
    assert len(pending) == 2
    assert all(p.status == 'pending' for p in pending)


def test_sqlite_proposal_list_pending_filter_by_agent(tmp_path):
    from storage.sqlite_proposals import SQLiteTradeProposalStore
    from storage.base import TradeProposal

    store = SQLiteTradeProposalStore(tmp_path=tmp_path)
    store.init_schema()
    store.insert(TradeProposal(
        id='p1', agent_id='a1', decision_at='x',
        action='buy', status='pending',
    ))
    store.insert(TradeProposal(
        id='p2', agent_id='a2', decision_at='x',
        action='buy', status='pending',
    ))
    assert len(store.list_pending(agent_id='a1')) == 1
    assert len(store.list_pending(agent_id='a2')) == 1
    assert len(store.list_pending()) == 2


def test_sqlite_proposal_update_status_sets_decided(tmp_path):
    from storage.sqlite_proposals import SQLiteTradeProposalStore
    from storage.base import TradeProposal

    store = SQLiteTradeProposalStore(tmp_path=tmp_path)
    store.init_schema()
    store.insert(TradeProposal(
        id='p1', agent_id='a1', decision_at='x',
        action='buy', status='pending',
    ))
    assert store.update_status('p1', 'approved', decided_by='user') is True
    got = store.get('p1')
    assert got.status == 'approved'
    assert got.decided_by == 'user'
    assert got.decided_at is not None


def test_sqlite_proposal_update_status_missing_returns_false(tmp_path):
    from storage.sqlite_proposals import SQLiteTradeProposalStore
    store = SQLiteTradeProposalStore(tmp_path=tmp_path)
    store.init_schema()
    assert store.update_status('nope', 'approved') is False


def test_sqlite_deployed_agents_upsert_and_list_running(tmp_path):
    from storage.sqlite_deployed_agents import SQLiteDeployedAgentStore
    store = SQLiteDeployedAgentStore(tmp_path=tmp_path)
    store.init_schema()
    store.upsert('a1', pid=1234, schedule='daily')
    store.upsert('a2', pid=5678, schedule='intraday_5m')
    running = store.list_running()
    assert len(running) == 2
    by_agent = {d.agent_id: d for d in running}
    assert by_agent['a1'].pid == 1234
    assert by_agent['a2'].schedule == 'intraday_5m'


def test_sqlite_deployed_agents_mark_stopped_filters_out(tmp_path):
    from storage.sqlite_deployed_agents import SQLiteDeployedAgentStore
    store = SQLiteDeployedAgentStore(tmp_path=tmp_path)
    store.init_schema()
    store.upsert('a1', pid=1234, schedule='daily')
    store.upsert('a2', pid=5678, schedule='daily')
    store.mark_stopped('a1')
    running = store.list_running()
    assert {d.agent_id for d in running} == {'a2'}
    # a1 still retrievable via get()
    assert store.get('a1').status == 'stopped'


def test_sqlite_deployed_agents_mark_crashed(tmp_path):
    from storage.sqlite_deployed_agents import SQLiteDeployedAgentStore
    store = SQLiteDeployedAgentStore(tmp_path=tmp_path)
    store.init_schema()
    store.upsert('a1', pid=1234, schedule='daily')
    store.mark_crashed('a1')
    assert store.get('a1').status == 'crashed'
    assert store.list_running() == []


def test_storage_factory_proposals_and_deployed_agents_return_singletons(tmp_path):
    import storage
    storage.reset()
    p1 = storage.proposals()
    p2 = storage.proposals()
    assert p1 is p2  # singleton
    d1 = storage.deployed_agents()
    d2 = storage.deployed_agents()
    assert d1 is d2
    storage.reset()


def test_next_tick_daily_before_930():
    from datetime import datetime
    from runner.scheduler import next_tick
    now = datetime(2026, 4, 23, 8, 0)
    t = next_tick('daily', now)
    assert t == datetime(2026, 4, 23, 9, 30)


def test_next_tick_daily_after_930_goes_next_day():
    from datetime import datetime
    from runner.scheduler import next_tick
    now = datetime(2026, 4, 23, 10, 0)
    t = next_tick('daily', now)
    assert t == datetime(2026, 4, 24, 9, 30)


def test_next_tick_weekly_monday():
    from datetime import datetime
    from runner.scheduler import next_tick
    # 2026-04-23 is a Thursday. Next Monday 2026-04-27.
    now = datetime(2026, 4, 23, 10, 0)
    t = next_tick('weekly', now)
    assert t == datetime(2026, 4, 27, 9, 30)


def test_next_tick_weekly_same_day_early():
    """Monday before 9:30 → use today 9:30."""
    from datetime import datetime
    from runner.scheduler import next_tick
    # 2026-04-27 is Monday.
    now = datetime(2026, 4, 27, 7, 0)
    t = next_tick('weekly', now)
    assert t == datetime(2026, 4, 27, 9, 30)


def test_next_tick_intraday_5m_mid_morning():
    """At 10:02, next tick should be 10:05."""
    from datetime import datetime
    from runner.scheduler import next_tick
    now = datetime(2026, 4, 23, 10, 2)
    t = next_tick('intraday_5m', now)
    assert t == datetime(2026, 4, 23, 10, 5)


def test_next_tick_intraday_5m_lunch_break():
    """At 12:30 (lunch), next tick jumps to 13:00."""
    from datetime import datetime
    from runner.scheduler import next_tick
    now = datetime(2026, 4, 23, 12, 30)
    t = next_tick('intraday_5m', now)
    assert t == datetime(2026, 4, 23, 13, 0)


def test_next_tick_intraday_5m_after_close():
    """After 15:00, next tick is tomorrow 9:30."""
    from datetime import datetime
    from runner.scheduler import next_tick
    now = datetime(2026, 4, 23, 15, 5)
    t = next_tick('intraday_5m', now)
    assert t == datetime(2026, 4, 24, 9, 30)


def test_emit_proposal_posts_payload(monkeypatch):
    """emit_proposal POSTs to /api/proposals with expected payload shape."""
    from runner.proposal_emitter import emit_proposal

    class _FakeResp:
        status_code = 201
        def json(self):
            return {'ok': True}
        def raise_for_status(self):
            pass

    captured = {}
    def _fake_post(url, json=None, headers=None, timeout=None):
        captured['url'] = url
        captured['json'] = json
        captured['headers'] = headers
        return _FakeResp()

    import runner.proposal_emitter as pe
    # Monkeypatch requests.post
    import requests
    monkeypatch.setattr(requests, 'post', _fake_post)
    monkeypatch.setenv('BIYINGTONG_PROPOSAL_TOKEN', 'secret')

    out = emit_proposal(
        'http://127.0.0.1:5000',
        agent_id='a1',
        decision={'action': 'buy', 'code': '600519.SH',
                  'shares': 100, 'price': 1700.0,
                  'reason': 'test', 'thinking': 'test'},
    )
    assert out == {'ok': True}
    assert captured['url'] == 'http://127.0.0.1:5000/api/proposals'
    assert captured['json']['agent_id'] == 'a1'
    assert captured['json']['action'] == 'buy'
    assert captured['json']['code'] == '600519.SH'
    assert 'id' in captured['json']
    assert 'decision_at' in captured['json']
    assert captured['headers']['X-Proposal-Token'] == 'secret'


def test_agent_process_argparse_requires_agent_id():
    """Missing --agent-id → argparse exits with SystemExit(2)."""
    from runner.agent_process import main
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_agent_process_unknown_agent_returns_2(observability_storage, monkeypatch):
    """If the agent_id doesn't exist, run() returns 2 (not raises)."""
    from runner.agent_process import run
    # observability_storage wired empty agents table → run() sees None
    # Don't actually loop — max_ticks=0 never runs, but agent check is before loop
    rc = run(agent_id='does-not-exist', flask_url='http://127.0.0.1:5000',
             max_ticks=0)
    assert rc == 2


# ────────────────────────────────────────────────────────────────────────
# P3-F Phase 1 — Tasks 4 + 5: deploy/stop + proposals endpoints
# ────────────────────────────────────────────────────────────────────────


def _fresh_flask_app():
    from flask import Flask
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def deploy_storage(observability_storage, tmp_path):
    """Extend observability_storage with tmp_path-scoped proposals +
    deployed_agents stores so tests don't touch the real data/ DB."""
    import storage
    from storage.sqlite_proposals import SQLiteTradeProposalStore
    from storage.sqlite_deployed_agents import SQLiteDeployedAgentStore

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


# ─── deploy endpoints ───────────────────────────────────────────────────


def test_deploy_agent_spawns_subprocess(deploy_storage, client, monkeypatch):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='d1', initial_capital=1_000_000.0,
    )

    class _FakeProc:
        pid = 99999

    from api import deploy as deploy_mod
    spawned = {}

    def _fake_spawn(agent_id, flask_url):
        spawned['agent_id'] = agent_id
        spawned['flask_url'] = flask_url
        return _FakeProc()
    monkeypatch.setattr(deploy_mod, '_spawn_subprocess', _fake_spawn)

    resp = client.post(f'/api/agents/{agent.id}/deploy')
    assert resp.status_code == 202
    data = resp.get_json()
    assert data['pid'] == 99999
    assert data['status'] == 'running'
    assert spawned['agent_id'] == agent.id
    # DB
    assert storage.deployed_agents().get(agent.id).status == 'running'


def test_deploy_agent_404_on_missing(deploy_storage, client):
    resp = client.post('/api/agents/nope/deploy')
    assert resp.status_code == 404


def test_deploy_agent_409_when_already_running(deploy_storage, client, monkeypatch):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='d2', initial_capital=1_000_000.0,
    )
    # Pre-seed a running deployment
    storage.deployed_agents().upsert(agent.id, pid=12345, schedule='daily')

    from api import deploy as deploy_mod

    def _boom(*a, **kw):
        raise RuntimeError('should not spawn')
    monkeypatch.setattr(deploy_mod, '_spawn_subprocess', _boom)
    resp = client.post(f'/api/agents/{agent.id}/deploy')
    assert resp.status_code == 409


def test_deploy_agent_schedule_override(deploy_storage, client, monkeypatch):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='d_sched', initial_capital=1_000_000.0,
    )

    class _FakeProc:
        pid = 11111

    from api import deploy as deploy_mod
    monkeypatch.setattr(deploy_mod, '_spawn_subprocess',
                        lambda *a, **kw: _FakeProc())
    resp = client.post(f'/api/agents/{agent.id}/deploy',
                       json={'schedule': 'intraday_5m'})
    assert resp.status_code == 202
    assert resp.get_json()['schedule'] == 'intraday_5m'


def test_stop_agent_happy(deploy_storage, client, monkeypatch):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='d3', initial_capital=1_000_000.0,
    )
    storage.deployed_agents().upsert(agent.id, pid=12345, schedule='daily')

    from api import deploy as deploy_mod
    killed = {}

    def _fake_terminate(pid):
        killed['pid'] = pid
    monkeypatch.setattr(deploy_mod, '_terminate_subprocess', _fake_terminate)

    resp = client.post(f'/api/agents/{agent.id}/stop')
    assert resp.status_code == 200
    assert killed['pid'] == 12345
    assert storage.deployed_agents().get(agent.id).status == 'stopped'


def test_stop_agent_404_when_not_deployed(deploy_storage, client):
    resp = client.post('/api/agents/nope/stop')
    assert resp.status_code == 404


def test_deploy_status(deploy_storage, client):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='d4', initial_capital=1_000_000.0,
    )
    storage.deployed_agents().upsert(agent.id, pid=99, schedule='weekly')
    resp = client.get(f'/api/agents/{agent.id}/deploy_status')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['pid'] == 99
    assert data['schedule'] == 'weekly'
    assert data['status'] == 'running'


def test_deploy_status_404(deploy_storage, client):
    resp = client.get('/api/agents/nope/deploy_status')
    assert resp.status_code == 404


# ─── proposals endpoints ────────────────────────────────────────────────


def test_create_proposal_happy(deploy_storage, client, monkeypatch):
    monkeypatch.delenv('BIYINGTONG_PROPOSAL_TOKEN', raising=False)
    resp = client.post('/api/proposals', json={
        'id': 'p-new-1', 'agent_id': 'a1',
        'decision_at': '2026-04-23T10:00:00',
        'action': 'buy', 'code': '600519.SH', 'shares': 100, 'price': 1700.0,
        'reason': 'x', 'thinking': 'y',
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['id'] == 'p-new-1'
    assert data['status'] == 'pending'


def test_create_proposal_400_on_missing_fields(deploy_storage, client, monkeypatch):
    monkeypatch.delenv('BIYINGTONG_PROPOSAL_TOKEN', raising=False)
    resp = client.post('/api/proposals', json={'id': 'x'})
    assert resp.status_code == 400


def test_create_proposal_token_enforced_when_env_set(deploy_storage, client, monkeypatch):
    monkeypatch.setenv('BIYINGTONG_PROPOSAL_TOKEN', 'secret')
    # No header → 403
    resp = client.post('/api/proposals', json={
        'id': 'p-t1', 'agent_id': 'a1',
        'decision_at': 'x', 'action': 'buy',
    })
    assert resp.status_code == 403
    # Wrong header → 403
    resp = client.post('/api/proposals',
                       headers={'X-Proposal-Token': 'wrong'},
                       json={'id': 'p-t2', 'agent_id': 'a1',
                             'decision_at': 'x', 'action': 'buy'})
    assert resp.status_code == 403
    # Correct header → 201
    resp = client.post('/api/proposals',
                       headers={'X-Proposal-Token': 'secret'},
                       json={'id': 'p-t3', 'agent_id': 'a1',
                             'decision_at': 'x', 'action': 'buy'})
    assert resp.status_code == 201


def test_create_proposal_no_token_when_env_unset(deploy_storage, client, monkeypatch):
    monkeypatch.delenv('BIYINGTONG_PROPOSAL_TOKEN', raising=False)
    resp = client.post('/api/proposals', json={
        'id': 'p-nt1', 'agent_id': 'a1',
        'decision_at': 'x', 'action': 'buy',
    })
    assert resp.status_code == 201  # dev mode accepts


def test_list_proposals_pending_default(deploy_storage, client):
    import storage
    from storage.base import TradeProposal
    for i, st in enumerate(['pending', 'approved', 'pending', 'rejected']):
        storage.proposals().insert(TradeProposal(
            id=f'lp{i}', agent_id='al', decision_at='x',
            action='buy', status=st,
        ))
    resp = client.get('/api/proposals')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert all(p['status'] == 'pending' for p in data)


def test_get_proposal_404(deploy_storage, client):
    resp = client.get('/api/proposals/nope')
    assert resp.status_code == 404


def test_approve_proposal_phase1_no_tdx(deploy_storage, client):
    import storage
    from storage.base import TradeProposal
    storage.proposals().insert(TradeProposal(
        id='pa1', agent_id='a1', decision_at='x',
        action='buy', status='pending',
    ))
    resp = client.post('/api/proposals/pa1/approve')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'approved'
    assert data['decided_by'] == 'user'
    # Verify DB state change only — Phase 1 has no TDX call


def test_approve_proposal_409_on_non_pending(deploy_storage, client):
    import storage
    from storage.base import TradeProposal
    storage.proposals().insert(TradeProposal(
        id='pa2', agent_id='a1', decision_at='x',
        action='buy', status='approved',
    ))
    resp = client.post('/api/proposals/pa2/approve')
    assert resp.status_code == 409


def test_approve_proposal_404(deploy_storage, client):
    resp = client.post('/api/proposals/nope/approve')
    assert resp.status_code == 404


def test_reject_proposal(deploy_storage, client):
    import storage
    from storage.base import TradeProposal
    storage.proposals().insert(TradeProposal(
        id='pr1', agent_id='a1', decision_at='x',
        action='buy', status='pending',
    ))
    resp = client.post('/api/proposals/pr1/reject')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'rejected'


def test_reject_proposal_404(deploy_storage, client):
    resp = client.post('/api/proposals/nope/reject')
    assert resp.status_code == 404
