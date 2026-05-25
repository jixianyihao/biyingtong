from __future__ import annotations

import struct
from pathlib import Path

from flask import Flask


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
