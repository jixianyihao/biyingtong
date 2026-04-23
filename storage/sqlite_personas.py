"""SQLitePersonaStore — personas table (agent philosophy definitions)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from data_schema.agent_state import SCHEMA_PERSONAS

from .base import Persona, PersonaStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _dumps_or_null(value):
    return None if value is None else json.dumps(value, ensure_ascii=False)


def _loads_or_none(text):
    return None if text is None else json.loads(text)


class SQLitePersonaStore(PersonaStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute(SCHEMA_PERSONAS)
            con.commit()
        finally:
            con.close()

    def upsert(self, persona: Persona) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(SCHEMA_PERSONAS)
            con.execute(
                '''INSERT OR REPLACE INTO personas
                   (id, name, style_desc, system_prompt,
                    default_pool, pool_filter, default_schedule,
                    default_rules, allowed_tools, is_builtin)
                   VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (
                    persona.id, persona.name, persona.style_desc,
                    persona.system_prompt,
                    json.dumps(persona.default_pool, ensure_ascii=False),
                    _dumps_or_null(persona.pool_filter),
                    persona.default_schedule,
                    json.dumps(persona.default_rules, ensure_ascii=False),
                    json.dumps(persona.allowed_tools, ensure_ascii=False),
                    1 if persona.is_builtin else 0,
                ),
            )
            con.commit()
        finally:
            con.close()

    def _row_to_persona(self, row) -> Persona:
        return Persona(
            id=row[0], name=row[1], style_desc=row[2],
            system_prompt=row[3],
            default_pool=json.loads(row[4]),
            pool_filter=_loads_or_none(row[5]),
            default_schedule=row[6],
            default_rules=json.loads(row[7]),
            allowed_tools=json.loads(row[8]),
            is_builtin=bool(row[9]),
            created_at=row[10],
        )

    def get(self, persona_id: str) -> Persona | None:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                '''SELECT id, name, style_desc, system_prompt,
                          default_pool, pool_filter, default_schedule,
                          default_rules, allowed_tools, is_builtin, created_at
                   FROM personas WHERE id = ?''',
                (persona_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return self._row_to_persona(row) if row else None

    def delete(self, persona_id: str) -> bool:
        """Delete by id. Does NOT check for dependent agents — caller's job.
        Returns True iff a row was removed."""
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(SCHEMA_PERSONAS)
            cur = con.execute(
                'DELETE FROM personas WHERE id = ?', (persona_id,),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    def list_all(self) -> list[Persona]:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                '''SELECT id, name, style_desc, system_prompt,
                          default_pool, pool_filter, default_schedule,
                          default_rules, allowed_tools, is_builtin, created_at
                   FROM personas ORDER BY id''',
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [self._row_to_persona(r) for r in rows]
