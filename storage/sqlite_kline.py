"""SQLiteKlineStore — KlineStore implementation backed by vnpy_sqlite.

Each public method opens a fresh vnpy_sqlite.Database() instance and closes
its peewee connection in finally. This is verbose but avoids the
'Connection already opened' error that vnpy_sqlite's module-level peewee
singleton causes when held open across usages.

This class does NOT do unit conversions. Volume-in-lots-vs-shares is the
ingestion layer's responsibility (scripts/setup/load_kline.py).
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from .base import KlineStore


_INTERVAL_MAP = None  # Lazy-initialized after vnpy_config runs


def _configure_vnpy_once() -> None:
    from scripts.setup.vnpy_config import configure
    configure()


def _interval(period: str):
    global _INTERVAL_MAP
    if _INTERVAL_MAP is None:
        _configure_vnpy_once()
        from vnpy.trader.constant import Interval
        _INTERVAL_MAP = {}
        for key, name in (('1d', 'DAILY'), ('1w', 'WEEKLY'), ('1M', 'MONTHLY')):
            val = getattr(Interval, name, None)
            if val is not None:
                _INTERVAL_MAP[key] = val
    iv = _INTERVAL_MAP.get(period)
    if iv is None:
        raise ValueError(f"unsupported period {period!r}; must be one of {list(_INTERVAL_MAP.keys())}")
    return iv


def _exchange_for(code: str):
    _configure_vnpy_once()
    from vnpy.trader.constant import Exchange
    if '.' in code:
        bare, suffix = code.split('.', 1)
        # Explicit suffix wins over prefix inference. Critical for indices
        # like 000300.SH (CSI 300) whose prefix '0' would otherwise mis-route
        # to SZSE.
        if suffix.upper() in ('SH', 'SSE'):
            return Exchange.SSE, bare
        if suffix.upper() in ('SZ', 'SZSE'):
            return Exchange.SZSE, bare
        bare_used = bare
    else:
        bare_used = code
    if bare_used.startswith(('6', '9')):
        return Exchange.SSE, bare_used
    if bare_used.startswith(('0', '3')):
        return Exchange.SZSE, bare_used
    return Exchange.SSE, bare_used


class SQLiteKlineStore(KlineStore):
    """KlineStore backed by vnpy_sqlite (peewee + SQLite)."""

    def save_bars(self, bars: list) -> int:
        if not bars:
            return 0
        _configure_vnpy_once()
        from vnpy_sqlite import Database
        db = Database()
        try:
            db.save_bar_data(bars)
            return len(bars)
        finally:
            db.db.close()

    def load_range(self, code: str, period: str,
                   start: datetime, end: datetime) -> list:
        _configure_vnpy_once()
        from vnpy_sqlite import Database
        exchange, bare = _exchange_for(code)
        iv = _interval(period)
        db = Database()
        try:
            return list(db.load_bar_data(bare, exchange, iv, start=start, end=end))
        finally:
            db.db.close()

    def get_recent(self, code: str, period: str, count: int) -> list:
        end = datetime.now()
        start = end - timedelta(days=count * 3 + 60)
        bars = self.load_range(code, period, start, end)
        return bars[-count:] if len(bars) > count else bars

    def get_closes(self, code: str, count: int) -> list[float]:
        bars = self.get_recent(code, '1d', count)
        return [float(b.close_price) for b in bars]

    def distinct_dates(self, start: date, end: date) -> list[date]:
        """Direct SQL — vnpy_sqlite table is `dbbardata` (peewee snake_case)."""
        from scripts.setup.vnpy_config import configure
        db_path = configure()
        con = sqlite3.connect(db_path)
        try:
            rows = con.execute(
                'SELECT DISTINCT DATE(datetime) FROM dbbardata '
                'WHERE DATE(datetime) >= ? AND DATE(datetime) <= ? '
                'ORDER BY DATE(datetime)',
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()

        out: list[date] = []
        for (iso,) in rows:
            try:
                out.append(datetime.fromisoformat(iso[:10]).date())
            except (TypeError, ValueError):
                continue
        return out
