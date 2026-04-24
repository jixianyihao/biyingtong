"""GET /api/strategies — list built-in rule strategies."""
from __future__ import annotations

from dataclasses import asdict

from flask import jsonify

from . import api_bp


@api_bp.route('/strategies')
def list_strategies():
    from backtest.strategies import list_all
    return jsonify([asdict(d) for d in list_all()])
