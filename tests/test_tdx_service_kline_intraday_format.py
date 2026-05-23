from __future__ import annotations

from datetime import datetime

import pandas as pd


def test_get_kline_preserves_intraday_timestamp(monkeypatch):
    import tdx_service

    idx = pd.to_datetime([
        datetime(2026, 1, 26, 9, 31),
        datetime(2026, 1, 26, 9, 32),
    ])
    frame = pd.DataFrame({'688981.SH': [100.0, 101.0]}, index=idx)
    monkeypatch.setattr(
        tdx_service.tq,
        'get_market_data',
        lambda **kwargs: {
            'Open': frame,
            'High': frame,
            'Low': frame,
            'Close': frame,
            'Volume': frame,
        },
    )

    service = tdx_service.TDXService()
    service._initialized = True

    bars = service.get_kline('688981.SH', period='1m', count=2)

    assert bars[0]['date'] == '2026-01-26 09:31:00'
    assert bars[1]['date'] == '2026-01-26 09:32:00'
