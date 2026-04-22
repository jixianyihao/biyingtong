"""Integration tests for P0 data pipelines.

These hit real TDX and are skipped if TDX is offline.
"""
from datetime import datetime


def test_kline_single_stock_roundtrip(tdx_ready, vnpy_configured):
    """茅台 1 year daily: load via tqcenter bridge → save to vnpy_sqlite → read back ~244 bars."""
    from scripts.setup.load_kline import load_single_stock

    start = datetime(2025, 4, 1)
    end = datetime(2026, 4, 1)
    written = load_single_stock(symbol='600519', start=start, end=end)

    assert written >= 200, f'expected ≥200 bars for 600519, got {written}'

    # Read back via vnpy's API
    from vnpy_sqlite import Database
    from vnpy.trader.constant import Exchange, Interval

    db = Database()
    bars = db.load_bar_data(
        symbol='600519',
        exchange=Exchange.SSE,
        interval=Interval.DAILY,
        start=start,
        end=end,
    )
    assert len(bars) == written, 'roundtrip count mismatch'
    first = bars[0]
    assert first.high_price >= first.low_price > 0
    assert first.open_price > 0 and first.close_price > 0
    assert first.volume >= 0


def test_kline_batch_hs300_top50(tdx_ready, vnpy_configured):
    """Top 50 HS300 constituents: batch load succeeds on ≥ 45/50."""
    from scripts.setup.load_kline import load_batch

    # A known-stable subset of HS300 (large caps). Full HS300 list loading
    # happens in the real setup run (Task 11), not here.
    top50 = [
        '600519', '601398', '601288', '601988', '600036',  # banks + liquor
        '600900', '601318', '600028', '600030', '600048',
        '600050', '601166', '601328', '601857', '601006',
        '600887', '000858', '000001', '000002', '000333',
        '000568', '000625', '000651', '000725', '000776',
        '000858', '000895', '002142', '002230', '002304',
        '002415', '002475', '002594', '002714', '300059',
        '300122', '300124', '300142', '300347', '300408',
        '300413', '300498', '300628', '300750', '300760',
        '600000', '600016', '600019', '600031', '600104',
    ]
    from datetime import datetime
    start = datetime(2025, 4, 1)
    end = datetime(2026, 4, 1)

    results = load_batch(top50, start, end)
    successful = sum(1 for cnt in results.values() if cnt >= 200)
    assert successful >= 45, (
        f'only {successful}/50 stocks loaded ≥200 bars; details: '
        f'{[(s, c) for s, c in results.items() if c < 200]}'
    )


def test_trading_calendar_returns_valid_dates(tdx_ready):
    """After migration: uses storage.calendar() (Task 3)."""
    from datetime import date
    from storage import calendar as storage_calendar

    days = storage_calendar().get_trading_days(date(2025, 4, 1), date(2025, 4, 30))
    assert 18 <= len(days) <= 23, f'expected 18–23 trading days in Apr 2025, got {len(days)}'
    for d in days:
        assert d.weekday() < 5, f'{d} is a weekend'
    assert days == sorted(days)


def test_trading_calendar_fallback_when_tdx_api_missing(vnpy_configured, monkeypatch):
    """Force fallback path."""
    from datetime import date
    from storage.sqlite_calendar import SQLiteCalendarStore
    import storage

    store = SQLiteCalendarStore()
    monkeypatch.setattr(store, '_try_primary', lambda *a, **kw: None)
    storage.set_calendar(store)

    days = store.get_trading_days(date(2025, 4, 1), date(2025, 4, 30))
    assert len(days) >= 15


def test_financial_cache_loads_pe_pb_roe(tdx_ready, tmp_path, monkeypatch):
    """load_financial writes PE/PB/ROE for a handful of stocks into the cache DB."""
    # Redirect the cache to tmp_path so we don't mutate real data/financial_cache.db.
    # Task 7: load_financial now uses storage.financial() rather than a module-level
    # CACHE_PATH; inject an isolated SQLiteFinancialStore instead.
    import storage
    from storage.sqlite_financial import SQLiteFinancialStore
    store = SQLiteFinancialStore(tmp_path=tmp_path)
    store.init_schema()
    storage.set_financial(store)

    from scripts.setup import load_financial as lf
    symbols = ['600519', '000858', '600036', '300750', '002415']
    written = lf.load_financial(symbols)
    assert written >= 4, f'expected ≥4/5 stocks with financial data, got {written}'

    # Verify schema + content
    import sqlite3
    con = sqlite3.connect(tmp_path / 'financial_cache.db')
    try:
        rows = con.execute(
            'SELECT stock_code, pe, pb, roe FROM financial_data'
        ).fetchall()
    finally:
        con.close()

    assert len(rows) >= 4
    for code, pe, pb, roe in rows:
        assert isinstance(code, str) and len(code) >= 6
        # PE/PB/ROE can legitimately be None (new stocks, no data); at least one must be set per row
        assert pe is not None or pb is not None or roe is not None, (
            f'{code} has all null PE/PB/ROE'
        )


def test_full_pipeline_integration(tdx_ready, vnpy_configured):
    """After setup has run, all three pipelines are queryable together."""
    # 1. K-line reads from vnpy_sqlite
    from datetime import datetime
    from vnpy_sqlite import Database
    from vnpy_sqlite.sqlite_database import db as _peewee_db
    from vnpy.trader.constant import Exchange, Interval

    # Earlier tests in this file instantiate Database() without closing; peewee's
    # SqliteDatabase is a module-level singleton so we must close any leaked
    # connection before opening a fresh one here. (Harmless if already closed.)
    if not _peewee_db.is_closed():
        _peewee_db.close()

    db = Database()
    try:
        bars = db.load_bar_data(
            symbol='600519', exchange=Exchange.SSE, interval=Interval.DAILY,
            start=datetime(2025, 4, 1), end=datetime(2026, 4, 1),
        )
    finally:
        db.db.close()
    assert len(bars) >= 200

    # 2. Financial cache has data
    import sqlite3
    from pathlib import Path
    cache = Path('data/financial_cache.db')
    assert cache.exists(), 'Run Task 11 Step 2 first'
    con = sqlite3.connect(cache)
    try:
        count = con.execute('SELECT COUNT(DISTINCT stock_code) FROM financial_data').fetchone()[0]
    finally:
        con.close()
    assert count >= 250, f'financial_cache has only {count} stocks; expected >=250'

    # 3. Trading calendar works over the same range
    from datetime import date
    from storage import calendar as storage_calendar
    days = storage_calendar().get_trading_days(date(2025, 4, 1), date(2026, 4, 1))
    # A full year: ~244 trading days
    assert 230 <= len(days) <= 260, (
        f'expected 230-260 trading days in Apr-2025 -> Apr-2026, got {len(days)}'
    )
