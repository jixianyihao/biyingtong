"""POST /api/screener — multi-factor screening backed by financial_cache.db.

Tests monkeypatch ``api.screener._DB_PATH`` at a tmp_path-backed sqlite DB
seeded inline with hand-crafted rows. No production DB is touched.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from flask import Flask


def _fresh_flask_app():
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


def _seed_db(db_path: Path, rows: list[tuple]) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.execute('''
            CREATE TABLE IF NOT EXISTS financial_data (
                stock_code TEXT NOT NULL,
                date DATE NOT NULL,
                pe REAL, pb REAL, roe REAL,
                gross_margin REAL,
                revenue_growth REAL,
                net_profit_growth REAL,
                PRIMARY KEY (stock_code, date)
            )
        ''')
        con.executemany(
            'INSERT INTO financial_data VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            rows,
        )
        con.commit()
    finally:
        con.close()


# (code, date, pe, pb, roe, gross_margin, revenue_growth, net_profit_growth)
_SEED_ROWS = [
    ('600001', '2026-04-26', 10.0, 1.5, 20.0, 35.0, 12.0, 18.0),
    ('600002', '2026-04-26', 30.0, 4.0, 8.0,  20.0, -5.0, -3.0),
    ('600003', '2026-04-26', 22.0, 2.5, 18.0, 42.0, 10.0, 15.0),
    ('600004', '2026-04-26', 15.0, 2.0, 25.0, 50.0, 30.0, 40.0),
    ('600005', '2026-04-26', 50.0, 6.0, 5.0,  10.0, -10.0, -20.0),
    # Stale row for 600001 — must be excluded by latest-per-code subquery.
    ('600001', '2025-01-01', 99.0, 99.0, 99.0, 99.0, 99.0, 99.0),
]


@pytest.fixture
def client_with_db(tmp_path, monkeypatch):
    """Yields a Flask test client wired to a tmp DB seeded with _SEED_ROWS."""
    db_path = tmp_path / 'financial_cache.db'
    _seed_db(db_path, _SEED_ROWS)

    import api.screener as screener_mod
    monkeypatch.setattr(screener_mod, '_DB_PATH', db_path)

    app = _fresh_flask_app()
    with app.test_client() as c:
        yield c


def test_screener_returns_universe_when_no_filters(client_with_db):
    """Empty filters → all stocks returned (universe = matched = 5)."""
    resp = client_with_db.post('/api/screener', json={'filters': []})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['total_universe'] == 5
    assert body['matched'] == 5
    assert len(body['stocks']) == 5
    codes = sorted(s['code'] for s in body['stocks'])
    assert codes == ['600001', '600002', '600003', '600004', '600005']
    # Latest-per-code subquery wins: 600001 is the 2026-04-26 row, not stale.
    row_600001 = next(s for s in body['stocks'] if s['code'] == '600001')
    assert row_600001['as_of_date'] == '2026-04-26'
    assert row_600001['pe'] == 10.0


def test_screener_pe_lt_filter(client_with_db):
    """pe < 20 → 600001 (10), 600003 (22 fails), 600004 (15)."""
    resp = client_with_db.post('/api/screener', json={
        'filters': [{'factor': 'pe', 'op': '<', 'value': 20, 'enabled': True}],
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['total_universe'] == 5
    matched_codes = sorted(s['code'] for s in body['stocks'])
    assert matched_codes == ['600001', '600004']
    assert body['matched'] == 2


def test_screener_combined_filters_AND(client_with_db):
    """All filters AND-combined: pe<25, pb<3, roe>15."""
    resp = client_with_db.post('/api/screener', json={
        'filters': [
            {'factor': 'pe',  'op': '<', 'value': 25, 'enabled': True},
            {'factor': 'pb',  'op': '<', 'value': 3,  'enabled': True},
            {'factor': 'roe', 'op': '>', 'value': 15, 'enabled': True},
        ],
    })
    assert resp.status_code == 200
    body = resp.get_json()
    # 600001 (pe=10, pb=1.5, roe=20) ✓
    # 600003 (pe=22, pb=2.5, roe=18) ✓
    # 600004 (pe=15, pb=2.0, roe=25) ✓
    # 600002 fails roe; 600005 fails everything
    matched_codes = sorted(s['code'] for s in body['stocks'])
    assert matched_codes == ['600001', '600003', '600004']
    assert body['matched'] == 3


def test_screener_disabled_filter_is_skipped(client_with_db):
    """enabled:false → filter is ignored, full universe returned."""
    resp = client_with_db.post('/api/screener', json={
        'filters': [
            {'factor': 'pe', 'op': '<', 'value': 1, 'enabled': False},
        ],
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['matched'] == 5  # No effective filters → full universe


def test_screener_growth_filter(client_with_db):
    """revenue_growth > 5 → 600001 (12), 600003 (10), 600004 (30)."""
    resp = client_with_db.post('/api/screener', json={
        'filters': [{'factor': 'revenue_growth', 'op': '>', 'value': 5, 'enabled': True}],
    })
    assert resp.status_code == 200
    body = resp.get_json()
    matched_codes = sorted(s['code'] for s in body['stocks'])
    assert matched_codes == ['600001', '600003', '600004']


def test_screener_no_data_file_returns_empty_with_note(tmp_path, monkeypatch):
    """DB file missing → returns empty result + helpful note (no 500)."""
    missing = tmp_path / 'does_not_exist.db'
    import api.screener as screener_mod
    monkeypatch.setattr(screener_mod, '_DB_PATH', missing)

    app = _fresh_flask_app()
    with app.test_client() as c:
        resp = c.post('/api/screener', json={'filters': []})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['total_universe'] == 0
    assert body['matched'] == 0
    assert body['stocks'] == []
    assert 'note' in body
    assert '财务数据' in body['note']


def test_screener_invalid_factor_is_ignored(client_with_db):
    """Unknown factor name is silently skipped, not 500."""
    resp = client_with_db.post('/api/screener', json={
        'filters': [
            {'factor': 'nonexistent', 'op': '<', 'value': 1, 'enabled': True},
            {'factor': 'pe', 'op': '<', 'value': 20, 'enabled': True},
        ],
    })
    assert resp.status_code == 200
    body = resp.get_json()
    # Only the 'pe < 20' filter applies → 600001 + 600004
    matched_codes = sorted(s['code'] for s in body['stocks'])
    assert matched_codes == ['600001', '600004']
