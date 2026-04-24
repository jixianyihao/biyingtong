"""Verify get_technical uses talib + produces correct shapes + known-good math."""
from __future__ import annotations

import math
import pytest


def _with_fake_closes(monkeypatch, closes):
    """Force _get_closes to return the given list."""
    import tools.get_technical as gt
    monkeypatch.setattr(gt, '_get_closes', lambda code: closes)


def test_ma_basic(monkeypatch):
    import tools.get_technical as gt
    closes = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0,
              20.0, 21.0, 22.0, 23.0, 24.0]
    _with_fake_closes(monkeypatch, closes)
    out = gt.call({'code': '600519.SH', 'indicator': 'MA', 'period': 5})
    assert out['indicator'] == 'MA'
    assert out['period'] == 5
    assert len(out['values']) == len(closes)
    # First 4 should be NaN; 5th = mean(10..14) = 12
    assert math.isnan(out['values'][3])
    assert out['values'][4] == 12.0
    # Last value = mean(20..24) = 22.0
    assert out['values'][-1] == 22.0


def test_rsi_basic(monkeypatch):
    """RSI on a continuously-rising series should be near 100."""
    import tools.get_technical as gt
    closes = [100.0 + i for i in range(30)]
    _with_fake_closes(monkeypatch, closes)
    out = gt.call({'code': 'x', 'indicator': 'RSI', 'period': 14})
    assert out['indicator'] == 'RSI'
    assert out['period'] == 14
    # talib returns same-length output; first (period) entries NaN
    assert math.isnan(out['values'][13])
    # Rising series -> RSI near 100 at tail
    tail = out['values'][-1]
    assert not math.isnan(tail)
    assert tail > 90


def test_rsi_falling_near_zero(monkeypatch):
    import tools.get_technical as gt
    closes = [100.0 - i for i in range(30)]
    _with_fake_closes(monkeypatch, closes)
    out = gt.call({'code': 'x', 'indicator': 'RSI', 'period': 14})
    tail = out['values'][-1]
    assert tail < 10


def test_macd_shape(monkeypatch):
    import tools.get_technical as gt
    closes = [100.0 + (i % 5) for i in range(60)]
    _with_fake_closes(monkeypatch, closes)
    out = gt.call({'code': 'x', 'indicator': 'MACD'})
    assert out['indicator'] == 'MACD'
    assert len(out['dif']) == len(closes)
    assert len(out['dea']) == len(closes)
    assert len(out['bar']) == len(closes)
    # hist = 2 * (dif - dea) - preserved convention
    for i, (d, e, b) in enumerate(zip(out['dif'], out['dea'], out['bar'])):
        if math.isnan(b) or math.isnan(d) or math.isnan(e):
            continue
        # Allow small slack for independent rounding (each value rounded to 4dp).
        assert abs(b - 2 * (d - e)) < 1e-3, f'row {i}: bar={b} vs 2*(dif-dea)={2*(d-e)}'


def test_boll_shape(monkeypatch):
    import tools.get_technical as gt
    closes = [100.0 + i * 0.5 for i in range(40)]
    _with_fake_closes(monkeypatch, closes)
    out = gt.call({'code': 'x', 'indicator': 'BOLL', 'period': 20})
    assert out['indicator'] == 'BOLL'
    assert out['period'] == 20
    # middle is SMA(20); upper > middle > lower at the end
    assert not math.isnan(out['upper'][-1])
    assert not math.isnan(out['middle'][-1])
    assert not math.isnan(out['lower'][-1])
    assert out['upper'][-1] > out['middle'][-1] > out['lower'][-1]


def test_empty_closes(monkeypatch):
    import tools.get_technical as gt
    _with_fake_closes(monkeypatch, [])
    out = gt.call({'code': 'x', 'indicator': 'MA'})
    assert 'error' in out


def test_unknown_indicator(monkeypatch):
    import tools.get_technical as gt
    _with_fake_closes(monkeypatch, [100.0] * 30)
    with pytest.raises(ValueError, match='unknown'):
        gt.call({'code': 'x', 'indicator': 'FOO'})


def test_talib_is_actually_used(monkeypatch):
    """Sanity: mock talib.SMA and confirm call() routes through it."""
    import tools.get_technical as gt
    import numpy as np

    called = {}
    def _spy_sma(arr, timeperiod=None):
        called['sma'] = True
        return np.full_like(arr, 42.0)

    monkeypatch.setattr(gt.talib, 'SMA', _spy_sma)
    _with_fake_closes(monkeypatch, [1.0] * 30)
    out = gt.call({'code': 'x', 'indicator': 'MA', 'period': 5})
    assert called.get('sma') is True
    assert out['values'][-1] == 42.0
