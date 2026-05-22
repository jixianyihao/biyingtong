"""SQLiteModelStore - llm_models registry with seeded models."""


def test_sqlite_models_satisfies_protocol(tmp_path):
    from storage.base import ModelStore
    from storage.sqlite_models import SQLiteModelStore
    assert isinstance(SQLiteModelStore(tmp_path=tmp_path), ModelStore)


def test_init_schema_creates_table(tmp_path):
    from storage.sqlite_models import SQLiteModelStore
    store = SQLiteModelStore(tmp_path=tmp_path)
    store.init_schema()

    import sqlite3
    con = sqlite3.connect(tmp_path / 'agent_state.db')
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='llm_models'"
        ).fetchall()
    finally:
        con.close()
    assert len(rows) == 1


def test_seed_inserts_models(tmp_path):
    from storage.sqlite_models import SQLiteModelStore
    store = SQLiteModelStore(tmp_path=tmp_path)
    store.init_schema()
    store.seed()

    enabled = store.list_enabled()
    assert len(enabled) == 8

    ids = {m.id for m in enabled}
    assert ids == {
        'claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5',
        'gpt-5.3-codex-spark', 'gpt-5', 'gpt-4o',
        'deepseek-v3', 'gemini-2-pro',
    }


def test_get_model_by_id(tmp_path):
    from storage.sqlite_models import SQLiteModelStore
    store = SQLiteModelStore(tmp_path=tmp_path)
    store.init_schema()
    store.seed()

    m = store.get('claude-opus-4-7')
    assert m is not None
    assert m.provider == 'anthropic'
    assert m.training_cutoff == '2026-01-31'
    assert m.supports_tool_use is True
    assert m.enabled is True


def test_codex_relay_model_seeded_as_openai(tmp_path):
    from storage.sqlite_models import SQLiteModelStore
    store = SQLiteModelStore(tmp_path=tmp_path)
    store.init_schema()
    store.seed()

    m = store.get('gpt-5.3-codex-spark')
    assert m is not None
    assert m.provider == 'openai'
    assert m.api_model_id == 'gpt-5.3-codex-spark'
    assert m.supports_tool_use is True


def test_get_missing_returns_none(tmp_path):
    from storage.sqlite_models import SQLiteModelStore
    store = SQLiteModelStore(tmp_path=tmp_path)
    store.init_schema()
    store.seed()
    assert store.get('does-not-exist') is None


def test_seed_idempotent(tmp_path):
    from storage.sqlite_models import SQLiteModelStore
    store = SQLiteModelStore(tmp_path=tmp_path)
    store.init_schema()
    store.seed()
    store.seed()
    assert len(store.list_enabled()) == 8
