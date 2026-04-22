"""SQLiteStockStatusStore — per-code ST/suspended flags."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from data_schema.validation_state import SCHEMA_STOCK_STATUS

from .base import StockStatusRow, StockStatusStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _row_to_obj(row) -> StockStatusRow:
    return StockStatusRow(
        code=row[0], name=row[1],
        is_st=bool(row[2]), is_suspended=bool(row[3]),
        is_delisted=bool(row[4]),
        listing_date=row[5], updated_at=row[6],
    )


class SQLiteStockStatusStore(StockStatusStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_STOCK_STATUS)
            con.commit()
        finally:
            con.close()

    def upsert(self, row: StockStatusRow) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_STOCK_STATUS)
            con.execute(
                '''INSERT OR REPLACE INTO stock_status
                   (code, name, is_st, is_suspended, is_delisted, listing_date)
                   VALUES (?,?,?,?,?,?)''',
                (row.code, row.name,
                 1 if row.is_st else 0,
                 1 if row.is_suspended else 0,
                 1 if row.is_delisted else 0,
                 row.listing_date),
            )
            con.commit()
        finally:
            con.close()

    def bulk_upsert(self, rows: list[StockStatusRow]) -> int:
        if not rows:
            return 0
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_STOCK_STATUS)
            con.executemany(
                '''INSERT OR REPLACE INTO stock_status
                   (code, name, is_st, is_suspended, is_delisted, listing_date)
                   VALUES (?,?,?,?,?,?)''',
                [(r.code, r.name,
                  1 if r.is_st else 0,
                  1 if r.is_suspended else 0,
                  1 if r.is_delisted else 0,
                  r.listing_date) for r in rows],
            )
            con.commit()
        finally:
            con.close()
        return len(rows)

    def get(self, code: str) -> StockStatusRow | None:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                '''SELECT code, name, is_st, is_suspended, is_delisted,
                          listing_date, updated_at
                   FROM stock_status WHERE code = ?''',
                (code,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return _row_to_obj(row) if row else None

    def is_st(self, code: str) -> bool:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                'SELECT is_st FROM stock_status WHERE code = ?', (code,)
            ).fetchone()
        except sqlite3.OperationalError:
            return False
        finally:
            con.close()
        return bool(row[0]) if row else False

    def is_suspended(self, code: str) -> bool:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                'SELECT is_suspended FROM stock_status WHERE code = ?', (code,)
            ).fetchone()
        except sqlite3.OperationalError:
            return False
        finally:
            con.close()
        return bool(row[0]) if row else False
