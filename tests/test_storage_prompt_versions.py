"""SQLitePromptVersionStore — immutable prompt snapshots per agent."""


def test_sqlite_prompt_version_store_satisfies_protocol(tmp_path):
    from storage.base import PromptVersionStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    assert isinstance(SQLitePromptVersionStore(tmp_path=tmp_path), PromptVersionStore)


def test_insert_first_version(tmp_path):
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    store = SQLitePromptVersionStore(tmp_path=tmp_path)
    store.init_schema()

    v = store.insert(agent_id='a1', system_prompt='First prompt')
    assert v.version_number == 1
    assert v.system_prompt == 'First prompt'
    assert v.id > 0
    assert v.created_at is not None


def test_insert_increments_version(tmp_path):
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    store = SQLitePromptVersionStore(tmp_path=tmp_path)
    store.init_schema()

    store.insert(agent_id='a1', system_prompt='v1')
    v2 = store.insert(agent_id='a1', system_prompt='v2', note='rev for X')

    assert v2.version_number == 2
    assert v2.note == 'rev for X'


def test_versions_are_per_agent(tmp_path):
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    store = SQLitePromptVersionStore(tmp_path=tmp_path)
    store.init_schema()

    v1_a = store.insert(agent_id='a1', system_prompt='hi')
    v1_b = store.insert(agent_id='b1', system_prompt='hi')
    v2_a = store.insert(agent_id='a1', system_prompt='hi v2')

    assert v1_a.version_number == 1
    assert v1_b.version_number == 1
    assert v2_a.version_number == 2


def test_get_latest_returns_newest(tmp_path):
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    store = SQLitePromptVersionStore(tmp_path=tmp_path)
    store.init_schema()

    store.insert(agent_id='a1', system_prompt='v1')
    store.insert(agent_id='a1', system_prompt='v2')
    latest = store.get_latest('a1')
    assert latest.version_number == 2
    assert latest.system_prompt == 'v2'


def test_get_latest_missing_returns_none(tmp_path):
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    store = SQLitePromptVersionStore(tmp_path=tmp_path)
    store.init_schema()
    assert store.get_latest('nonexistent') is None


def test_list_for_agent_ascending(tmp_path):
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    store = SQLitePromptVersionStore(tmp_path=tmp_path)
    store.init_schema()

    store.insert(agent_id='a1', system_prompt='v1')
    store.insert(agent_id='a1', system_prompt='v2')
    store.insert(agent_id='a1', system_prompt='v3')

    versions = store.list_for_agent('a1')
    assert [v.version_number for v in versions] == [1, 2, 3]
    assert versions[0].system_prompt == 'v1'
    assert versions[-1].system_prompt == 'v3'


def test_storage_factory_returns_sqlite_prompt_version_store(tmp_path):
    import storage
    storage.reset()
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    assert isinstance(storage.prompt_versions(), SQLitePromptVersionStore)
