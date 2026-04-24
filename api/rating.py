"""Strategy rating endpoint."""
from __future__ import annotations

from dataclasses import asdict

from flask import jsonify

from . import api_bp


@api_bp.route('/backtests/<result_id>/rating')
def get_backtest_rating(result_id):
    """Compute + return 5-sub-score strategy rating for a backtest result."""
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    from rating.strategy_rating import compute_strategy_rating
    rating = compute_strategy_rating(r)
    return jsonify({
        **asdict(rating),
        'notes': list(rating.notes),
    })
