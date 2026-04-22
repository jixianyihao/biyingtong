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
