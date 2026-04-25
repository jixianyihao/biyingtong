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
