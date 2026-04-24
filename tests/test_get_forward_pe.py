# tests/test_get_forward_pe.py
"""Tests for tdx_service.get_gp_one_data wrapper and tools.get_forward_pe."""
from __future__ import annotations


# ---- Task A1: TDXService.get_gp_one_data wrapper ----

def test_tdx_service_get_gp_one_data_delegates(monkeypatch):
    """TDXService.get_gp_one_data should delegate to tq.get_gp_one_data with the
    given codes + fields."""
    import tdx_service

    captured = {}

    def fake_get_gp_one_data(stock_list, field_list):
        captured['stock_list'] = stock_list
        captured['field_list'] = field_list
        return {'688318.SH': {'GO23': '18.5', 'GO24': '15.2', 'GO25': '13.1'}}

    # Avoid real SDK init
    monkeypatch.setattr(tdx_service.tdx, 'ensure_connected', lambda: True)
    monkeypatch.setattr(tdx_service.tq, 'get_gp_one_data', fake_get_gp_one_data)

    out = tdx_service.tdx.get_gp_one_data(['688318.SH'], ['GO23', 'GO24', 'GO25'])
    assert captured['stock_list'] == ['688318.SH']
    assert captured['field_list'] == ['GO23', 'GO24', 'GO25']
    assert out == {'688318.SH': {'GO23': '18.5', 'GO24': '15.2', 'GO25': '13.1'}}


def test_tdx_service_get_gp_one_data_returns_empty_on_error(monkeypatch):
    """Errors from the SDK should be swallowed and produce an empty dict,
    matching the get_gpjy_value / get_bkjy_value pattern."""
    import tdx_service

    def boom(stock_list, field_list):
        raise RuntimeError('sdk exploded')

    monkeypatch.setattr(tdx_service.tdx, 'ensure_connected', lambda: True)
    monkeypatch.setattr(tdx_service.tq, 'get_gp_one_data', boom)

    out = tdx_service.tdx.get_gp_one_data(['600519.SH'], ['GO23'])
    assert out == {}


# ---- Task A2: tools.get_forward_pe ----

def test_forward_pe_returns_three_horizons(monkeypatch):
    from tools import get_forward_pe
    import tdx_service

    monkeypatch.setattr(
        tdx_service.tdx, 'get_gp_one_data',
        lambda codes, fields: {
            '688318.SH': {'GO23': '18.5', 'GO24': '15.2', 'GO25': '13.1'},
        },
    )
    out = get_forward_pe.call({'code': '688318.SH'})
    assert out['code'] == '688318.SH'
    assert out['pe_t'] == 18.5
    assert out['pe_t1'] == 15.2
    assert out['pe_t2'] == 13.1
    assert isinstance(out['pe_t'], float)
    assert isinstance(out['pe_t1'], float)
    assert isinstance(out['pe_t2'], float)


def test_forward_pe_missing_code_errors():
    from tools import get_forward_pe
    out = get_forward_pe.call({})
    assert 'error' in out


def test_forward_pe_handles_missing_fields(monkeypatch):
    from tools import get_forward_pe
    import tdx_service

    # tdx returns partial — only GO23 available
    monkeypatch.setattr(
        tdx_service.tdx, 'get_gp_one_data',
        lambda codes, fields: {'600519.SH': {'GO23': '22.0'}},
    )
    out = get_forward_pe.call({'code': '600519.SH'})
    assert out['code'] == '600519.SH'
    assert out['pe_t'] == 22.0
    assert out['pe_t1'] is None
    assert out['pe_t2'] is None


def test_forward_pe_handles_non_numeric_values(monkeypatch):
    """Non-numeric or empty string values should become None, not raise."""
    from tools import get_forward_pe
    import tdx_service

    monkeypatch.setattr(
        tdx_service.tdx, 'get_gp_one_data',
        lambda codes, fields: {'600519.SH': {'GO23': '', 'GO24': 'n/a', 'GO25': '12.0'}},
    )
    out = get_forward_pe.call({'code': '600519.SH'})
    assert out['pe_t'] is None
    assert out['pe_t1'] is None
    assert out['pe_t2'] == 12.0


def test_forward_pe_handles_empty_tdx_response(monkeypatch):
    from tools import get_forward_pe
    import tdx_service

    monkeypatch.setattr(
        tdx_service.tdx, 'get_gp_one_data',
        lambda codes, fields: {},
    )
    out = get_forward_pe.call({'code': '600519.SH'})
    assert out['code'] == '600519.SH'
    assert out['pe_t'] is None
    assert out['pe_t1'] is None
    assert out['pe_t2'] is None


def test_spec_has_expected_shape():
    from tools import get_forward_pe
    assert get_forward_pe.SPEC.name == 'get_forward_pe'
    props = get_forward_pe.SPEC.input_schema['properties']
    assert 'code' in props
    assert get_forward_pe.SPEC.input_schema.get('type') == 'object'
    assert 'code' in get_forward_pe.SPEC.input_schema.get('required', [])
