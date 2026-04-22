"""SQLitePromptVersionStore — immutable per-agent prompt history."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from data_schema.agent_state import (
    SCHEMA_PROMPT_VERSIONS, SCHEMA_PROMPT_VERSION_INDEX,
)

from .base import PromptVersion, PromptVersionStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


class SQLitePromptVersionStore(PromptVersionStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute(SCHEMA_PROMPT_VERSIONS)
            con.execute(SCHEMA_PROMPT_VERSION_INDEX)
            con.commit()
        finally:
            con.close()

    def insert(
        self, agent_id: str, system_prompt: str, note: str | None = None,
    ) -> PromptVersion:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(SCHEMA_PROMPT_VERSIONS)
            con.execute(SCHEMA_PROMPT_VERSION_INDEX)

            # Compute next version_number for this agent
            row = con.execute(
                'SELECT COALESCE(MAX(version_number), 0) FROM prompt_versions '
                'WHERE agent_id = ?',
                (agent_id,),
            ).fetchone()
            next_version = (row[0] if row else 0) + 1

            cursor = con.execute(
                '''INSERT INTO prompt_versions
                   (agent_id, version_number, system_prompt, note)
                   VALUES (?, ?, ?, ?)''',
                (agent_id, next_version, system_prompt, note),
            )
            new_id = cursor.lastrowid
            con.commit()

            row = con.execute(
                '''SELECT id, agent_id, version_number, system_prompt,
                          created_at, note
                   FROM prompt_versions WHERE id = ?''',
                (new_id,),
            ).fetchone()
        finally:
            con.close()
        return PromptVersion(
            id=row[0], agent_id=row[1], version_number=row[2],
            system_prompt=row[3], created_at=row[4], note=row[5],
        )

    def _row_to_version(self, row) -> PromptVersion:
        return PromptVersion(
            id=row[0], agent_id=row[1], version_number=row[2],
            system_prompt=row[3], created_at=row[4], note=row[5],
        )

    def get_latest(self, agent_id: str) -> PromptVersion | None:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                '''SELECT id, agent_id, version_number, system_prompt,
                          created_at, note
                   FROM prompt_versions WHERE agent_id = ?
                   ORDER BY version_number DESC LIMIT 1''',
                (agent_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return self._row_to_version(row) if row else None

    def list_for_agent(self, agent_id: str) -> list[PromptVersion]:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                '''SELECT id, agent_id, version_number, system_prompt,
                          created_at, note
                   FROM prompt_versions WHERE agent_id = ?
                   ORDER BY version_number ASC''',
                (agent_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [self._row_to_version(r) for r in rows]
