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
