"""SQLiteLLMDecisionCache — (agent,date,portfolio,prompt) → decisions replay."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from data_schema.backtest_state import SCHEMA_LLM_DECISION_CACHE

from .base import LLMDecisionCacheStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


class SQLiteLLMDecisionCache(LLMDecisionCacheStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_LLM_DECISION_CACHE)
            con.commit()
        finally:
            con.close()

    def has(self, cache_key: str) -> bool:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                'SELECT 1 FROM llm_decision_cache WHERE cache_key = ?',
                (cache_key,),
            ).fetchone()
        except sqlite3.OperationalError:
            return False
        finally:
            con.close()
        return row is not None

    def get(self, cache_key: str):
        from backtest.base import CachedDecision
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                '''SELECT agent_id, date, response_json
                   FROM llm_decision_cache WHERE cache_key = ?''',
                (cache_key,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        if row is None:
            return None
        payload = json.loads(row[2])
        return CachedDecision(
            agent_id=row[0], date=row[1],
            portfolio_hash=payload['portfolio_hash'],
            prompt_hash=payload['prompt_hash'],
            decisions=payload['decisions'],
        )

    def put(self, entry) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_LLM_DECISION_CACHE)
            payload = json.dumps({
                'portfolio_hash': entry.portfolio_hash,
                'prompt_hash': entry.prompt_hash,
                'decisions': entry.decisions,
            }, ensure_ascii=False)
            con.execute(
                '''INSERT OR REPLACE INTO llm_decision_cache
                   (cache_key, agent_id, date, response_json)
                   VALUES (?,?,?,?)''',
                (entry.cache_key, entry.agent_id, entry.date, payload),
            )
            con.commit()
        finally:
            con.close()
