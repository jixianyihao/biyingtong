"""SQLiteTradeProposalStore — Phase 1 schema + Phase 2 execution fields."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from data_schema.deployment_state import (
    SCHEMA_TRADE_PROPOSALS,
    TRADE_PROPOSALS_PHASE2_ALTERS,
)

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
        execution_mode=row[13],
        execution_order_id=row[14],
        execution_error=row[15],
        executed_at=row[16],
        filled_qty=row[17],
        filled_price=row[18],
    )


def _apply_phase2_alters(con: sqlite3.Connection) -> None:
    """Idempotent ALTER TABLE ADD COLUMN for Phase 2 execution fields.

    SQLite raises sqlite3.OperationalError "duplicate column name: X" when
    the column already exists — we swallow that specific case so re-init
    on a Phase 2 database is a no-op.
    """
    for stmt in TRADE_PROPOSALS_PHASE2_ALTERS:
        try:
            con.execute(stmt)
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if 'duplicate column name' not in msg:
                raise


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
            _apply_phase2_alters(con)
            con.commit()
        finally:
            con.close()

    def insert(self, proposal: TradeProposal) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_TRADE_PROPOSALS)
            _apply_phase2_alters(con)
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
                'reason, thinking, status, decided_by, decided_at, '
                'execution_mode, execution_order_id, execution_error, '
                'executed_at, filled_qty, filled_price')

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
            _apply_phase2_alters(con)
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

    def update_execution(self, proposal_id: str, *,
                         execution_mode: str,
                         execution_order_id: str | None,
                         execution_error: str | None,
                         filled_qty: int | None,
                         filled_price: float | None,
                         executed_at: str) -> bool:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_TRADE_PROPOSALS)
            _apply_phase2_alters(con)
            cur = con.execute(
                '''UPDATE trade_proposals
                   SET execution_mode = ?,
                       execution_order_id = ?,
                       execution_error = ?,
                       filled_qty = ?,
                       filled_price = ?,
                       executed_at = ?
                   WHERE id = ?''',
                (execution_mode, execution_order_id, execution_error,
                 filled_qty, filled_price, executed_at, proposal_id),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()
