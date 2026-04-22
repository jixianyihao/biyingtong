"""SQLiteAuditStore — append-only log. Never truncated in MVP (Spec § 7.5)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from data_schema.validation_state import SCHEMA_AUDIT_LOG

from .base import AuditStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _row_to_dict(row) -> dict:
    return {
        'id': row[0], 'timestamp': row[1], 'kind': row[2],
        'agent_id': row[3], 'persona_id': row[4], 'model_id': row[5],
        'prompt_version': row[6],
        'details': json.loads(row[7]) if row[7] else {},
    }


class SQLiteAuditStore(AuditStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_AUDIT_LOG)
            con.commit()
        finally:
            con.close()

    def log(self, entry) -> int:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_AUDIT_LOG)
            cur = con.execute(
                '''INSERT INTO audit_log
                   (kind, agent_id, persona_id, model_id,
                    prompt_version, details)
                   VALUES (?,?,?,?,?,?)''',
                (entry.kind, entry.agent_id, entry.persona_id,
                 entry.model_id, entry.prompt_version,
                 json.dumps(entry.details, ensure_ascii=False)),
            )
            con.commit()
            return cur.lastrowid
        finally:
            con.close()

    def query_by_agent(self, agent_id: str, limit: int = 100) -> list[dict]:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                '''SELECT id, timestamp, kind, agent_id, persona_id, model_id,
                          prompt_version, details
                   FROM audit_log WHERE agent_id = ?
                   ORDER BY id DESC LIMIT ?''',
                (agent_id, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_dict(r) for r in rows]

    def query_by_kind(self, kind: str, limit: int = 100) -> list[dict]:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                '''SELECT id, timestamp, kind, agent_id, persona_id, model_id,
                          prompt_version, details
                   FROM audit_log WHERE kind = ?
                   ORDER BY id DESC LIMIT ?''',
                (kind, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_dict(r) for r in rows]
