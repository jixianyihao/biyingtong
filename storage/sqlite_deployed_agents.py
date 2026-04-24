"""SQLiteDeployedAgentStore — Phase 1 subprocess tracking."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from data_schema.deployment_state import SCHEMA_DEPLOYED_AGENTS

from .base import DeployedAgent, DeployedAgentStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _row_to_deployed(row) -> DeployedAgent:
    return DeployedAgent(
        agent_id=row[0], pid=row[1],
        started_at=row[2], status=row[3], schedule=row[4],
    )


class SQLiteDeployedAgentStore(DeployedAgentStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_DEPLOYED_AGENTS)
            con.commit()
        finally:
            con.close()

    def upsert(self, agent_id: str, pid: int, schedule: str) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_DEPLOYED_AGENTS)
            con.execute(
                '''INSERT OR REPLACE INTO deployed_agents
                   (agent_id, pid, status, schedule)
                   VALUES (?, ?, 'running', ?)''',
                (agent_id, int(pid), schedule),
            )
            con.commit()
        finally:
            con.close()

    def get(self, agent_id: str) -> DeployedAgent | None:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                'SELECT agent_id, pid, started_at, status, schedule '
                'FROM deployed_agents WHERE agent_id = ?',
                (agent_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return _row_to_deployed(row) if row else None

    def list_running(self) -> list:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                'SELECT agent_id, pid, started_at, status, schedule '
                "FROM deployed_agents WHERE status = 'running' "
                'ORDER BY started_at DESC',
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_deployed(r) for r in rows]

    def mark_stopped(self, agent_id: str) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(
                "UPDATE deployed_agents SET status='stopped' WHERE agent_id=?",
                (agent_id,),
            )
            con.commit()
        finally:
            con.close()

    def mark_crashed(self, agent_id: str) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(
                "UPDATE deployed_agents SET status='crashed' WHERE agent_id=?",
                (agent_id,),
            )
            con.commit()
        finally:
            con.close()
