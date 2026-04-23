"""SQLiteCalendarStore — A-share trading calendar.

Primary: tqcenter's tq.get_trading_calendar(market, start, end).
Fallback: unique dates present in vnpy_sqlite K-line bars (SQLiteKlineStore).

Absorbs the former trading_calendar.py module.
"""
from __future__ import annotations

from datetime import date, datetime

from .base import CalendarStore


class SQLiteCalendarStore(CalendarStore):
    def __init__(self, tmp_path=None):
        self._tmp_path = tmp_path

    def init_schema(self) -> None:
        """No-op: CalendarStore delegates to TDX/KlineStore, no own schema."""

    def get_trading_days(self, start: date, end: date) -> list[date]:
        days = self._try_primary(start, end)
        if days is not None:
            return days
        return self._fallback(start, end)

    def _try_primary(self, start: date, end: date) -> list[date] | None:
        """Call tq.get_trading_calendar('SH', start_YYYYMMDD, end_YYYYMMDD).
        Returns None on any failure so caller triggers fallback."""
        try:
            from tdx_service import tdx
            if not tdx.is_connected():
                tdx.initialize()
            if not tdx.is_connected():
                return None
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
            return sorted(
                d for d in (_coerce_date(x) for x in raw)
                if d is not None and start <= d <= end
            )
        except Exception:  # noqa: BLE001  any error → fallback
            return None

    def _fallback(self, start: date, end: date) -> list[date]:
        """Use SQLiteKlineStore.distinct_dates — any date with a bar counts as trading."""
        from . import kline  # factory import; avoids circular
        return kline().distinct_dates(start, end)


def _coerce_date(value) -> date | None:
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
