"""SQLiteAgentStore — agents table + atomic prompt-version-on-create."""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from data_schema.agent_state import SCHEMA_AGENTS

from .base import Agent, AgentStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


class SQLiteAgentStore(AgentStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute(SCHEMA_AGENTS)
            con.commit()
        finally:
            con.close()

    def create_from_persona(
        self,
        persona_id: str,
        model_id: str,
        display_name: str,
        rules_override: dict | None = None,
        initial_capital: float = 1_000_000,
    ) -> Agent:
        # Fetch persona via factory (caller is responsible for wiring)
        from . import personas as _personas_factory
        from . import prompt_versions as _pv_factory

        persona = _personas_factory().get(persona_id)
        if persona is None:
            raise ValueError(f'persona {persona_id!r} not found; seed or upsert it first')

        agent_id = f'{persona_id}_{uuid.uuid4().hex[:8]}'

        rules_override_dict = rules_override or {}
        rules_json = json.dumps(rules_override_dict, ensure_ascii=False)

        # Step 1: insert Agent row (current_prompt_version_id=NULL)
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(SCHEMA_AGENTS)
            con.execute(
                '''INSERT INTO agents
                   (id, persona_id, model_id, display_name, rules_override,
                    initial_capital, status, subprocess_pid, health_score,
                    trust_rating, current_prompt_version_id)
                   VALUES (?, ?, ?, ?, ?, ?, 'created', NULL, 100, 'A', NULL)''',
                (agent_id, persona_id, model_id, display_name,
                 rules_json, float(initial_capital)),
            )
            con.commit()
        finally:
            con.close()

        # Step 2: insert initial PromptVersion v1 with persona.system_prompt
        pv = _pv_factory().insert(
            agent_id=agent_id,
            system_prompt=persona.system_prompt,
            note='initial version (from persona at creation time)',
        )

        # Step 3: backfill agents.current_prompt_version_id
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(
                'UPDATE agents SET current_prompt_version_id = ? WHERE id = ?',
                (pv.id, agent_id),
            )
            con.commit()
        finally:
            con.close()

        loaded = self.get(agent_id)
        assert loaded is not None
        return loaded

    def _row_to_agent(self, row) -> Agent:
        return Agent(
            id=row[0], persona_id=row[1], model_id=row[2],
            display_name=row[3],
            rules_override=json.loads(row[4]),
            initial_capital=row[5],
            status=row[6],
            subprocess_pid=row[7],
            health_score=row[8],
            trust_rating=row[9],
            current_prompt_version_id=row[10],
            created_at=row[11],
        )

    def get(self, agent_id: str) -> Agent | None:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                '''SELECT id, persona_id, model_id, display_name,
                          rules_override, initial_capital, status,
                          subprocess_pid, health_score, trust_rating,
                          current_prompt_version_id, created_at
                   FROM agents WHERE id = ?''',
                (agent_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return self._row_to_agent(row) if row else None

    def list_all(self) -> list[Agent]:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                '''SELECT id, persona_id, model_id, display_name,
                          rules_override, initial_capital, status,
                          subprocess_pid, health_score, trust_rating,
                          current_prompt_version_id, created_at
                   FROM agents ORDER BY created_at''',
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [self._row_to_agent(r) for r in rows]

    def update_status(self, agent_id: str, status: str) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(SCHEMA_AGENTS)
            con.execute(
                'UPDATE agents SET status = ? WHERE id = ?',
                (status, agent_id),
            )
            con.commit()
        finally:
            con.close()

    def update_health(self, agent_id: str, health: int,
                      rating: str) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(
                '''UPDATE agents
                   SET health_score = ?, trust_rating = ?
                   WHERE id = ?''',
                (int(health), rating, agent_id),
            )
            con.commit()
        finally:
            con.close()

    def update(self, agent_id: str, *,
               display_name: str | None = None,
               rules_override: dict | None = None) -> None:
        """Partial update — None means skip that field. Noop if no kwargs
        or if agent_id doesn't exist (sqlite UPDATE with no match is silent)."""
        if display_name is None and rules_override is None:
            return

        sets: list[str] = []
        vals: list = []
        if display_name is not None:
            sets.append('display_name = ?')
            vals.append(display_name)
        if rules_override is not None:
            sets.append('rules_override = ?')
            vals.append(json.dumps(rules_override, ensure_ascii=False))
        vals.append(agent_id)

        con = sqlite3.connect(self._db_path)
        try:
            con.execute(SCHEMA_AGENTS)
            con.execute(
                f'UPDATE agents SET {", ".join(sets)} WHERE id = ?',
                tuple(vals),
            )
            con.commit()
        finally:
            con.close()

    def delete(self, agent_id: str) -> bool:
        """Hard delete agent + its prompt_versions. backtest_results are
        preserved (they reference agent_id by value, not FK)."""
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(SCHEMA_AGENTS)
            cur = con.execute(
                'DELETE FROM agents WHERE id = ?', (agent_id,),
            )
            removed = cur.rowcount > 0
            if removed:
                con.execute(
                    'DELETE FROM prompt_versions WHERE agent_id = ?',
                    (agent_id,),
                )
            con.commit()
        finally:
            con.close()
        return removed

    def set_current_prompt_version(self, agent_id: str, version_id: int) -> None:
        """Point agents.current_prompt_version_id at version_id.
        Silent if agent_id doesn't exist (UPDATE with no match)."""
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(
                'UPDATE agents SET current_prompt_version_id = ? WHERE id = ?',
                (int(version_id), agent_id),
            )
            con.commit()
        finally:
            con.close()
