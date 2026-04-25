"""POST /api/screener — multi-factor stock screening backed by financial cache.

Reads `financial_data` directly from `data/financial_cache.db` to keep the
endpoint local — extending the FinancialStore Protocol with a "list latest"
method would be a multi-file change beyond this PR's ownership boundary.

Body shape:
    {filters: [{factor, op, value, enabled}, ...]}

Each filter:
    factor:  'pe' | 'pb' | 'roe' | 'revenue_growth' |
             'net_profit_growth' | 'gross_margin'
    op:      '<' | '>' | '='
    value:   numeric threshold
    enabled: bool — disabled filters are skipped (caller toggles in UI)

Response:
    {
      total_universe: int,
      matched: int,
      stocks: [{code, pe, pb, roe, gross_margin, revenue_growth,
                net_profit_growth, as_of_date}, ...]
    }

Stocks list is capped at 200 rows to keep the UI snappy.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import jsonify, request

from . import api_bp


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DB_PATH = _REPO_ROOT / 'data' / 'financial_cache.db'

_VALID_FACTORS = {
    'pe', 'pb', 'roe',
    'revenue_growth', 'net_profit_growth', 'gross_margin',
}
_VALID_OPS = {'<', '>', '='}


def _apply_op(value, op, threshold):
    """Compare a (possibly None) DB value to a threshold using op.

    None / non-numeric values fail the predicate (excluded from results)
    rather than throwing; this is the desired UX — a stock with missing
    PE is not "PE < 25".
    """
    if value is None:
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    try:
        t = float(threshold)
    except (TypeError, ValueError):
        return False
    if op == '<':
        return v < t
    if op == '>':
        return v > t
    if op == '=':
        return abs(v - t) < 1e-6
    return False


@api_bp.route('/screener', methods=['POST'])
def run_screener():
    body = request.get_json(silent=True) or {}
    raw_filters = body.get('filters') or []

    # Sanitize: only well-formed enabled filters with whitelisted factor/op.
    enabled_filters = []
    for f in raw_filters:
        if not isinstance(f, dict):
            continue
        if not f.get('enabled'):
            continue
        factor = f.get('factor')
        op = f.get('op')
        value = f.get('value')
        if factor not in _VALID_FACTORS:
            continue
        if op not in _VALID_OPS:
            continue
        if value is None:
            continue
        enabled_filters.append({'factor': factor, 'op': op, 'value': value})

    if not _DB_PATH.exists():
        return jsonify({
            'total_universe': 0,
            'matched': 0,
            'stocks': [],
            'note': '本地财务数据未加载。请先运行 scripts/setup/load_financial.py',
        })

    # Latest snapshot per stock_code.
    con = sqlite3.connect(_DB_PATH)
    try:
        rows = con.execute('''
            SELECT f.stock_code, f.date, f.pe, f.pb, f.roe,
                   f.gross_margin, f.revenue_growth, f.net_profit_growth
            FROM financial_data f
            INNER JOIN (
              SELECT stock_code, MAX(date) AS d
              FROM financial_data
              GROUP BY stock_code
            ) m ON m.stock_code = f.stock_code AND m.d = f.date
            ORDER BY f.stock_code
        ''').fetchall()
    finally:
        con.close()

    universe = []
    for r in rows:
        universe.append({
            'code': r[0],
            'as_of_date': r[1],
            'pe': r[2],
            'pb': r[3],
            'roe': r[4],
            'gross_margin': r[5],
            'revenue_growth': r[6],
            'net_profit_growth': r[7],
        })

    matched = []
    for rec in universe:
        ok = True
        for f in enabled_filters:
            if not _apply_op(rec[f['factor']], f['op'], f['value']):
                ok = False
                break
        if ok:
            matched.append(rec)

    return jsonify({
        'total_universe': len(universe),
        'matched': len(matched),
        'stocks': matched[:200],
    })
