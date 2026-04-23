"""E2E: PUT /api/redlines with audit trail."""
from __future__ import annotations

import pytest


def _fresh_app():
    """Build a Flask app with only the P2e blueprint (skip socketio / TDX wiring)."""
    from flask import Flask
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def wired(tmp_path):
    """Wire up redline + audit + models (models.seed() runs via init_schema)."""
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    from storage.sqlite_audit import SQLiteAuditStore
    from storage.sqlite_models import SQLiteModelStore

    for cls, setter in [
        (SQLiteRedLineStore, 'set_redline'),
        (SQLiteAuditStore, 'set_audit'),
        (SQLiteModelStore, 'set_models'),
    ]:
        inst = cls(tmp_path=tmp_path); inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()
    return storage


@pytest.fixture
def client(wired):
    return _fresh_app().test_client()


def test_put_redlines_valid_subset(client, wired):
    """PUT with a valid subset merges into current config; GET reflects it."""
    # Original defaults
    before = client.get('/api/redlines').get_json()
    assert before['position_max_pct'] == 15.0
    assert before['ban_st'] is True

    resp = client.put('/api/redlines', json={
        'position_max_pct': 10.0,
        'ban_st': False,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['position_max_pct'] == 10.0
    assert data['ban_st'] is False
    # Untouched keys preserved
    assert data['daily_loss_max_pct'] == before['daily_loss_max_pct']

    after = client.get('/api/redlines').get_json()
    assert after['position_max_pct'] == 10.0
    assert after['ban_st'] is False


def test_put_redlines_unknown_key(client):
    """Unknown key -> 400 and mentions the key."""
    resp = client.put('/api/redlines', json={
        'position_max_pct': 10.0,
        'no_such_rule': 42,
    })
    assert resp.status_code == 400
    body = resp.get_json()
    assert 'no_such_rule' in body['error']


def test_put_redlines_empty_body(client):
    """Empty body -> 400 with 'empty body'."""
    resp = client.put('/api/redlines', json={})
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'empty body'


def test_put_redlines_writes_audit(client, wired):
    """Successful PUT writes an AuditEntry(kind='redline_changed')."""
    resp = client.put('/api/redlines', json={'position_max_pct': 12.0})
    assert resp.status_code == 200

    rows = wired.audit().query_by_kind('redline_changed')
    assert len(rows) == 1
    row = rows[0]
    assert row['kind'] == 'redline_changed'
    assert row['agent_id'] is None
    details = row['details']
    assert 'before' in details and 'after' in details
    assert details['before']['position_max_pct'] == 15.0
    assert details['after']['position_max_pct'] == 12.0
