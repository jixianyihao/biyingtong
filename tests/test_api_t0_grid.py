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
            {'date': '2026-05-20 09:31:00', 'open': 100, 'high': 100, 'low': 100, 'close': 100, 'vol': 100000},
            {'date': '2026-05-20 09:40:00', 'open': 103, 'high': 103.2, 'low': 100, 'close': 103, 'vol': 100000},
            {'date': '2026-05-20 10:10:00', 'open': 101, 'high': 103.2, 'low': 100.8, 'close': 101, 'vol': 100000},
        ]

    def get_snapshot(self, code):  # pragma: no cover - grid does not need it
        return {}


def test_t0_grid_endpoint_returns_coverage_and_ranked_rows(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _FakeTDX())
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/grid', json={
        'code': '688981.SH',
        'top': 3,
        'min_last_date': '2026-05-01',
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['code'] == '688981.SH'
    assert body['coverage']['first'] == '2026-05-20'
    assert body['coverage']['last'] == '2026-05-20'
    assert body['coverage']['is_stale'] is False
    assert len(body['rows']) <= 3
    assert body['rows'][0]['params']['mode'] in {'sell_first_only', 'both'}


def test_t0_grid_marks_stale_data(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _FakeTDX())
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/grid', json={
        'code': '688981.SH',
        'top': 3,
        'min_last_date': '2026-05-22',
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['coverage']['is_stale'] is True
    assert body['coverage']['stale_reason'] == 'latest 1m bar 2026-05-20 < required 2026-05-22'
