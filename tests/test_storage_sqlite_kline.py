"""SQLiteKlineStore — wraps vnpy_sqlite with a clean API."""
from datetime import date, datetime


def test_sqlite_kline_satisfies_protocol():
    from storage.base import KlineStore
    from storage.sqlite_kline import SQLiteKlineStore
    assert isinstance(SQLiteKlineStore(), KlineStore)


def test_save_and_load_roundtrip(vnpy_configured):
    """Save 3 bars, load them back."""
    from storage.sqlite_kline import SQLiteKlineStore
    from vnpy.trader.constant import Exchange, Interval
    from vnpy.trader.object import BarData

    store = SQLiteKlineStore()
    bars = [
        BarData(symbol='STORE_TEST_A', exchange=Exchange.SSE,
                datetime=datetime(2025, 1, 3), interval=Interval.DAILY,
                open_price=10.0, high_price=10.5, low_price=9.8, close_price=10.2,
                volume=500_000, turnover=0.0, open_interest=0.0, gateway_name='TDX'),
        BarData(symbol='STORE_TEST_A', exchange=Exchange.SSE,
                datetime=datetime(2025, 1, 6), interval=Interval.DAILY,
                open_price=10.2, high_price=10.6, low_price=10.0, close_price=10.4,
                volume=600_000, turnover=0.0, open_interest=0.0, gateway_name='TDX'),
        BarData(symbol='STORE_TEST_A', exchange=Exchange.SSE,
                datetime=datetime(2025, 1, 7), interval=Interval.DAILY,
                open_price=10.4, high_price=10.8, low_price=10.3, close_price=10.5,
                volume=700_000, turnover=0.0, open_interest=0.0, gateway_name='TDX'),
    ]
    assert store.save_bars(bars) == 3

    loaded = store.load_range('STORE_TEST_A', '1d',
                              datetime(2025, 1, 1), datetime(2025, 1, 10))
    assert len(loaded) == 3
    assert loaded[0].open_price == 10.0
    assert loaded[-1].close_price == 10.5
    assert loaded[0].volume == 500_000


def test_get_recent_returns_last_n(vnpy_configured):
    """Requires P0-populated data/vnpy_data.db with ≥20 茅台 bars."""
    from storage.sqlite_kline import SQLiteKlineStore
    store = SQLiteKlineStore()
    bars = store.get_recent('600519', '1d', 20)
    assert 10 <= len(bars) <= 20
    dts = [b.datetime for b in bars]
    assert dts == sorted(dts)


def test_get_closes(vnpy_configured):
    from storage.sqlite_kline import SQLiteKlineStore
    store = SQLiteKlineStore()
    closes = store.get_closes('600519', 30)
    assert len(closes) <= 30
    assert all(isinstance(c, float) for c in closes)
    assert all(c > 0 for c in closes)


def test_distinct_dates(vnpy_configured):
    """After P0, vnpy_data.db has 243 trading days for 2025-04-01..2026-04-01."""
    from storage.sqlite_kline import SQLiteKlineStore
    store = SQLiteKlineStore()
    days = store.distinct_dates(date(2025, 4, 1), date(2026, 4, 1))
    assert 200 <= len(days) <= 260
    assert days == sorted(days)


def test_connection_closed_between_calls(vnpy_configured):
    """Every save/load pair must close its peewee connection."""
    from storage.sqlite_kline import SQLiteKlineStore
    store = SQLiteKlineStore()
    _ = store.get_recent('600519', '1d', 5)
    _ = store.get_recent('600519', '1d', 10)
    _ = store.get_closes('600519', 30)
