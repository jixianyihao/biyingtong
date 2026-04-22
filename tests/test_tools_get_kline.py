def test_spec_shape():
    from tools.get_kline import SPEC
    assert SPEC.name == 'get_kline'
    assert set(SPEC.input_schema['required']) == {'code', 'period', 'count'}


def test_returns_ohlcv_list(vnpy_configured):
    from tools.get_kline import call
    r = call({'code': '600519.SH', 'period': '1d', 'count': 20})
    assert 'bars' in r
    assert 10 <= len(r['bars']) <= 20
    for b in r['bars']:
        assert b['high'] >= b['low'] > 0
        assert 'volume' in b


def test_handles_bare_code(vnpy_configured):
    from tools.get_kline import call
    r = call({'code': '600519', 'period': '1d', 'count': 5})
    assert len(r['bars']) > 0


def test_empty_for_unknown_stock(vnpy_configured):
    from tools.get_kline import call
    r = call({'code': '999999.SH', 'period': '1d', 'count': 10})
    assert r['bars'] == []


def test_period_validation():
    from tools.get_kline import call
    import pytest
    with pytest.raises(ValueError):
        call({'code': '600519.SH', 'period': 'bad', 'count': 10})


def test_uses_storage_layer():
    """Structural: get_kline.py must not import vnpy_sqlite directly."""
    from pathlib import Path
    source = Path('tools/get_kline.py').read_text(encoding='utf-8')
    assert 'from vnpy_sqlite' not in source
    assert 'from storage' in source or 'import storage' in source
