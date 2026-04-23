"""GET /api/backtests — list + detail + per-session aggregated view."""
from __future__ import annotations

from dataclasses import asdict

from flask import jsonify, request

from . import api_bp


def _result_to_dict(r) -> dict:
    return {
        'id': r.id,
        'session_id': r.session_id,
        'agent_id': r.agent_id,
        'persona_id': r.persona_id,
        'model_id': r.model_id,
        'start_date': r.start_date,
        'end_date': r.end_date,
        'initial_capital': r.initial_capital,
        'final_equity': r.final_equity,
        'stats': asdict(r.stats),
        'zone_stats': [asdict(z) for z in r.zone_stats],
        'quality_gate_label': r.quality_gate_label,
        'quality_gate_criteria': r.quality_gate_criteria,
    }


@api_bp.route('/backtests')
def list_backtests():
    """List recent backtests. Optional filter: ?agent_id=..."""
    import storage
    agent_id = request.args.get('agent_id')
    limit = int(request.args.get('limit', '50'))
    if agent_id:
        rows = storage.backtests().list_for_agent(agent_id, limit=limit)
    else:
        # No global list method on store; caller should filter by agent_id
        return jsonify({'error': 'agent_id query param required'}), 400
    return jsonify([_result_to_dict(r) for r in rows])


@api_bp.route('/backtests/<result_id>')
def get_backtest(result_id):
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify(_result_to_dict(r))


@api_bp.route('/backtests/session/<session_id>')
def get_session(session_id):
    """Composite view: all agent backtests + baselines under one session."""
    import storage
    from backtest.baselines.base import BaselineResult  # noqa: F401

    agent_results = storage.backtests().list_for_session(session_id)
    baseline_results = storage.baselines().list_for_session(session_id)

    def _baseline_to_dict(b) -> dict:
        return {
            'id': b.id,
            'session_id': b.session_id,
            'name': b.name,
            'start_date': b.start_date,
            'end_date': b.end_date,
            'initial_capital': b.initial_capital,
            'final_equity': b.final_equity,
            'stats': asdict(b.stats),
        }

    return jsonify({
        'session_id': session_id,
        'agents': [_result_to_dict(r) for r in agent_results],
        'baselines': [_baseline_to_dict(b) for b in baseline_results],
    })
