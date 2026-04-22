"""Smoke test for persona schema DDL."""
import sqlite3


def test_personas_schema_applies_cleanly(tmp_path):
    from data_schema.agent_state import SCHEMA_PERSONAS
    db = tmp_path / 'test.db'
    con = sqlite3.connect(db)
    try:
        con.execute(SCHEMA_PERSONAS)
        con.commit()
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='personas'"
        ).fetchall()
    finally:
        con.close()
    assert len(rows) == 1


def test_agents_schema_applies_cleanly(tmp_path):
    from data_schema.agent_state import SCHEMA_PERSONAS, SCHEMA_AGENTS
    db = tmp_path / 'test.db'
    con = sqlite3.connect(db)
    try:
        con.execute(SCHEMA_PERSONAS)
        con.execute(SCHEMA_AGENTS)
        con.commit()
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agents'"
        ).fetchall()
    finally:
        con.close()
    assert len(rows) == 1


def test_prompt_versions_schema_applies_cleanly(tmp_path):
    from data_schema.agent_state import (
        SCHEMA_PERSONAS, SCHEMA_AGENTS, SCHEMA_PROMPT_VERSIONS,
        SCHEMA_PROMPT_VERSION_INDEX,
    )
    db = tmp_path / 'test.db'
    con = sqlite3.connect(db)
    try:
        con.execute(SCHEMA_PERSONAS)
        con.execute(SCHEMA_AGENTS)
        con.execute(SCHEMA_PROMPT_VERSIONS)
        con.execute(SCHEMA_PROMPT_VERSION_INDEX)
        con.commit()
    finally:
        con.close()


def _sample_persona():
    from storage.base import Persona
    return Persona(
        id='test_p', name='Test Persona',
        style_desc='Test style',
        system_prompt='You are a test agent.',
        default_pool=['600519.SH', '000858.SZ'],
        pool_filter=None,
        default_schedule='weekly',
        default_rules={'position_max_pct': 20.0, 'cash_min_pct': 5.0},
        allowed_tools=['get_kline', 'get_financials'],
        is_builtin=True,
    )


def test_sqlite_persona_store_satisfies_protocol(tmp_path):
    from storage.base import PersonaStore
    from storage.sqlite_personas import SQLitePersonaStore
    assert isinstance(SQLitePersonaStore(tmp_path=tmp_path), PersonaStore)


def test_upsert_and_get(tmp_path):
    from storage.sqlite_personas import SQLitePersonaStore
    store = SQLitePersonaStore(tmp_path=tmp_path)
    store.init_schema()

    p = _sample_persona()
    store.upsert(p)

    loaded = store.get('test_p')
    assert loaded is not None
    assert loaded.id == 'test_p'
    assert loaded.name == 'Test Persona'
    assert loaded.default_pool == ['600519.SH', '000858.SZ']
    assert loaded.default_rules == {'position_max_pct': 20.0, 'cash_min_pct': 5.0}
    assert loaded.allowed_tools == ['get_kline', 'get_financials']
    assert loaded.is_builtin is True
    assert loaded.created_at is not None


def test_upsert_replaces_existing(tmp_path):
    from storage.sqlite_personas import SQLitePersonaStore
    store = SQLitePersonaStore(tmp_path=tmp_path)
    store.init_schema()

    p = _sample_persona()
    store.upsert(p)

    # Re-upsert with changed system_prompt
    from dataclasses import replace
    p2 = replace(p, system_prompt='Updated prompt.')
    store.upsert(p2)

    loaded = store.get('test_p')
    assert loaded.system_prompt == 'Updated prompt.'

    # Still only one row
    assert len(store.list_all()) == 1


def test_get_missing_returns_none(tmp_path):
    from storage.sqlite_personas import SQLitePersonaStore
    store = SQLitePersonaStore(tmp_path=tmp_path)
    store.init_schema()
    assert store.get('nonexistent') is None


def test_list_all_sorted_by_id(tmp_path):
    from storage.sqlite_personas import SQLitePersonaStore
    store = SQLitePersonaStore(tmp_path=tmp_path)
    store.init_schema()

    from dataclasses import replace
    p = _sample_persona()
    store.upsert(replace(p, id='z_later'))
    store.upsert(replace(p, id='a_earlier'))

    ids = [row.id for row in store.list_all()]
    assert ids == ['a_earlier', 'z_later']


def test_pool_filter_roundtrip_with_none(tmp_path):
    from storage.sqlite_personas import SQLitePersonaStore
    from dataclasses import replace
    store = SQLitePersonaStore(tmp_path=tmp_path)
    store.init_schema()

    p = _sample_persona()
    store.upsert(p)
    loaded = store.get('test_p')
    assert loaded.pool_filter is None


def test_pool_filter_roundtrip_with_dict(tmp_path):
    from storage.sqlite_personas import SQLitePersonaStore
    from dataclasses import replace
    store = SQLitePersonaStore(tmp_path=tmp_path)
    store.init_schema()

    p = replace(_sample_persona(), pool_filter={'top_momentum': 15, 'top_value': 10})
    store.upsert(p)
    loaded = store.get('test_p')
    assert loaded.pool_filter == {'top_momentum': 15, 'top_value': 10}


def test_storage_factory_returns_sqlite_persona_store(tmp_path, monkeypatch):
    """storage.personas() returns SQLitePersonaStore by default."""
    import storage
    storage.reset()
    from storage.sqlite_personas import SQLitePersonaStore
    assert isinstance(storage.personas(), SQLitePersonaStore)
