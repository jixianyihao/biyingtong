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
