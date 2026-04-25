"""Data coverage endpoint — what date range is available for a code."""
from __future__ import annotations

from datetime import datetime

from flask import jsonify, request

from . import api_bp


@api_bp.route('/data/coverage')
def data_coverage():
    """Returns {code, period, first_date, last_date, count} for the given code.

    Used by BacktestLab pre-submit validation to warn when the requested
    window falls outside the locally-cached k-line range.

    Query: code=600519.SH&period=1d (period defaults to '1d')

    Response 200 (data present):
        {'code': '600519.SH', 'period': '1d',
         'first_date': '2025-04-01', 'last_date': '2026-04-01', 'count': 243}

    Response 200 (no data — empty cache for this code):
        {'code': '600519.SH', 'period': '1d',
         'first_date': None, 'last_date': None, 'count': 0}

    Response 400: {'error': 'code required'}
    """
    code = request.args.get('code', '').strip()
    period = request.args.get('period', '1d').strip() or '1d'
    if not code:
        return jsonify({'error': 'code required'}), 400

    import storage
    bars = storage.kline().load_range(
        code, period,
        datetime(2000, 1, 1),
        datetime(2100, 12, 31),
    )
    if not bars:
        return jsonify({
            'code': code, 'period': period,
            'first_date': None, 'last_date': None, 'count': 0,
        })
    return jsonify({
        'code': code, 'period': period,
        'first_date': bars[0].datetime.date().isoformat(),
        'last_date': bars[-1].datetime.date().isoformat(),
        'count': len(bars),
    })
