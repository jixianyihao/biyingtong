"""P0 follow-up: K-line volume is stored in SHARES (not lots).

tqcenter returns `vol` in 手 (100 shares). vnpy BarData.volume should be
in shares, so ingestion multiplies by 100.
"""
from datetime import datetime


def test_load_single_stock_multiplies_volume_by_100(tdx_ready, vnpy_configured, monkeypatch):
    from scripts.setup import load_kline as lk

    fake_bars = [
        {'date': '2025-04-01', 'open': 10.0, 'high': 10.5, 'low': 9.8, 'close': 10.2, 'vol': 5000},
        {'date': '2025-04-02', 'open': 10.2, 'high': 10.4, 'low': 10.0, 'close': 10.3, 'vol': 3000},
    ]
    monkeypatch.setattr(lk.tdx, 'get_kline', lambda *a, **kw: fake_bars)
    monkeypatch.setattr(lk.tdx, 'ensure_connected', lambda: True)

    written = lk.load_single_stock('VOLFIXT', datetime(2025, 4, 1), datetime(2025, 4, 3))
    assert written == 2

    # Read back through storage (not direct vnpy_sqlite)
    from storage import kline
    bars = kline().load_range('VOLFIXT', '1d',
                              datetime(2025, 4, 1), datetime(2025, 4, 3))
    assert len(bars) == 2
    assert bars[0].volume == 500_000
    assert bars[1].volume == 300_000


def test_load_kline_uses_storage_not_direct_vnpy(tdx_ready, vnpy_configured):
    """Structural check: load_kline.py must not import vnpy_sqlite.Database directly."""
    from pathlib import Path
    source = Path('scripts/setup/load_kline.py').read_text(encoding='utf-8')
    assert 'from vnpy_sqlite import Database' not in source, (
        'load_kline.py must not import Database directly; use storage.kline().save_bars()'
    )
    assert 'from storage import' in source or 'import storage' in source, (
        'load_kline.py must import from storage package'
    )
