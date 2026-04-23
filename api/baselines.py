"""GET /api/baselines?session_id=... — list baselines under a session."""
from __future__ import annotations

from dataclasses import asdict

from flask import jsonify, request

from . import api_bp


@api_bp.route('/baselines')
def list_baselines():
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({'error': 'session_id query param required'}), 400
    import storage
    rows = storage.baselines().list_for_session(session_id)
    return jsonify([
        {
            'id': b.id,
            'session_id': b.session_id,
            'name': b.name,
            'start_date': b.start_date,
            'end_date': b.end_date,
            'initial_capital': b.initial_capital,
            'final_equity': b.final_equity,
            'stats': asdict(b.stats),
        }
        for b in rows
    ])
