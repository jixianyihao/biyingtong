"""SQLiteModelStore — llm_models table (no pricing)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from data_schema.agent_state import SCHEMA_LLM_MODELS

from .base import ModelInfo, ModelStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


# (id, provider, display_name, api_model_id, training_cutoff,
#  supports_tool_use, max_tokens_out, enabled)
_SEED = [
    ('claude-opus-4-7',   'anthropic', 'Claude Opus 4.7 (1M)', 'claude-opus-4-7',           '2026-01-31', 1, 4096, 1),
    ('claude-sonnet-4-6', 'anthropic', 'Claude Sonnet 4.6',     'claude-sonnet-4-6',         '2026-01-31', 1, 4096, 1),
    ('claude-haiku-4-5',  'anthropic', 'Claude Haiku 4.5',      'claude-haiku-4-5-20251001', '2025-07-31', 1, 4096, 1),
    ('gpt-5.3-codex-spark', 'openai',  'GPT-5.3 Codex Spark (relay)', 'gpt-5.3-codex-spark', '2026-05-01', 1, 4096, 1),
    ('gpt-5',             'openai',    'GPT-5',                 'gpt-5',                     '2025-10-31', 1, 4096, 1),
    ('gpt-4o',            'openai',    'GPT-4o',                'gpt-4o',                    '2023-10-31', 1, 4096, 1),
    ('deepseek-v3',       'deepseek',  'DeepSeek V3',           'deepseek-chat',             '2025-07-31', 1, 4096, 1),
    ('gemini-2-pro',      'gemini',    'Gemini 2.0 Pro',        'gemini-2.0-pro',            '2025-08-31', 1, 4096, 1),
]


class SQLiteModelStore(ModelStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        base.mkdir(parents=True, exist_ok=True) if hasattr(base, 'mkdir') else None
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute(SCHEMA_LLM_MODELS)
            con.commit()
        finally:
            con.close()

    def seed(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(SCHEMA_LLM_MODELS)
            con.executemany(
                '''INSERT OR REPLACE INTO llm_models
                   (id, provider, display_name, api_model_id, training_cutoff,
                    supports_tool_use, max_tokens_out, enabled)
                   VALUES (?,?,?,?,?,?,?,?)''',
                _SEED,
            )
            con.commit()
        finally:
            con.close()

    def _row_to_info(self, row) -> ModelInfo:
        return ModelInfo(
            id=row[0], provider=row[1], display_name=row[2],
            api_model_id=row[3], training_cutoff=row[4],
            supports_tool_use=bool(row[5]), max_tokens_out=row[6], enabled=bool(row[7]),
        )

    def get(self, model_id: str) -> ModelInfo | None:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                '''SELECT id, provider, display_name, api_model_id, training_cutoff,
                          supports_tool_use, max_tokens_out, enabled
                   FROM llm_models WHERE id = ?''',
                (model_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return self._row_to_info(row) if row else None

    def list_enabled(self) -> list[ModelInfo]:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                '''SELECT id, provider, display_name, api_model_id, training_cutoff,
                          supports_tool_use, max_tokens_out, enabled
                   FROM llm_models WHERE enabled = 1 ORDER BY id''',
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [self._row_to_info(r) for r in rows]
