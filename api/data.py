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


@api_bp.route('/data/kline')
def data_kline():
    """Date-range kline from the LOCAL storage.kline() SQLite cache.

    Unlike /api/market/kline (TDX live, count-based), this reads only what's
    been pre-ingested into vnpy_sqlite. Used by backtest UI to render historic
    OHLC for the exact backtest window without depending on live TDX.

    Query: code=600519.SH&period=1d&start=2025-06-01&end=2026-04-01
    Response: [{date, open, high, low, close, volume}, ...]
    """
    code = request.args.get('code', '').strip()
    period = request.args.get('period', '1d').strip() or '1d'
    start_str = request.args.get('start', '').strip()
    end_str = request.args.get('end', '').strip()
    if not code:
        return jsonify({'error': 'code required'}), 400
    if not start_str or not end_str:
        return jsonify({'error': 'start and end required (YYYY-MM-DD)'}), 400
    try:
        start = datetime.strptime(start_str, '%Y-%m-%d')
        end = datetime.strptime(end_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'start/end must be YYYY-MM-DD'}), 400

    import storage
    bars = storage.kline().load_range(code, period, start, end)
    return jsonify([
        {
            'date': b.datetime.date().isoformat(),
            'open': float(b.open_price),
            'high': float(b.high_price),
            'low': float(b.low_price),
            'close': float(b.close_price),
            'volume': float(b.volume),
        }
        for b in bars
    ])
