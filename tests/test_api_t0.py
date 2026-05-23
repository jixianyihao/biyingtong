from __future__ import annotations

from flask import Flask


def _fresh_flask_app():
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


class _FakeTDX:
    def get_snapshot(self, code):
        assert code == '688981.SH'
        return {'code': code, 'name': '中芯国际', 'lastClose': 126.0}

    def get_kline(self, code, period='1d', count=80, dividend_type='front'):
        assert code == '688981.SH'
        assert period == '1m'
        return [
            {'date': '2026-05-22 09:31', 'open': 126.2, 'high': 126.3, 'low': 126.0, 'close': 126.2, 'vol': 100000},
            {'date': '2026-05-22 09:32', 'open': 126.2, 'high': 127.5, 'low': 126.2, 'close': 127.4, 'vol': 120000},
            {'date': '2026-05-22 09:33', 'open': 127.4, 'high': 128.9, 'low': 127.4, 'close': 128.7, 'vol': 140000},
            {'date': '2026-05-22 09:34', 'open': 128.7, 'high': 129.5, 'low': 128.6, 'close': 129.2, 'vol': 130000},
        ]


class _FakeStaleTDX:
    def get_snapshot(self, code):
        return {
            'code': code, 'name': '中芯国际',
            'price': 131.33, 'lastClose': 127.22,
            'open': 129.33, 'high': 132.18, 'low': 126.50,
            'vol': 1_199_477, 'amount': 1_551_684.38,
        }

    def get_kline(self, code, period='1d', count=80, dividend_type='front'):
        return [
            {'date': '2026-02-03 14:59', 'open': 116.03, 'high': 116.04, 'low': 116.01, 'close': 116.02, 'vol': 243100},
            {'date': '2026-02-03 15:00', 'open': 116.03, 'high': 116.03, 'low': 116.03, 'close': 116.03, 'vol': 407600},
        ]


def test_t0_signal_scores_a_share_one_minute_bars(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _FakeTDX())
    app = _fresh_flask_app()

    resp = app.test_client().get('/api/t0/signal?code=688981.SH&as_of=2026-05-23')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['code'] == '688981.SH'
    assert body['name'] == '中芯国际'
    assert body['data_mode'] == 'minute_1m'
    assert body['action'] == 'sell_t_candidate'
    assert body['metrics']['bar_count'] == 4
    assert body['minute_stale'] is False


def test_t0_signal_falls_back_to_snapshot_when_minute_bars_are_stale(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _FakeStaleTDX())
    app = _fresh_flask_app()

    resp = app.test_client().get('/api/t0/signal?code=688981.SH&as_of=2026-05-23')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['data_mode'] == 'snapshot_fallback'
    assert body['minute_stale'] is True
    assert body['minute_latest_date'] == '2026-02-03'
    assert body['action'] == 'sell_t_candidate'


def test_t0_signal_requires_code():
    app = _fresh_flask_app()

    resp = app.test_client().get('/api/t0/signal')

    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'code required'}
