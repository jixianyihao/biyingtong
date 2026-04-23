"""GET /api/personas — list built-in + seeded personas."""
from __future__ import annotations

from flask import jsonify

from . import api_bp


@api_bp.route('/personas')
def list_personas():
    import storage
    rows = storage.personas().list_all()
    return jsonify([
        {
            'id': p.id,
            'name': p.name,
            'style_desc': p.style_desc,
            'default_schedule': p.default_schedule,
            'default_pool': p.default_pool,
            'allowed_tools': p.allowed_tools,
            'default_rules': p.default_rules,
            'is_builtin': p.is_builtin,
        }
        for p in rows
    ])


@api_bp.route('/personas/<persona_id>')
def get_persona(persona_id):
    import storage
    p = storage.personas().get(persona_id)
    if p is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'id': p.id,
        'name': p.name,
        'style_desc': p.style_desc,
        'system_prompt': p.system_prompt,
        'default_schedule': p.default_schedule,
        'default_pool': p.default_pool,
        'pool_filter': p.pool_filter,
        'allowed_tools': p.allowed_tools,
        'default_rules': p.default_rules,
        'is_builtin': p.is_builtin,
    })
