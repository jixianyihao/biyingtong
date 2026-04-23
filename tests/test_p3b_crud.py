"""P3-B CRUD: agent/persona update + delete + prompt rollback."""
from __future__ import annotations


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
