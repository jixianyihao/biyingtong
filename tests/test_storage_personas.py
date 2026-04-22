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
