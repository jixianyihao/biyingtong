from __future__ import annotations

from flask import Flask


def _fresh_flask_app():
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


class _FakeTDX:
    def get_kline(self, code, period='1d', count=80, dividend_type='front'):
        assert code == '688981.SH'
        assert period == '1m'
        return [
            {'date': '2026-01-26 09:31:00', 'open': 100, 'high': 100, 'low': 100, 'close': 100, 'vol': 100000},
            {'date': '2026-01-26 09:35:00', 'open': 98, 'high': 100, 'low': 97.8, 'close': 98, 'vol': 100000},
            {'date': '2026-01-26 10:05:00', 'open': 101, 'high': 101.2, 'low': 97.8, 'close': 101, 'vol': 100000},
            {'date': '2026-01-26 15:00:00', 'open': 101, 'high': 101, 'low': 101, 'close': 101, 'vol': 100000},
        ]

    def get_snapshot(self, code):  # pragma: no cover
        return {}


class _BullishFakeTDX:
    def get_kline(self, code, period='1d', count=80, dividend_type='front'):
        assert code == '688981.SH'
        assert period == '1m'
        return [
            {'date': '2026-01-26 09:31:00', 'open': 100, 'high': 100, 'low': 100, 'close': 100, 'vol': 100000},
            {'date': '2026-02-10 15:00:00', 'open': 102, 'high': 102, 'low': 102, 'close': 102, 'vol': 100000},
            {'date': '2026-03-02 15:00:00', 'open': 104, 'high': 104, 'low': 104, 'close': 104, 'vol': 100000},
            {'date': '2026-04-01 15:00:00', 'open': 107, 'high': 107, 'low': 107, 'close': 107, 'vol': 100000},
        ]

    def get_snapshot(self, code):  # pragma: no cover
        return {}


def test_t0_portfolio_endpoint_returns_account_level_result(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _FakeTDX())
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/portfolio', json={
        'code': '688981.SH',
        'initial_capital': 1_000_000,
        'base_position_pct': 0.75,
        't_shares_pct': 0.20,
        'fee_bps': 0,
        'sell_tax_bps': 0,
        'slippage_bps': 0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['code'] == '688981.SH'
    assert body['base_shares'] == 7500
    assert body['round_trips'] == 1
    assert body['t_pnl'] == 4500
    assert body['alpha_vs_base_hold'] == 4500


def test_t0_portfolio_endpoint_auto_allocation_uses_bull_mode(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _BullishFakeTDX())
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/portfolio', json={
        'code': '688981.SH',
        'initial_capital': 1_000_000,
        'fee_bps': 0,
        'sell_tax_bps': 0,
        'slippage_bps': 0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['allocation']['mode'] == 'bull_high_base'
    assert body['params']['base_position_pct'] == 0.90
    assert body['params']['t_shares_pct'] == 0.15
    assert body['params']['allow_sell_first'] is False
    assert body['params']['allow_buy_first'] is True
    assert body['params']['high_band'] == 0.82
    assert body['params']['low_band'] == 0.25
    assert body['params']['stop_loss_pct'] == 1.0
    assert body['base_shares'] == 9000
