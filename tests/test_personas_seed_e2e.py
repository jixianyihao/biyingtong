"""E2E: seed personas → create agent → verify prompt version chain."""


def _setup_stores(tmp_path):
    """Wire all stores pointing at tmp_path."""
    import storage
    from storage.sqlite_personas import SQLitePersonaStore
    from storage.sqlite_agents import SQLiteAgentStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    from storage.sqlite_models import SQLiteModelStore

    pstore = SQLitePersonaStore(tmp_path=tmp_path)
    pstore.init_schema()
    storage.set_personas(pstore)

    agent_store = SQLiteAgentStore(tmp_path=tmp_path)
    agent_store.init_schema()
    storage.set_agents(agent_store)

    pv_store = SQLitePromptVersionStore(tmp_path=tmp_path)
    pv_store.init_schema()
    storage.set_prompt_versions(pv_store)

    # Models are needed so agent.model_id references resolve (no FK enforcement in SQLite)
    m_store = SQLiteModelStore(tmp_path=tmp_path)
    m_store.init_schema()
    m_store.seed()
    storage.set_models(m_store)


def test_seed_inserts_all_5_personas(tmp_path):
    _setup_stores(tmp_path)
    from personas import seed
    seed()

    import storage
    all_seeded = storage.personas().list_all()
    assert {p.id for p in all_seeded} == {
        'linyuan', 'fuyou', 'buffet', 'soros', 'quant_neutral',
    }


def test_seed_is_idempotent(tmp_path):
    _setup_stores(tmp_path)
    from personas import seed
    seed()
    seed()
    seed()

    import storage
    assert len(storage.personas().list_all()) == 5


def test_seeded_persona_has_full_data(tmp_path):
    _setup_stores(tmp_path)
    from personas import seed
    seed()

    import storage
    linyuan = storage.personas().get('linyuan')
    assert linyuan is not None
    assert linyuan.name == '林园风格'
    assert linyuan.default_schedule == 'weekly'
    assert 'value' in linyuan.system_prompt.lower() or '价值投资' in linyuan.system_prompt
    assert len(linyuan.default_pool) >= 10
    assert linyuan.default_rules.get('position_max_pct') == 30.0
    assert 'get_kline' in linyuan.allowed_tools
    assert linyuan.is_builtin is True


def test_create_agent_from_seeded_persona_links_prompt_version(tmp_path):
    """Full chain: seeded persona → create_from_persona → v1 prompt snapshot."""
    _setup_stores(tmp_path)
    from personas import seed
    seed()

    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan',
        model_id='claude-opus-4-7',
        display_name='林园 · Claude Opus 4.7',
    )
    assert agent.persona_id == 'linyuan'
    assert agent.model_id == 'claude-opus-4-7'
    assert agent.current_prompt_version_id is not None

    pv = storage.prompt_versions().get_latest(agent.id)
    assert pv is not None
    assert pv.version_number == 1
    assert '林园' in pv.system_prompt
    assert pv.id == agent.current_prompt_version_id


def test_multiple_agents_from_same_persona_with_different_models(tmp_path):
    """Spec § 4.2: same persona + different models = separate instances."""
    _setup_stores(tmp_path)
    from personas import seed
    seed()

    import storage
    a_claude = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='林园 · Claude Opus',
    )
    a_gpt = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='gpt-5',
        display_name='林园 · GPT-5',
    )
    assert a_claude.id != a_gpt.id
    assert a_claude.persona_id == a_gpt.persona_id == 'linyuan'
    assert a_claude.model_id == 'claude-opus-4-7'
    assert a_gpt.model_id == 'gpt-5'

    all_agents = storage.agents().list_all()
    assert len(all_agents) == 2
