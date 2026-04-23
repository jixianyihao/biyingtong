"""GET /api/agents + /api/agents/:id + /api/agents/:id/health."""
from __future__ import annotations

from flask import jsonify

from . import api_bp


def _agent_to_dict(a) -> dict:
    return {
        'id': a.id,
        'persona_id': a.persona_id,
        'model_id': a.model_id,
        'display_name': a.display_name,
        'rules_override': a.rules_override,
        'initial_capital': a.initial_capital,
        'status': a.status,
        'health_score': a.health_score,
        'trust_rating': a.trust_rating,
        'current_prompt_version_id': a.current_prompt_version_id,
        'created_at': a.created_at,
    }


@api_bp.route('/agents')
def list_agents():
    import storage
    rows = storage.agents().list_all()
    return jsonify([_agent_to_dict(a) for a in rows])


@api_bp.route('/agents/<agent_id>')
def get_agent(agent_id):
    import storage
    a = storage.agents().get(agent_id)
    if a is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify(_agent_to_dict(a))


@api_bp.route('/agents/<agent_id>/health')
def get_agent_health(agent_id):
    """Recompute health score + rating from latest audit_log. Persists to agents."""
    import storage
    a = storage.agents().get(agent_id)
    if a is None:
        return jsonify({'error': 'not_found'}), 404

    from agents.rating import compute_health, classify_rating
    health = compute_health(agent_id)
    rating = classify_rating(health)
    storage.agents().update_health(agent_id, health=health, rating=rating)
    return jsonify({
        'agent_id': agent_id,
        'health_score': health,
        'trust_rating': rating,
    })
