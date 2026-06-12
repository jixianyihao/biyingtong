from __future__ import annotations

import struct
from pathlib import Path

from flask import Flask

from api.t0 import _preview_drawdown_allowed, _preview_sort_key


def _fresh_flask_app():
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


def _date_code(year: int, month: int, day: int) -> int:
    return (year - 2004) * 2048 + month * 100 + day


def _write_lc1(path: Path, code: str, closes: list[float]) -> Path:
    market = code[-2:].lower()
    raw = code[:6]
    target = path / market / 'minline'
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    day = 1
    for i, close in enumerate(closes):
        if i and i % 4 == 0:
            day += 1
        rows.append(struct.pack(
            '<HHfffffii',
            _date_code(2026, 5, day),
            9 * 60 + 31 + (i % 4),
            close,
            close * 1.02,
            close * 0.98,
            close,
            close * 100_000,
            100_000,
            0,
        ))
    file_path = target / f'{market}{raw}.lc1'
    file_path.write_bytes(b''.join(rows))
    return target


def test_t0_candidates_endpoint_scans_local_lc1_files(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [10 + i * 0.05 for i in range(80)])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 10,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['count'] == 1
    assert body['rows'][0]['code'] == '688981.SH'
    assert body['rows'][0]['bar_count'] == 80


def test_t0_candidates_endpoint_can_attach_portfolio_preview(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 2,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'preview_pool': 5,
        'min_preview_trips': 0,
    })

    assert resp.status_code == 200
    row = resp.get_json()['rows'][0]
    assert row['code'] == '688981.SH'
    assert row['preview_total_return_pct'] is not None
    assert row['preview_alpha_vs_all_in'] is not None
    assert row['preview_round_trips'] >= 0


def test_t0_candidates_endpoint_can_attach_walk_forward_preview(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
        104.0, 102.0, 105.0, 105.0,
        106.0, 104.0, 107.0, 107.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 4,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'preview_pool': 5,
        'preview_validation_ratio': 0.5,
        'min_preview_trips': 0,
    })

    assert resp.status_code == 200
    row = resp.get_json()['rows'][0]
    assert row['preview_train_total_return_pct'] is not None
    assert row['preview_train_alpha_vs_all_in'] is not None
    assert row['preview_validation_total_return_pct'] is not None
    assert row['preview_validation_alpha_vs_all_in'] is not None


def test_t0_candidates_endpoint_can_filter_negative_preview_returns(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 97.0, 96.0,
        95.0, 94.0, 93.0, 92.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 2,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'preview_pool': 5,
        'min_preview_trips': 0,
        'min_preview_return_pct': 0,
    })

    assert resp.status_code == 200
    assert resp.get_json()['rows'] == []


def test_t0_candidates_endpoint_can_filter_negative_preview_alpha(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 2,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'preview_pool': 5,
        'min_preview_trips': 0,
        'min_preview_alpha_vs_all_in': 1_000_000,
    })

    assert resp.status_code == 200
    assert resp.get_json()['rows'] == []


def test_previewed_candidates_sort_by_return_after_alpha_filter():
    rows = [
        {
            'code': 'low-return-high-alpha',
            'preview_total_return_pct': 1.1,
            'preview_alpha_vs_all_in': 31_000.0,
            'preview_round_trips': 70,
        },
        {
            'code': 'high-return-positive-alpha',
            'preview_total_return_pct': 13.1,
            'preview_alpha_vs_all_in': 4_000.0,
            'preview_round_trips': 49,
        },
    ]

    rows.sort(key=_preview_sort_key, reverse=True)

    assert [r['code'] for r in rows] == [
        'high-return-positive-alpha',
        'low-return-high-alpha',
    ]


def test_previewed_candidates_sort_by_validation_return_when_available():
    rows = [
        {
            'code': 'high-full-return-bad-validation',
            'preview_total_return_pct': 20.0,
            'preview_alpha_vs_all_in': 50_000.0,
            'preview_validation_total_return_pct': -1.0,
            'preview_validation_alpha_vs_all_in': -3_000.0,
            'preview_round_trips': 80,
        },
        {
            'code': 'lower-full-return-good-validation',
            'preview_total_return_pct': 8.0,
            'preview_alpha_vs_all_in': 12_000.0,
            'preview_validation_total_return_pct': 2.0,
            'preview_validation_alpha_vs_all_in': 2_000.0,
            'preview_round_trips': 30,
        },
    ]

    rows.sort(key=_preview_sort_key, reverse=True)

    assert rows[0]['code'] == 'lower-full-return-good-validation'


def test_preview_drawdown_filter_uses_absolute_drawdown_limit():
    assert _preview_drawdown_allowed(-7.5, 8.0)
    assert _preview_drawdown_allowed(0.0, 8.0)
    assert not _preview_drawdown_allowed(-8.1, 8.0)
    assert _preview_drawdown_allowed(-99.0, float('inf'))
