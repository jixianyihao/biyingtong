# tests/test_get_capital_flow.py
from tools import get_capital_flow


def test_capital_flow_stock(monkeypatch):
    import tdx_service
    raw = {'600519.SH': {'GP3': [{'Date': '20260422', 'Value': ['141405.89', '11113.00']}]}}
    monkeypatch.setattr(
        tdx_service.tdx, 'get_gpjy_value',
        lambda codes, fields, start_time, end_time: raw
    )
    out = get_capital_flow.call({
        'code': '600519.SH',
        'start_date': '20260422',
        'end_date': '20260422',
    })
    assert out['code'] == '600519.SH'
    assert 'rows' in out
    assert len(out['rows']) >= 1


def test_capital_flow_sector(monkeypatch):
    import tdx_service
    raw = {'880660.SH': {'BK5': [{'Date': '20260422', 'Value': ['1000']}]}}
    monkeypatch.setattr(
        tdx_service.tdx, 'get_bkjy_value',
        lambda codes, fields, start_time, end_time: raw
    )
    out = get_capital_flow.call({
        'sector_code': '880660.SH',
        'start_date': '20260422',
        'end_date': '20260422',
    })
    assert out['sector_code'] == '880660.SH'
    assert 'rows' in out


def test_capital_flow_requires_one_target():
    out = get_capital_flow.call({'start_date': '20260422', 'end_date': '20260422'})
    assert 'error' in out


def test_spec_has_expected_shape():
    assert get_capital_flow.SPEC.name == 'get_capital_flow'
    props = get_capital_flow.SPEC.input_schema['properties']
    assert 'code' in props and 'sector_code' in props
