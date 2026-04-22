"""SQLiteFinancialStore — financial_cache.db (PE/PB/ROE/growth/margins)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .base import FinancialStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]

_SCHEMA = '''
CREATE TABLE IF NOT EXISTS financial_data (
    stock_code         TEXT NOT NULL,
    date               DATE NOT NULL,
    pe                 REAL,
    pb                 REAL,
    roe                REAL,
    gross_margin       REAL,
    revenue_growth     REAL,
    net_profit_growth  REAL,
    PRIMARY KEY (stock_code, date)
);
'''


class SQLiteFinancialStore(FinancialStore):
    def __init__(self, tmp_path: Path | None = None):
        """tmp_path: override data dir for tests. None = production path."""
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        base.mkdir(parents=True, exist_ok=True) if hasattr(base, 'mkdir') else None
        self._db_path = Path(base) / 'financial_cache.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute(_SCHEMA)
            con.commit()
        finally:
            con.close()

    def upsert(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        con = sqlite3.connect(self._db_path)
        written = 0
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute(_SCHEMA)
            for r in rows:
                con.execute(
                    '''INSERT OR REPLACE INTO financial_data
                       (stock_code, date, pe, pb, roe, gross_margin,
                        revenue_growth, net_profit_growth)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        r.get('stock_code'),
                        r.get('date'),
                        r.get('pe'),
                        r.get('pb'),
                        r.get('roe'),
                        r.get('gross_margin'),
                        r.get('revenue_growth'),
                        r.get('net_profit_growth'),
                    ),
                )
                written += 1
            con.commit()
        finally:
            con.close()
        return written

    def get_latest(self, code: str) -> dict | None:
        bare = code.split('.', 1)[0] if '.' in code else code
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                '''SELECT stock_code, date, pe, pb, roe, gross_margin,
                          revenue_growth, net_profit_growth
                   FROM financial_data WHERE stock_code = ?
                   ORDER BY date DESC LIMIT 1''',
                (bare,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        if row is None:
            return None
        return {
            'stock_code': row[0], 'date': row[1],
            'pe': row[2], 'pb': row[3], 'roe': row[4],
            'gross_margin': row[5],
            'revenue_growth': row[6], 'net_profit_growth': row[7],
        }
