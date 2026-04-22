"""DDL sanity checks for P2b validation tables."""
import sqlite3


def test_schemas_create_expected_tables(tmp_path):
    from data_schema.validation_state import (
        SCHEMA_REDLINES, SCHEMA_STOCK_STATUS, SCHEMA_AUDIT_LOG,
    )
    db = tmp_path / 'x.db'
    con = sqlite3.connect(db)
    try:
        con.executescript(SCHEMA_REDLINES)
        con.executescript(SCHEMA_STOCK_STATUS)
        con.executescript(SCHEMA_AUDIT_LOG)
        names = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    finally:
        con.close()
    assert {'redlines', 'stock_status', 'audit_log'} <= names


def test_redlines_is_single_row():
    """redlines uses id=1 as the sole row — enforced by CHECK."""
    from data_schema.validation_state import SCHEMA_REDLINES
    assert 'CHECK' in SCHEMA_REDLINES
    assert 'id = 1' in SCHEMA_REDLINES or 'id=1' in SCHEMA_REDLINES


def test_audit_log_has_indexes():
    from data_schema.validation_state import SCHEMA_AUDIT_LOG
    assert 'audit_by_agent' in SCHEMA_AUDIT_LOG
    assert 'audit_by_kind' in SCHEMA_AUDIT_LOG
