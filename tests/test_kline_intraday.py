from datetime import datetime
from unittest.mock import MagicMock, patch

from storage.sqlite_kline import _interval


def test_5m_interval_resolves():
    iv = _interval('5m')
    # Must be vnpy Interval.MINUTE_5 or closest match
    assert iv is not None
    assert str(iv) not in ('Interval.DAILY', 'Interval.WEEKLY')


def test_load_single_stock_5m_builds_bar_with_minute_interval(monkeypatch):
    from scripts.setup import load_kline_intraday as mod
    from vnpy.trader.constant import Interval

    fake_raw = [{
        'date': '2026-04-23 14:55:00',
        'open': 100.0, 'high': 100.5, 'low': 99.8, 'close': 100.3,
        'vol': 10,  # lots
    }]
    monkeypatch.setattr('tdx_service.tdx.ensure_connected', lambda: True)
    monkeypatch.setattr('tdx_service.tdx.get_kline',
                        lambda full, period, count: fake_raw)

    captured = {}
    import storage
    store = storage.kline()
    orig_save = store.save_bars

    def spy(bars):
        captured['bars'] = list(bars)
        return len(bars)
    monkeypatch.setattr(store, 'save_bars', spy)

    n = mod.load_single_stock_5m('600519',
                                  start=datetime(2026, 4, 23),
                                  end=datetime(2026, 4, 23, 23, 59))
    assert n == 1
    # Plan calls for Interval.MINUTE_5; this vnpy version may lack it, in
    # which case the loader falls back to Interval.MINUTE per the plan's
    # getattr(..., None) pattern. Accept whichever is present.
    expected_interval = getattr(Interval, 'MINUTE_5', None) or Interval.MINUTE
    assert captured['bars'][0].interval == expected_interval
    assert captured['bars'][0].volume == 10 * 100
