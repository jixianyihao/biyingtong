"""GET /api/backtests/<id>/ledger — joined LLM decision → validation → fill view.

The endpoint joins ``BacktestResult.thinking[].decisions[]`` with
``BacktestResult.trades[]`` by ``(date, code, action)``. Tests use a fake
BacktestResultStore so no SQLite/vnpy dependency leaks into the suite.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from flask import Flask


def _fresh_flask_app():
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@dataclass
class _FakeResult:
    """Just enough of BacktestResult for the ledger endpoint."""
    id: str
    trades: list[dict]
    thinking: list[dict]


class _FakeBacktestStore:
    """Single-method stand-in: only .get() is exercised by /ledger."""

    def __init__(self, results: dict[str, Any]):
        self._results = results

    def get(self, result_id: str):
        return self._results.get(result_id)

    # The rest of the BacktestResultStore protocol is never called by the
    # ledger endpoint — explicit no-ops keep duck-typing checks happy if
    # something else stumbles into this fake by accident.
    def init_schema(self) -> None:  # pragma: no cover
        return None

    def insert(self, result) -> None:  # pragma: no cover
        return None

    def list_for_agent(self, agent_id, limit=50):  # pragma: no cover
        return []

    def list_for_session(self, session_id):  # pragma: no cover
        return []

    def list_all(self, limit=50):  # pragma: no cover
        return []

    def create_session(self, *a, **kw):  # pragma: no cover
        return None

    def list_sessions(self, limit=50):  # pragma: no cover
        return []

    def delete(self, result_id):  # pragma: no cover
        return False


@pytest.fixture
def client():
    app = _fresh_flask_app()
    with app.test_client() as c:
        yield c


def test_ledger_happy_path_join_buy_with_fill(client):
    """1 day, 1 buy decision matching 1 fill → 1 row, executed_shares populated."""
    import storage
    r = _FakeResult(
        id='r1',
        thinking=[{
            'date': '2025-06-01',
            'reasoning': 'looks good — Maotai 5y trough',
            'tool_calls': [
                {'name': 'get_kline', 'input': {}},
                {'name': 'get_financials', 'input': {}},
            ],
            'decisions': [{
                'action': 'buy', 'code': '600519.SH',
                'shares': 100, 'price': 1500.0,
                'outcome': 'ok', 'reasoning': 'value pick',
            }],
        }],
        trades=[{
            'date': '2025-06-01', 'code': '600519.SH',
            'action': 'buy', 'shares': 100, 'price': 1500.5,
            'fee': 7.50,
        }],
    )
    storage.set_backtests(_FakeBacktestStore({'r1': r}))

    resp = client.get('/api/backtests/r1/ledger')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['result_id'] == 'r1'
    assert len(body['ledger']) == 1
    row = body['ledger'][0]
    assert row['date'] == '2025-06-01'
    assert row['action'] == 'buy'
    assert row['code'] == '600519.SH'
    assert row['requested_shares'] == 100
    assert row['requested_price'] == 1500.0
    assert row['outcome'] == 'ok'
    assert row['rejection_reasons'] == []
    assert row['executed_shares'] == 100
    assert row['executed_price'] == 1500.5
    assert row['executed_fee'] == 7.50
    assert row['reasoning'] == 'value pick'
    assert row['tool_calls_count'] == 2


def test_ledger_rejected_decision_has_no_fill(client):
    """buy decision with NO matching fill (outcome=rejected) → executed_shares=0."""
    import storage
    r = _FakeResult(
        id='r1',
        thinking=[{
            'date': '2025-06-02',
            'reasoning': 'try to overweight',
            'tool_calls': [{'name': 'get_snapshot', 'input': {}}],
            'decisions': [{
                'action': 'buy', 'code': '601318.SH',
                'shares': 5000, 'price': 50.0,
                'outcome': 'rejected', 'reasoning': 'pushing position cap',
            }],
        }],
        trades=[],
    )
    storage.set_backtests(_FakeBacktestStore({'r1': r}))

    resp = client.get('/api/backtests/r1/ledger')
    assert resp.status_code == 200
    rows = resp.get_json()['ledger']
    assert len(rows) == 1
    row = rows[0]
    assert row['action'] == 'buy'
    assert row['outcome'] == 'rejected'
    assert row['executed_shares'] == 0
    assert row['executed_price'] is None
    assert row['executed_fee'] is None
    assert row['rejection_reasons'] == ['rejected by validation']
    assert row['tool_calls_count'] == 1


def test_ledger_day_without_decisions_emits_hold_row(client):
    """A day with N tool_calls but no place_decision → 1 hold row."""
    import storage
    r = _FakeResult(
        id='r1',
        thinking=[{
            'date': '2025-06-03',
            'reasoning': 'just scanning',
            'tool_calls': [
                {'name': 'get_kline', 'input': {}},
                {'name': 'get_news', 'input': {}},
                {'name': 'get_snapshot', 'input': {}},
            ],
            'decisions': [],
        }],
        trades=[],
    )
    storage.set_backtests(_FakeBacktestStore({'r1': r}))

    resp = client.get('/api/backtests/r1/ledger')
    assert resp.status_code == 200
    rows = resp.get_json()['ledger']
    assert len(rows) == 1
    row = rows[0]
    assert row['date'] == '2025-06-03'
    assert row['action'] == 'hold'
    assert row['code'] is None
    assert row['requested_shares'] is None
    assert row['requested_price'] is None
    assert row['outcome'] == 'hold'
    assert row['executed_shares'] == 0
    assert row['executed_price'] is None
    assert row['executed_fee'] is None
    assert row['reasoning'] == 'just scanning'
    assert row['tool_calls_count'] == 3


def test_ledger_404_on_unknown_result_id(client):
    import storage
    storage.set_backtests(_FakeBacktestStore({}))
    resp = client.get('/api/backtests/does-not-exist/ledger')
    assert resp.status_code == 404
    assert resp.get_json() == {'error': 'not_found'}
