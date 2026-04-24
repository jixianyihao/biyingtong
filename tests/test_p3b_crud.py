"""P3-B CRUD: agent/persona update + delete + prompt rollback."""
from __future__ import annotations

import pytest


def test_agent_store_protocol_has_update_method():
    from storage.base import AgentStore
    assert 'update' in dir(AgentStore)


def test_agent_store_protocol_has_delete_method():
    from storage.base import AgentStore
    assert 'delete' in dir(AgentStore)


def test_agent_store_protocol_has_set_current_prompt_version_method():
    from storage.base import AgentStore
    assert 'set_current_prompt_version' in dir(AgentStore)


def test_persona_store_protocol_has_delete_method():
    from storage.base import PersonaStore
    assert 'delete' in dir(PersonaStore)


def test_prompt_version_store_protocol_has_rollback_method():
    from storage.base import PromptVersionStore
    assert 'rollback' in dir(PromptVersionStore)


def test_agent_update_display_name(observability_storage):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='original', initial_capital=1_000_000.0,
    )
    storage.agents().update(agent.id, display_name='renamed')
    fetched = storage.agents().get(agent.id)
    assert fetched.display_name == 'renamed'
    # rules_override not passed → unchanged
    assert fetched.rules_override == {}


def test_agent_update_rules_override(observability_storage):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    storage.agents().update(agent.id, rules_override={'max_holdings': 3})
    fetched = storage.agents().get(agent.id)
    assert fetched.rules_override == {'max_holdings': 3}
    assert fetched.display_name == 't'


def test_agent_update_both_fields(observability_storage):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    storage.agents().update(
        agent.id, display_name='new', rules_override={'k': 1})
    fetched = storage.agents().get(agent.id)
    assert fetched.display_name == 'new'
    assert fetched.rules_override == {'k': 1}


def test_agent_update_nonexistent_is_noop(observability_storage):
    import storage
    storage.agents().update('nonexistent', display_name='x')
    assert storage.agents().get('nonexistent') is None


def test_agent_update_empty_kwargs_is_noop(observability_storage):
    """No kwargs passed → no SQL executed → no-op."""
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    storage.agents().update(agent.id)
    fetched = storage.agents().get(agent.id)
    assert fetched.display_name == 't'


def test_agent_delete_removes_row(observability_storage):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    assert storage.agents().delete(agent.id) is True
    assert storage.agents().get(agent.id) is None


def test_agent_delete_also_removes_prompt_versions(observability_storage):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    storage.prompt_versions().insert(
        agent_id=agent.id, system_prompt='new prompt', note='test',
    )
    assert len(storage.prompt_versions().list_for_agent(agent.id)) == 2

    storage.agents().delete(agent.id)
    assert storage.prompt_versions().list_for_agent(agent.id) == []


def test_agent_delete_nonexistent_returns_false(observability_storage):
    import storage
    assert storage.agents().delete('nonexistent') is False


def test_agent_set_current_prompt_version(observability_storage):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    pv = storage.prompt_versions().insert(
        agent_id=agent.id, system_prompt='v2', note='test',
    )
    storage.agents().set_current_prompt_version(agent.id, pv.id)
    fetched = storage.agents().get(agent.id)
    assert fetched.current_prompt_version_id == pv.id


def test_agent_set_current_prompt_version_missing_agent_is_silent(observability_storage):
    import storage
    # Must not raise
    storage.agents().set_current_prompt_version('nope', 1)


def test_persona_delete_removes_row(observability_storage):
    import storage
    from storage.base import Persona
    storage.personas().upsert(Persona(
        id='custom_test', name='Custom Test',
        style_desc='test', system_prompt='you are test',
        default_pool=[], pool_filter=None,
        default_schedule='daily', default_rules={},
        allowed_tools=[], is_builtin=False,
    ))
    assert storage.personas().get('custom_test') is not None
    assert storage.personas().delete('custom_test') is True
    assert storage.personas().get('custom_test') is None


def test_persona_delete_nonexistent_returns_false(observability_storage):
    import storage
    assert storage.personas().delete('nonexistent') is False


def test_prompt_version_rollback_creates_new_version_with_old_prompt(observability_storage):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    pv = storage.prompt_versions()
    # v1 is auto-created; make v2
    v2 = pv.insert(agent_id=agent.id, system_prompt='v2 prompt', note='updated')
    assert v2.version_number == 2

    # Rollback to v1
    versions = pv.list_for_agent(agent.id)
    v1 = versions[0]
    assert v1.version_number == 1
    new_version = pv.rollback(agent_id=agent.id, version_id=v1.id)

    assert new_version.version_number == 3
    assert new_version.system_prompt == v1.system_prompt
    assert 'rolled back to v1' in (new_version.note or '')
    # v1 and v2 unchanged
    assert [v.version_number for v in pv.list_for_agent(agent.id)] == [1, 2, 3]


def test_prompt_version_rollback_unknown_version_raises(observability_storage):
    import pytest
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    with pytest.raises(ValueError, match='not found'):
        storage.prompt_versions().rollback(
            agent_id=agent.id, version_id=99999)


def test_prompt_version_rollback_wrong_agent_raises(observability_storage):
    import pytest
    import storage
    a1 = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='a1', initial_capital=1_000_000.0,
    )
    a2 = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='a2', initial_capital=1_000_000.0,
    )
    a1_v1 = storage.prompt_versions().list_for_agent(a1.id)[0]
    with pytest.raises(ValueError, match='does not belong'):
        storage.prompt_versions().rollback(
            agent_id=a2.id, version_id=a1_v1.id)


# ---------------------------------------------------------------------------
# Task 5: agent endpoints
# ---------------------------------------------------------------------------


def _fresh_flask_app():
    """Minimal Flask app wrapping api_bp — avoids importing app.py (TDX)."""
    from flask import Flask
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(observability_storage):
    app = _fresh_flask_app()
    with app.test_client() as c:
        yield c


def test_put_agent_updates_display_name(observability_storage, client):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='original', initial_capital=1_000_000.0,
    )
    resp = client.put(f'/api/agents/{agent.id}',
                      json={'display_name': 'renamed'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['display_name'] == 'renamed'
    assert storage.agents().get(agent.id).display_name == 'renamed'


def test_put_agent_updates_rules_override(observability_storage, client):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    resp = client.put(f'/api/agents/{agent.id}',
                      json={'rules_override': {'max_holdings': 5}})
    assert resp.status_code == 200
    assert resp.get_json()['rules_override'] == {'max_holdings': 5}


def test_put_agent_404_on_missing(observability_storage, client):
    resp = client.put('/api/agents/nope', json={'display_name': 'x'})
    assert resp.status_code == 404


def test_put_agent_empty_body_is_noop_200(observability_storage, client):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    resp = client.put(f'/api/agents/{agent.id}', json={})
    assert resp.status_code == 200
    assert resp.get_json()['display_name'] == 't'


def test_delete_agent_204(observability_storage, client):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    resp = client.delete(f'/api/agents/{agent.id}')
    assert resp.status_code == 204
    assert storage.agents().get(agent.id) is None


def test_delete_agent_404_on_missing(observability_storage, client):
    resp = client.delete('/api/agents/nope')
    assert resp.status_code == 404


def test_rollback_prompt_creates_new_version(observability_storage, client):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    storage.prompt_versions().insert(
        agent_id=agent.id, system_prompt='v2 new', note='edited',
    )
    v1 = storage.prompt_versions().list_for_agent(agent.id)[0]

    resp = client.post(
        f'/api/agents/{agent.id}/prompts/rollback',
        json={'version_id': v1.id},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['version_number'] == 3
    assert data['system_prompt'] == v1.system_prompt
    # agents.current_prompt_version_id updated
    fresh = storage.agents().get(agent.id)
    assert fresh.current_prompt_version_id == data['id']


def test_rollback_404_on_missing_agent(observability_storage, client):
    resp = client.post('/api/agents/nope/prompts/rollback',
                       json={'version_id': 1})
    assert resp.status_code == 404


def test_rollback_400_on_missing_version_id(observability_storage, client):
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    resp = client.post(f'/api/agents/{agent.id}/prompts/rollback', json={})
    assert resp.status_code == 400


def test_rollback_400_on_bad_version_id(observability_storage, client):
    """version_id for a non-existent prompt version → 400 (ValueError from store)."""
    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    resp = client.post(f'/api/agents/{agent.id}/prompts/rollback',
                       json={'version_id': 99999})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Task 6: persona endpoints
# ---------------------------------------------------------------------------


def test_post_persona_creates(observability_storage, client):
    import storage
    body = {
        'id': 'custom1',
        'name': 'Custom 1',
        'style_desc': 'my custom style',
        'system_prompt': 'You are a custom agent.',
        'default_schedule': 'daily',
    }
    resp = client.post('/api/personas', json=body)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['id'] == 'custom1'
    assert data['is_builtin'] is False
    p = storage.personas().get('custom1')
    assert p is not None
    assert p.is_builtin is False


def test_post_persona_409_on_duplicate_id(observability_storage, client):
    resp = client.post('/api/personas', json={
        'id': 'linyuan',  # seeded as builtin
        'name': 'x', 'style_desc': 'x', 'system_prompt': 'x',
    })
    assert resp.status_code == 409


def test_post_persona_400_on_missing_fields(observability_storage, client):
    resp = client.post('/api/personas', json={'id': 'x'})
    assert resp.status_code == 400


def test_put_persona_updates_non_prompt_field(observability_storage, client):
    import storage
    from storage.base import Persona
    storage.personas().upsert(Persona(
        id='c2', name='C2', style_desc='old', system_prompt='old prompt',
        default_pool=[], pool_filter=None, default_schedule='daily',
        default_rules={}, allowed_tools=[], is_builtin=False,
    ))
    resp = client.put('/api/personas/c2', json={'name': 'C2 NEW'})
    assert resp.status_code == 200
    assert storage.personas().get('c2').name == 'C2 NEW'
    # system_prompt unchanged
    assert storage.personas().get('c2').system_prompt == 'old prompt'


def test_put_persona_system_prompt_bumps_agent_versions(observability_storage, client):
    """Key test: changing system_prompt must insert a new prompt_version for each
    referencing agent and point its current_prompt_version_id at the new row."""
    import storage
    from storage.base import Persona
    storage.personas().upsert(Persona(
        id='c3', name='C3', style_desc='v', system_prompt='v1',
        default_pool=[], pool_filter=None, default_schedule='daily',
        default_rules={}, allowed_tools=[], is_builtin=False,
    ))
    agent = storage.agents().create_from_persona(
        persona_id='c3', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    assert len(storage.prompt_versions().list_for_agent(agent.id)) == 1

    resp = client.put('/api/personas/c3',
                      json={'system_prompt': 'v2 improved'})
    assert resp.status_code == 200

    versions = storage.prompt_versions().list_for_agent(agent.id)
    assert len(versions) == 2
    assert versions[1].system_prompt == 'v2 improved'
    assert 'c3' in (versions[1].note or '')
    fresh = storage.agents().get(agent.id)
    assert fresh.current_prompt_version_id == versions[1].id


def test_put_persona_403_on_builtin(observability_storage, client):
    resp = client.put('/api/personas/linyuan', json={'name': 'NOT ALLOWED'})
    assert resp.status_code == 403


def test_put_persona_404_on_missing(observability_storage, client):
    resp = client.put('/api/personas/nope', json={'name': 'x'})
    assert resp.status_code == 404


def test_delete_persona_204(observability_storage, client):
    import storage
    from storage.base import Persona
    storage.personas().upsert(Persona(
        id='c4', name='c4', style_desc='x', system_prompt='x',
        default_pool=[], pool_filter=None, default_schedule='daily',
        default_rules={}, allowed_tools=[], is_builtin=False,
    ))
    resp = client.delete('/api/personas/c4')
    assert resp.status_code == 204
    assert storage.personas().get('c4') is None


def test_delete_persona_403_on_builtin(observability_storage, client):
    resp = client.delete('/api/personas/linyuan')
    assert resp.status_code == 403


def test_delete_persona_409_when_agent_references_it(observability_storage, client):
    import storage
    from storage.base import Persona
    storage.personas().upsert(Persona(
        id='c5', name='c5', style_desc='x', system_prompt='x',
        default_pool=[], pool_filter=None, default_schedule='daily',
        default_rules={}, allowed_tools=[], is_builtin=False,
    ))
    storage.agents().create_from_persona(
        persona_id='c5', model_id='claude-opus-4-7',
        display_name='t', initial_capital=1_000_000.0,
    )
    resp = client.delete('/api/personas/c5')
    assert resp.status_code == 409
    assert storage.personas().get('c5') is not None


def test_delete_persona_404_on_missing(observability_storage, client):
    resp = client.delete('/api/personas/nope')
    assert resp.status_code == 404


def test_put_persona_system_prompt_cascade_bumps_ALL_referencing_agents(
    observability_storage, client,
):
    """Changing a persona's system_prompt must bump every referencing agent's
    current_prompt_version_id, not just one of them."""
    import storage
    from storage.base import Persona
    storage.personas().upsert(Persona(
        id='c-multi', name='multi', style_desc='x', system_prompt='v1',
        default_pool=[], pool_filter=None, default_schedule='daily',
        default_rules={}, allowed_tools=[], is_builtin=False,
    ))
    # Three agents referencing the same persona
    agents = [
        storage.agents().create_from_persona(
            persona_id='c-multi', model_id='claude-opus-4-7',
            display_name=f'agent-{i}', initial_capital=1_000_000.0,
        )
        for i in range(3)
    ]
    # Baseline: each has exactly one prompt_version row
    for a in agents:
        assert len(storage.prompt_versions().list_for_agent(a.id)) == 1
    original_pv_ids = {a.id: storage.agents().get(a.id).current_prompt_version_id
                       for a in agents}

    resp = client.put('/api/personas/c-multi',
                      json={'system_prompt': 'v2 cascade'})
    assert resp.status_code == 200

    # EVERY agent's current_prompt_version_id must now differ from before,
    # AND each must have 2 versions (v1 + v2).
    for a in agents:
        versions = storage.prompt_versions().list_for_agent(a.id)
        assert len(versions) == 2, (
            f'agent {a.id}: expected 2 versions after cascade, got {len(versions)}'
        )
        assert versions[1].system_prompt == 'v2 cascade'
        fresh = storage.agents().get(a.id)
        assert fresh.current_prompt_version_id == versions[1].id
        assert fresh.current_prompt_version_id != original_pv_ids[a.id]
