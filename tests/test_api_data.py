"""GET /api/data/coverage — kline date range for a code.

Used by BacktestLab pre-submit validation. Tests use a fake KlineStore so
we don't drag vnpy_sqlite + the real DB file into the suite.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from flask import Flask


def _fresh_flask_app():
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


class _FakeKlineStore:
    """Minimal stand-in: only load_range is exercised by /api/data/coverage."""

    def __init__(self, bars: dict):
        # bars: {(code, period): [bar_objs_ascending]}
        self._bars = bars

    def save_bars(self, bars):  # pragma: no cover — protocol-only
        return 0

    def load_range(self, code, period, start, end):
        rows = self._bars.get((code, period), [])
        return [b for b in rows
                if start <= b.datetime <= end]

    def get_recent(self, code, period, count):  # pragma: no cover
        return []

    def get_closes(self, code, count):  # pragma: no cover
        return []

    def distinct_dates(self, start, end):  # pragma: no cover
        return []


def _bar(dt: datetime):
    """Just enough of vnpy BarData for the endpoint to call .datetime."""
    return SimpleNamespace(datetime=dt)


@pytest.fixture
def client():
    app = _fresh_flask_app()
    with app.test_client() as c:
        yield c


def test_coverage_returns_first_last_for_existing(client):
    import storage
    bars = [
        _bar(datetime(2025, 4, 1)),
        _bar(datetime(2025, 6, 15)),
        _bar(datetime(2026, 4, 1)),
    ]
    storage.set_kline(_FakeKlineStore({('600519.SH', '1d'): bars}))

    resp = client.get('/api/data/coverage?code=600519.SH')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {
        'code': '600519.SH', 'period': '1d',
        'first_date': '2025-04-01',
        'last_date': '2026-04-01',
        'count': 3,
    }


def test_coverage_respects_period_param(client):
    import storage
    daily = [_bar(datetime(2025, 4, 1)), _bar(datetime(2025, 4, 2))]
    weekly = [_bar(datetime(2025, 4, 4))]
    storage.set_kline(_FakeKlineStore({
        ('600519.SH', '1d'): daily,
        ('600519.SH', '1w'): weekly,
    }))

    resp = client.get('/api/data/coverage?code=600519.SH&period=1w')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['period'] == '1w'
    assert body['count'] == 1
    assert body['first_date'] == '2025-04-04'
    assert body['last_date'] == '2025-04-04'


def test_coverage_returns_zero_for_unknown_code(client):
    import storage
    storage.set_kline(_FakeKlineStore({}))

    resp = client.get('/api/data/coverage?code=999999.SH')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {
        'code': '999999.SH', 'period': '1d',
        'first_date': None, 'last_date': None, 'count': 0,
    }


def test_coverage_400_when_code_missing(client):
    resp = client.get('/api/data/coverage')
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'code required'}


def test_coverage_400_when_code_blank(client):
    resp = client.get('/api/data/coverage?code=%20%20')
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'code required'}


# ── /api/data/kline tests ───────────────────────────────────────────────────


def _bar_full(dt: datetime, o, h, l, c, v=0.0):
    """Bar with OHLC fields needed by /api/data/kline."""
    return SimpleNamespace(
        datetime=dt,
        open_price=o, high_price=h, low_price=l, close_price=c,
        volume=v,
    )


def test_kline_returns_ohlc_in_range(client):
    import storage
    bars = [
        _bar_full(datetime(2025, 5, 31), 100, 101, 99, 100.5),
        _bar_full(datetime(2025, 6, 1), 100.5, 102, 100, 101.5),
        _bar_full(datetime(2025, 6, 2), 101.5, 103, 101, 102.5),
        _bar_full(datetime(2025, 6, 30), 105, 106, 104, 105.5),
        _bar_full(datetime(2025, 7, 1), 105.5, 107, 105, 106.5),
    ]
    storage.set_kline(_FakeKlineStore({('600519.SH', '1d'): bars}))

    resp = client.get('/api/data/kline?code=600519.SH&start=2025-06-01&end=2025-06-30')
    assert resp.status_code == 200
    rows = resp.get_json()
    assert len(rows) == 3
    assert rows[0] == {'date': '2025-06-01', 'open': 100.5, 'high': 102.0,
                       'low': 100.0, 'close': 101.5, 'volume': 0.0}
    assert rows[-1]['date'] == '2025-06-30'


def test_kline_400_when_code_missing(client):
    resp = client.get('/api/data/kline?start=2025-06-01&end=2025-06-30')
    assert resp.status_code == 400


def test_kline_400_when_dates_missing(client):
    resp = client.get('/api/data/kline?code=600519.SH')
    assert resp.status_code == 400
    assert 'start and end' in resp.get_json()['error']


def test_kline_400_when_dates_malformed(client):
    resp = client.get('/api/data/kline?code=600519.SH&start=foo&end=bar')
    assert resp.status_code == 400
    assert 'YYYY-MM-DD' in resp.get_json()['error']


def test_kline_returns_empty_when_no_data(client):
    import storage
    storage.set_kline(_FakeKlineStore({}))
    resp = client.get('/api/data/kline?code=999999.SH&start=2025-01-01&end=2025-12-31')
    assert resp.status_code == 200
    assert resp.get_json() == []
