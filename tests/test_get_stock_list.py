# tests/test_get_stock_list.py
from unittest.mock import patch
from tools import get_stock_list


def test_get_stock_list_returns_codes(monkeypatch):
    import tdx_service
    monkeypatch.setattr(
        tdx_service.tdx, 'get_stock_list_in_sector',
        lambda name: ['600519.SH', '000858.SZ', '']
    )
    out = get_stock_list.call({'sector': '白酒'})
    assert out['sector'] == '白酒'
    assert out['codes'] == ['600519.SH', '000858.SZ']
    assert 'count' in out
    assert out['count'] == 2


def test_get_stock_list_filters_invalid(monkeypatch):
    import tdx_service
    monkeypatch.setattr(
        tdx_service.tdx, 'get_stock_list_in_sector',
        lambda name: ['600519.SH', None, '', 'ABC', '000858.SZ']
    )
    out = get_stock_list.call({'sector': '白酒'})
    assert out['codes'] == ['600519.SH', '000858.SZ']


def test_get_stock_list_missing_sector_errors():
    out = get_stock_list.call({})
    assert 'error' in out


def test_get_stock_list_list_sectors(monkeypatch):
    import tdx_service
    monkeypatch.setattr(
        tdx_service.tdx, 'get_sector_list',
        lambda: ['白酒', '新能源', '半导体']
    )
    out = get_stock_list.call({'list_sectors': True})
    assert out['sectors'] == ['白酒', '新能源', '半导体']


def test_spec_has_expected_shape():
    assert get_stock_list.SPEC.name == 'get_stock_list'
    assert 'sector' in get_stock_list.SPEC.input_schema.get('properties', {})
