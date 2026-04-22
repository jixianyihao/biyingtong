def test_spec_shape():
    from tools.get_technical import SPEC
    assert SPEC.name == 'get_technical'


def test_ma_20(vnpy_configured):
    from tools.get_technical import call
    r = call({'code': '600519.SH', 'indicator': 'MA', 'period': 20})
    assert r['indicator'] == 'MA'
    assert len(r['values']) > 0
    last = r['values'][-1]
    assert 1000 < last < 3000


def test_macd(vnpy_configured):
    from tools.get_technical import call
    r = call({'code': '600519.SH', 'indicator': 'MACD'})
    assert len(r['dif']) == len(r['dea']) == len(r['bar'])


def test_rsi_bounded(vnpy_configured):
    from tools.get_technical import call
    import math
    r = call({'code': '600519.SH', 'indicator': 'RSI', 'period': 14})
    for v in r['values']:
        if math.isnan(v):
            continue
        assert 0 <= v <= 100


def test_boll_ordering(vnpy_configured):
    from tools.get_technical import call
    r = call({'code': '600519.SH', 'indicator': 'BOLL'})
    for u, m, l in zip(r['upper'][-10:], r['middle'][-10:], r['lower'][-10:]):
        assert u >= m >= l


def test_unknown_indicator():
    from tools.get_technical import call
    import pytest
    with pytest.raises(ValueError, match='unknown indicator'):
        call({'code': '600519.SH', 'indicator': 'XXX'})
