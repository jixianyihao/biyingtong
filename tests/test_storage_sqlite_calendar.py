"""SQLiteCalendarStore — moves trading_calendar.py into storage."""
from datetime import date


def test_sqlite_calendar_satisfies_protocol():
    from storage.base import CalendarStore
    from storage.sqlite_calendar import SQLiteCalendarStore
    assert isinstance(SQLiteCalendarStore(), CalendarStore)


def test_get_trading_days_for_april_2025(tdx_ready, vnpy_configured):
    """21 trading days expected for April 2025."""
    from storage.sqlite_calendar import SQLiteCalendarStore
    store = SQLiteCalendarStore()
    days = store.get_trading_days(date(2025, 4, 1), date(2025, 4, 30))
    assert 18 <= len(days) <= 23
    for d in days:
        assert d.weekday() < 5
    assert days == sorted(days)


def test_fallback_triggers_when_primary_fails(vnpy_configured, monkeypatch):
    """If _try_primary returns None, fallback reads K-line dates."""
    from storage.sqlite_calendar import SQLiteCalendarStore
    store = SQLiteCalendarStore()
    monkeypatch.setattr(store, '_try_primary', lambda *a, **kw: None)

    days = store.get_trading_days(date(2025, 4, 1), date(2025, 4, 30))
    assert len(days) >= 15, (
        'fallback should return ≥15 trading days in Apr 2025; '
        'ensure data/vnpy_data.db populated via P0 setup'
    )


def test_trading_calendar_legacy_import_is_gone():
    """The repo-root trading_calendar.py should no longer exist."""
    from pathlib import Path
    import sys
    legacy = Path(__file__).resolve().parents[1] / 'trading_calendar.py'
    assert not legacy.exists(), (
        f'{legacy} should be deleted; use storage.calendar().get_trading_days() instead'
    )
    if 'trading_calendar' in sys.modules:
        del sys.modules['trading_calendar']
    import pytest
    with pytest.raises(ModuleNotFoundError):
        import trading_calendar  # noqa: F401
