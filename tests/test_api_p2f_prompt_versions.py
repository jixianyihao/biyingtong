"""GET /api/agents/:id/prompt_versions."""
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


def test_unknown_agent_404(client):
    resp = client.get('/api/agents/nope/prompt_versions')
    assert resp.status_code == 404


def test_new_agent_has_v1(client, wired):
    a = wired.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='PromptTest',
    )
    resp = client.get(f'/api/agents/{a.id}/prompt_versions')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['version_number'] == 1
    assert '林园' in data[0]['system_prompt'] or 'value' in data[0]['system_prompt'].lower()


def test_multiple_versions_ordered(client, wired):
    a = wired.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='MultiVer',
    )
    wired.prompt_versions().insert(a.id, 'v2 prompt content — revised', note='tuned trigger threshold')
    wired.prompt_versions().insert(a.id, 'v3 prompt content — again', note='add position sizing guard')
    resp = client.get(f'/api/agents/{a.id}/prompt_versions')
    data = resp.get_json()
    assert len(data) == 3
    assert [v['version_number'] for v in data] == [1, 2, 3]
    assert data[2]['note'] == 'add position sizing guard'
