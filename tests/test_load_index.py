"""load_index — fetches index bars with forced SSE exchange, saves via storage.kline()."""
from datetime import datetime


def test_construct_index_bar_preserves_sse_exchange():
    """Unit-level: the BarData built for 000300 must be on SSE, not SZSE."""
    from scripts.setup.load_index import _build_bar
    bar = _build_bar(
        symbol='000300',
        raw={'date': '2025-11-17', 'open': 4500.0, 'high': 4550.0,
             'low': 4490.0, 'close': 4520.0, 'vol': 10_000_000},
    )
    assert bar is not None
    # Exchange enum — compare by value to avoid vnpy import leakage in the test
    assert bar.exchange.value == 'SSE'
    assert bar.symbol == '000300'
    assert bar.close_price == 4520.0


def test_bad_date_returns_none():
    from scripts.setup.load_index import _build_bar
    assert _build_bar('000300', {'date': 'garbage'}) is None


def test_missing_date_returns_none():
    from scripts.setup.load_index import _build_bar
    assert _build_bar('000300', {}) is None


def test_load_index_uses_ssc_for_hs300_code(tmp_path, monkeypatch):
    """End-to-end (mocked): load_index calls tq, builds bars, saves via kline()."""
    from scripts.setup import load_index as mod

    # Stub TDX
    class _StubTdx:
        def ensure_connected(self): return True
        def get_kline(self, full_code, period, count):
            # Shape mimics tqcenter raw rows
            return [
                {'date': '2025-11-17', 'open': 4500, 'high': 4550,
                 'low': 4490, 'close': 4520, 'vol': 1},
                {'date': '2025-11-18', 'open': 4520, 'high': 4560,
                 'low': 4510, 'close': 4545, 'vol': 1},
            ]
    monkeypatch.setattr(mod, 'tdx', _StubTdx())

    # Stub storage.kline to capture bars
    import storage
    saved_bars = []
    class _StubKline:
        def save_bars(self, bars):
            saved_bars.extend(bars)
            return len(bars)
    storage.set_kline(_StubKline())

    n = mod.load_index('000300',
                       datetime(2025, 11, 1), datetime(2025, 11, 30))
    assert n == 2
    assert all(b.exchange.value == 'SSE' for b in saved_bars)
    assert [b.close_price for b in saved_bars] == [4520.0, 4545.0]
