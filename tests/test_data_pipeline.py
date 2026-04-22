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
