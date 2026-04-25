"""GET /api/positions — current TDX holdings.

Returns the live tqcenter position list. In dry_run mode returns an empty
list (no positions because no real orders have been placed). In live mode
returns whatever tdx_service.get_positions reports.

The frontend uses this to populate PositionsPanel. Failure modes:
  - TDX disconnected -> empty list with status_hint
  - Adapter is dry_run -> empty list with status_hint='dry_run'
"""
from __future__ import annotations

from flask import jsonify

from . import api_bp


@api_bp.route('/positions')
def get_positions():
    from execution import get_adapter
    mode = get_adapter().mode
    if mode != 'live':
        return jsonify({'mode': mode, 'positions': [],
                        'hint': 'dry_run - no real positions'})
    from tdx_service import tdx
    raw = tdx.get_positions() or []
    # Normalize tqcenter shape into a flat list of dicts the UI can render
    out = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        out.append({
            'code': p.get('stock_code') or p.get('code') or '',
            'name': p.get('stock_name') or p.get('name') or '',
            'shares': int(p.get('current_amount') or p.get('shares') or 0),
            'avg_price': float(p.get('avg_buy_price') or p.get('avg_price') or 0.0),
            'last_price': float(p.get('last_price') or 0.0),
            'pnl_pct': float(p.get('income_balance_rate') or p.get('pnl_pct') or 0.0),
        })
    return jsonify({'mode': mode, 'positions': out})
