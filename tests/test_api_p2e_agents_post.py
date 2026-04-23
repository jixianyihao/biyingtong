"""POST /api/agents — create agent from persona + model."""
import pytest


def _fresh_app():
    from flask import Flask
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def wired(tmp_path):
    import storage
    from storage.sqlite_personas import SQLitePersonaStore
    from storage.sqlite_agents import SQLiteAgentStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    from storage.sqlite_models import SQLiteModelStore
    for cls, setter in [
        (SQLitePersonaStore, 'set_personas'),
        (SQLiteAgentStore, 'set_agents'),
        (SQLitePromptVersionStore, 'set_prompt_versions'),
        (SQLiteModelStore, 'set_models'),
    ]:
        inst = cls(tmp_path=tmp_path); inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()
    from personas import seed as seed_personas
    seed_personas()
    return storage


@pytest.fixture
def client(wired):
    return _fresh_app().test_client()


def test_post_missing_fields(client):
    resp = client.post('/api/agents', json={'persona_id': 'linyuan'})
    assert resp.status_code == 400


def test_post_unknown_persona(client):
    resp = client.post('/api/agents', json={
        'persona_id': 'nope', 'model_id': 'claude-opus-4-7',
        'display_name': 'X',
    })
    assert resp.status_code == 404


def test_post_unknown_model(client):
    resp = client.post('/api/agents', json={
        'persona_id': 'linyuan', 'model_id': 'ghost-model',
        'display_name': 'X',
    })
    assert resp.status_code == 404


def test_post_creates_agent(client, wired):
    resp = client.post('/api/agents', json={
        'persona_id': 'linyuan', 'model_id': 'claude-opus-4-7',
        'display_name': 'Created-via-API',
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['persona_id'] == 'linyuan'
    assert data['model_id'] == 'claude-opus-4-7'
    assert data['display_name'] == 'Created-via-API'
    # Persisted
    assert wired.agents().get(data['id']) is not None


def test_post_accepts_rules_override(client, wired):
    resp = client.post('/api/agents', json={
        'persona_id': 'linyuan', 'model_id': 'claude-opus-4-7',
        'display_name': 'StrictAgent',
        'rules_override': {'position_max_pct': 5.0},
        'initial_capital': 500_000,
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['rules_override'] == {'position_max_pct': 5.0}
    assert data['initial_capital'] == 500_000.0


def test_post_empty_body(client):
    resp = client.post('/api/agents', json={})
    assert resp.status_code == 400
