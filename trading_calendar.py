"""Trading-day calendar for A-shares.

Primary path: tq.get_trading_calendar() (tqcenter SDK).
Fallback path: unique dates present in any K-line row in vnpy_sqlite.

Usage:
    from trading_calendar import get_trading_days
    days = get_trading_days(date(2025, 4, 1), date(2026, 4, 1))
"""
from __future__ import annotations

from datetime import date, datetime


def get_trading_days(start: date, end: date) -> list[date]:
    """Return ascending list of trading days in [start, end].

    Falls back to K-line-dates if the primary TDX calendar API fails.
    """
    days = _try_tdx_calendar(start, end)
    if days is not None:
        return days
    days = _fallback_kline_dates(start, end)
    return days


def _try_tdx_calendar(start: date, end: date) -> list[date] | None:
    """Call tqcenter's calendar API. Returns None on any failure (triggers fallback)."""
    try:
        from tdx_service import tdx
        if not tdx.is_connected():
            tdx.initialize()
        if not tdx.is_connected():
            return None
        # Real signature (tqcenter source):
        #   tq.get_trading_calendar(market: str, start_time: str, end_time: str) -> List[str]
        # market is REQUIRED (e.g. 'SH' for A-shares). Dates are YYYYMMDD strings.
        # Requires client to have downloaded 上证指数 (999999) 盘后数据.
        from tqcenter import tq
        if not hasattr(tq, 'get_trading_calendar'):
            return None
        raw = tq.get_trading_calendar(
            'SH',
            start.strftime('%Y%m%d'),
            end.strftime('%Y%m%d'),
        )
        if not raw:
            return None
        days = [_coerce_date(d) for d in raw]
        return sorted(d for d in days if d and start <= d <= end)
    except Exception:  # noqa: BLE001  (any error → fallback)
        return None


def _fallback_kline_dates(start: date, end: date) -> list[date]:
    """Read unique dates from vnpy_sqlite K-line bars.

    Any trading day with at least one bar written counts. Requires that
    data/vnpy_data.db has already been populated (Task 5 or Task 9).
    """
    from scripts.setup.vnpy_config import configure
    configure()

    import sqlite3
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
        # Table doesn't exist yet (vnpy_sqlite creates on first save)
        return []
    finally:
        con.close()

    out: list[date] = []
    for (iso,) in rows:
        d = _coerce_date(iso)
        if d is not None:
            out.append(d)
    return out


def _coerce_date(value) -> date | None:
    """Accept date, datetime, or ISO string; return date or None."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value[:10]).date()
        except ValueError:
            return None
    return None
