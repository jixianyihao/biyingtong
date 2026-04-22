"""SQLiteAgentStore — agent instances (persona × model × rules_override)."""


def _prepare_persona(tmp_path):
    """Seed a minimal persona so agent creation can reference it."""
    import storage
    from storage.base import Persona
    from storage.sqlite_personas import SQLitePersonaStore
    pstore = SQLitePersonaStore(tmp_path=tmp_path)
    pstore.init_schema()
    pstore.upsert(Persona(
        id='p_test', name='Test Persona', style_desc='',
        system_prompt='You are persona p_test.',
        default_pool=['600519.SH'], pool_filter=None,
        default_schedule='weekly',
        default_rules={'position_max_pct': 30.0},
        allowed_tools=['get_kline'], is_builtin=True,
    ))
    storage.set_personas(pstore)


def _prepare_prompt_version_store(tmp_path):
    """Seed prompt_versions table + factory so agent.create_from_persona works."""
    import storage
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    pv = SQLitePromptVersionStore(tmp_path=tmp_path)
    pv.init_schema()
    storage.set_prompt_versions(pv)


def test_sqlite_agent_store_satisfies_protocol(tmp_path):
    from storage.base import AgentStore
    from storage.sqlite_agents import SQLiteAgentStore
    assert isinstance(SQLiteAgentStore(tmp_path=tmp_path), AgentStore)


def test_create_from_persona_inserts_agent_and_v1(tmp_path):
    _prepare_persona(tmp_path)
    _prepare_prompt_version_store(tmp_path)
    from storage.sqlite_agents import SQLiteAgentStore
    store = SQLiteAgentStore(tmp_path=tmp_path)
    store.init_schema()

    agent = store.create_from_persona(
        persona_id='p_test',
        model_id='claude-opus-4-7',
        display_name='p_test · Claude Opus 4.7',
    )
    assert agent.id.startswith('p_test_')
    assert agent.persona_id == 'p_test'
    assert agent.model_id == 'claude-opus-4-7'
    assert agent.display_name == 'p_test · Claude Opus 4.7'
    assert agent.status == 'created'
    assert agent.health_score == 100
    assert agent.trust_rating == 'A'
    assert agent.current_prompt_version_id is not None
    assert agent.initial_capital == 1_000_000.0

    # Verify prompt_versions v1 was inserted with the persona's system_prompt
    import storage
    pv = storage.prompt_versions().get_latest(agent.id)
    assert pv is not None
    assert pv.version_number == 1
    assert pv.system_prompt == 'You are persona p_test.'
    assert pv.id == agent.current_prompt_version_id


def test_create_from_persona_applies_rules_override(tmp_path):
    _prepare_persona(tmp_path)
    _prepare_prompt_version_store(tmp_path)
    from storage.sqlite_agents import SQLiteAgentStore
    store = SQLiteAgentStore(tmp_path=tmp_path)
    store.init_schema()

    agent = store.create_from_persona(
        persona_id='p_test', model_id='claude-opus-4-7',
        display_name='custom',
        rules_override={'daily_loss_max_pct': 2.0},
        initial_capital=500_000,
    )
    assert agent.rules_override == {'daily_loss_max_pct': 2.0}
    assert agent.initial_capital == 500_000.0


def test_create_from_persona_unknown_persona_raises(tmp_path):
    _prepare_prompt_version_store(tmp_path)  # needs prompt_versions wired
    from storage.sqlite_agents import SQLiteAgentStore
    import storage
    # Empty persona store so persona lookup returns None
    from storage.sqlite_personas import SQLitePersonaStore
    pstore = SQLitePersonaStore(tmp_path=tmp_path)
    pstore.init_schema()
    storage.set_personas(pstore)

    store = SQLiteAgentStore(tmp_path=tmp_path)
    store.init_schema()

    import pytest
    with pytest.raises(ValueError, match='persona'):
        store.create_from_persona(
            persona_id='does_not_exist', model_id='claude-opus-4-7',
            display_name='x',
        )


def test_get_and_list(tmp_path):
    _prepare_persona(tmp_path)
    _prepare_prompt_version_store(tmp_path)
    from storage.sqlite_agents import SQLiteAgentStore
    store = SQLiteAgentStore(tmp_path=tmp_path)
    store.init_schema()

    a1 = store.create_from_persona(
        persona_id='p_test', model_id='claude-opus-4-7',
        display_name='inst1',
    )
    a2 = store.create_from_persona(
        persona_id='p_test', model_id='gpt-5',
        display_name='inst2',
    )

    loaded = store.get(a1.id)
    assert loaded is not None
    assert loaded.display_name == 'inst1'

    all_agents = store.list_all()
    assert len(all_agents) == 2
    assert {a.id for a in all_agents} == {a1.id, a2.id}


def test_update_status(tmp_path):
    _prepare_persona(tmp_path)
    _prepare_prompt_version_store(tmp_path)
    from storage.sqlite_agents import SQLiteAgentStore
    store = SQLiteAgentStore(tmp_path=tmp_path)
    store.init_schema()

    a = store.create_from_persona(
        persona_id='p_test', model_id='claude-opus-4-7',
        display_name='x',
    )
    assert a.status == 'created'

    store.update_status(a.id, 'backtested')
    loaded = store.get(a.id)
    assert loaded.status == 'backtested'


def test_storage_factory_returns_sqlite_agent_store(tmp_path):
    import storage
    storage.reset()
    from storage.sqlite_agents import SQLiteAgentStore
    assert isinstance(storage.agents(), SQLiteAgentStore)
