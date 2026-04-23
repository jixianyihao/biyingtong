"""GET /api/models — list enabled LLM models."""
from __future__ import annotations

from flask import jsonify

from . import api_bp


@api_bp.route('/models')
def list_models():
    import storage
    rows = storage.models().list_enabled()
    return jsonify([
        {
            'id': m.id,
            'provider': m.provider,
            'display_name': m.display_name,
            'api_model_id': m.api_model_id,
            'training_cutoff': m.training_cutoff,
            'supports_tool_use': m.supports_tool_use,
            'max_tokens_out': m.max_tokens_out,
            'enabled': m.enabled,
        }
        for m in rows
    ])


@api_bp.route('/models/<model_id>')
def get_model(model_id):
    import storage
    m = storage.models().get(model_id)
    if m is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'id': m.id,
        'provider': m.provider,
        'display_name': m.display_name,
        'api_model_id': m.api_model_id,
        'training_cutoff': m.training_cutoff,
        'supports_tool_use': m.supports_tool_use,
        'max_tokens_out': m.max_tokens_out,
        'enabled': m.enabled,
    })
