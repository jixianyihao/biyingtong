"""SQLiteTradeProposalStore — Phase 1 (NO real-money execution)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from data_schema.deployment_state import SCHEMA_TRADE_PROPOSALS

from .base import TradeProposal, TradeProposalStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _row_to_proposal(row) -> TradeProposal:
    return TradeProposal(
        id=row[0],
        agent_id=row[1],
        created_at=row[2],
        decision_at=row[3],
        action=row[4],
        code=row[5],
        shares=row[6],
        price=row[7],
        reason=row[8],
        thinking=row[9],
        status=row[10],
        decided_by=row[11],
        decided_at=row[12],
    )


class SQLiteTradeProposalStore(TradeProposalStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_TRADE_PROPOSALS)
            con.commit()
        finally:
            con.close()

    def insert(self, proposal: TradeProposal) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_TRADE_PROPOSALS)
            con.execute(
                '''INSERT OR REPLACE INTO trade_proposals
                   (id, agent_id, decision_at, action, code, shares, price,
                    reason, thinking, status, decided_by, decided_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (proposal.id, proposal.agent_id, proposal.decision_at,
                 proposal.action, proposal.code, proposal.shares,
                 proposal.price, proposal.reason, proposal.thinking,
                 proposal.status, proposal.decided_by, proposal.decided_at),
            )
            con.commit()
        finally:
            con.close()

    def _cols(self):
        return ('id, agent_id, created_at, decision_at, '
                'action, code, shares, price, '
                'reason, thinking, status, decided_by, decided_at')

    def get(self, proposal_id: str) -> TradeProposal | None:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                f'SELECT {self._cols()} FROM trade_proposals WHERE id = ?',
                (proposal_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return _row_to_proposal(row) if row else None

    def list_pending(self, agent_id: str | None = None,
                     limit: int = 100) -> list:
        con = sqlite3.connect(self._db_path)
        try:
            if agent_id:
                rows = con.execute(
                    f'SELECT {self._cols()} FROM trade_proposals '
                    f"WHERE status = 'pending' AND agent_id = ? "
                    f'ORDER BY created_at DESC LIMIT ?',
                    (agent_id, limit),
                ).fetchall()
            else:
                rows = con.execute(
                    f'SELECT {self._cols()} FROM trade_proposals '
                    f"WHERE status = 'pending' "
                    f'ORDER BY created_at DESC LIMIT ?',
                    (limit,),
                ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_proposal(r) for r in rows]

    def list_for_agent(self, agent_id: str, limit: int = 100) -> list:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                f'SELECT {self._cols()} FROM trade_proposals '
                f'WHERE agent_id = ? '
                f'ORDER BY created_at DESC LIMIT ?',
                (agent_id, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_proposal(r) for r in rows]

    def update_status(self, proposal_id: str, status: str,
                      decided_by: str | None = None) -> bool:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_TRADE_PROPOSALS)
            cur = con.execute(
                "UPDATE trade_proposals "
                "SET status = ?, decided_by = ?, "
                "decided_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (status, decided_by, proposal_id),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()
