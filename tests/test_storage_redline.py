"""SQLiteRedLineStore — single-row config with defaults fallback."""


def test_get_on_empty_returns_defaults(tmp_path):
    from storage.sqlite_redline import SQLiteRedLineStore
    from validation.base import DEFAULT_REDLINES
    s = SQLiteRedLineStore(tmp_path=tmp_path)
    s.init_schema()
    assert s.get() == DEFAULT_REDLINES


def test_set_then_get_roundtrip(tmp_path):
    from storage.sqlite_redline import SQLiteRedLineStore
    from validation.base import DEFAULT_REDLINES
    s = SQLiteRedLineStore(tmp_path=tmp_path)
    s.init_schema()
    custom = {**DEFAULT_REDLINES, 'position_max_pct': 10.0}
    s.set(custom)
    assert s.get()['position_max_pct'] == 10.0


def test_set_is_single_row(tmp_path):
    """Calling set() twice must not grow the table."""
    import sqlite3
    from storage.sqlite_redline import SQLiteRedLineStore
    from validation.base import DEFAULT_REDLINES
    s = SQLiteRedLineStore(tmp_path=tmp_path)
    s.init_schema()
    s.set({**DEFAULT_REDLINES, 'position_max_pct': 12.0})
    s.set({**DEFAULT_REDLINES, 'position_max_pct': 8.0})
    con = sqlite3.connect(tmp_path / 'agent_state.db')
    try:
        n = con.execute('SELECT COUNT(*) FROM redlines').fetchone()[0]
    finally:
        con.close()
    assert n == 1
    assert s.get()['position_max_pct'] == 8.0
