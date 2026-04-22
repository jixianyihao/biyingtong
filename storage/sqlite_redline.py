"""SQLiteRedLineStore — global RedLine, stored as a single JSON row."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from data_schema.validation_state import SCHEMA_REDLINES
from validation.base import DEFAULT_REDLINES

from .base import RedLineStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


class SQLiteRedLineStore(RedLineStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_REDLINES)
            con.commit()
        finally:
            con.close()

    def get(self) -> dict:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_REDLINES)
            row = con.execute(
                'SELECT values_json FROM redlines WHERE id = 1'
            ).fetchone()
        finally:
            con.close()
        if row is None:
            return dict(DEFAULT_REDLINES)
        return json.loads(row[0])

    def set(self, values: dict) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_REDLINES)
            con.execute(
                '''INSERT INTO redlines (id, values_json)
                   VALUES (1, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       values_json = excluded.values_json,
                       updated_at  = CURRENT_TIMESTAMP''',
                (json.dumps(values, ensure_ascii=False),),
            )
            con.commit()
        finally:
            con.close()
