"""P3-F Phase 2 Task 5 — execution fields on trade_proposals + update_execution."""
from __future__ import annotations

import pytest

from storage.base import TradeProposal
from storage.sqlite_proposals import SQLiteTradeProposalStore


@pytest.fixture
def store(tmp_path):
    s = SQLiteTradeProposalStore(tmp_path=tmp_path)
    s.init_schema()
    return s


def _seed(store):
    p = TradeProposal(
        id='p-1', agent_id='a-1',
        decision_at='2026-04-24T09:30:00', action='buy',
        code='600519.SH', shares=100, price=237.5,
        reason='r', thinking='t', status='pending',
    )
    store.insert(p)
    return p


def test_new_proposal_has_null_execution_fields(store):
    _seed(store)
    got = store.get('p-1')
    assert got is not None
    assert got.execution_mode is None
    assert got.execution_order_id is None
    assert got.execution_error is None
    assert got.executed_at is None
    assert got.filled_qty is None
    assert got.filled_price is None


def test_update_execution_writes_fields(store):
    _seed(store)
    ok = store.update_execution(
        'p-1', execution_mode='dry_run', execution_order_id='mock-abc',
        execution_error=None, filled_qty=100, filled_price=237.5,
        executed_at='2026-04-24T10:00:00',
    )
    assert ok is True
    got = store.get('p-1')
    assert got.execution_mode == 'dry_run'
    assert got.execution_order_id == 'mock-abc'
    assert got.execution_error is None
    assert got.filled_qty == 100
    assert got.filled_price == 237.5
    assert got.executed_at == '2026-04-24T10:00:00'


def test_update_execution_missing_returns_false(store):
    assert store.update_execution(
        'ghost', execution_mode='dry_run', execution_order_id='x',
        execution_error=None, filled_qty=0, filled_price=0.0,
        executed_at='2026-04-24T10:00:00',
    ) is False


def test_init_schema_is_idempotent(tmp_path):
    # Second init on same path must not raise (ALTER column-exists handled)
    s1 = SQLiteTradeProposalStore(tmp_path=tmp_path)
    s1.init_schema()
    s2 = SQLiteTradeProposalStore(tmp_path=tmp_path)
    s2.init_schema()
    s2.init_schema()  # third call for good measure
    # still usable
    s2.insert(TradeProposal(
        id='pz', agent_id='a', decision_at='x',
        action='buy', status='pending',
    ))
    assert s2.get('pz') is not None
