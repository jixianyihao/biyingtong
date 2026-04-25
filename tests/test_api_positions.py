"""GET /api/positions — TDX holdings endpoint."""
from __future__ import annotations

import importlib

import pytest
from flask import Flask


def _fresh_flask_app():
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client():
    app = _fresh_flask_app()
    with app.test_client() as c:
        yield c


def test_positions_endpoint_returns_empty_in_dry_run(client, monkeypatch):
    monkeypatch.delenv('BIYINGTONG_EXECUTION_MODE', raising=False)
    import execution
    importlib.reload(execution)

    resp = client.get('/api/positions')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['mode'] == 'dry_run'
    assert body['positions'] == []
    assert 'hint' in body and 'dry_run' in body['hint']


def test_positions_endpoint_returns_normalized_in_live(client, monkeypatch):
    monkeypatch.setenv('BIYINGTONG_EXECUTION_MODE', 'live')
    import execution
    importlib.reload(execution)

    import tdx_service
    monkeypatch.setattr(tdx_service.tdx, 'get_positions', lambda: [
        {
            'stock_code': '600519.SH', 'stock_name': '贵州茅台',
            'current_amount': 100, 'avg_buy_price': 1700.0,
            'last_price': 1750.0, 'income_balance_rate': 2.94,
        },
        {
            'stock_code': '000001.SZ', 'stock_name': '平安银行',
            'current_amount': 1000, 'avg_buy_price': 12.0,
            'last_price': 11.5, 'income_balance_rate': -4.17,
        },
    ])

    resp = client.get('/api/positions')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['mode'] == 'live'
    assert len(body['positions']) == 2
    p0 = body['positions'][0]
    assert p0 == {
        'code': '600519.SH', 'name': '贵州茅台', 'shares': 100,
        'avg_price': 1700.0, 'last_price': 1750.0, 'pnl_pct': 2.94,
    }
    p1 = body['positions'][1]
    assert p1['code'] == '000001.SZ'
    assert p1['shares'] == 1000
    assert p1['pnl_pct'] == -4.17


def test_positions_endpoint_normalizes_tqcenter_field_aliases(client, monkeypatch):
    """Some tqcenter call paths use 'code'/'shares'/'avg_price' instead of
    the long-form aliases. Endpoint should accept either."""
    monkeypatch.setenv('BIYINGTONG_EXECUTION_MODE', 'live')
    import execution
    importlib.reload(execution)

    import tdx_service
    monkeypatch.setattr(tdx_service.tdx, 'get_positions', lambda: [
        {
            'code': '600036.SH', 'name': '招商银行',
            'shares': 200, 'avg_price': 35.0,
            'last_price': 36.5, 'pnl_pct': 4.29,
        },
        # mixed: short-form code, long-form everything else
        {
            'code': '601318.SH', 'stock_name': '中国平安',
            'current_amount': 500, 'avg_buy_price': 50.0,
            'last_price': 52.0, 'income_balance_rate': 4.0,
        },
        # garbage entry skipped
        'not-a-dict',
        # empty / malformed dict yields empty-string code but still emitted
    ])

    resp = client.get('/api/positions')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['mode'] == 'live'
    # Only dict entries, two of them
    assert len(body['positions']) == 2
    assert body['positions'][0]['code'] == '600036.SH'
    assert body['positions'][0]['name'] == '招商银行'
    assert body['positions'][0]['shares'] == 200
    assert body['positions'][0]['avg_price'] == 35.0
    assert body['positions'][1]['code'] == '601318.SH'
    assert body['positions'][1]['name'] == '中国平安'
    assert body['positions'][1]['shares'] == 500
    assert body['positions'][1]['avg_price'] == 50.0
