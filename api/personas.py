"""GET /api/personas + CRUD on non-builtin personas (P3-B)."""
from __future__ import annotations

from flask import jsonify, request

from . import api_bp


def _persona_to_dict(p) -> dict:
    return {
        'id': p.id, 'name': p.name, 'style_desc': p.style_desc,
        'system_prompt': p.system_prompt,
        'default_pool': p.default_pool, 'pool_filter': p.pool_filter,
        'default_schedule': p.default_schedule,
        'default_rules': p.default_rules,
        'allowed_tools': p.allowed_tools,
        'is_builtin': p.is_builtin,
    }


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


@api_bp.route('/personas', methods=['POST'])
def create_persona():
    import storage
    from storage.base import Persona
    body = request.get_json(silent=True) or {}
    required = ['id', 'name', 'style_desc', 'system_prompt']
    missing = [k for k in required if not body.get(k)]
    if missing:
        return jsonify({'error': f'missing required fields: {missing}'}), 400
    if storage.personas().get(body['id']) is not None:
        return jsonify({'error': f'persona {body["id"]!r} already exists'}), 409
    persona = Persona(
        id=body['id'], name=body['name'],
        style_desc=body['style_desc'],
        system_prompt=body['system_prompt'],
        default_pool=body.get('default_pool') or [],
        pool_filter=body.get('pool_filter'),
        default_schedule=body.get('default_schedule') or 'daily',
        default_rules=body.get('default_rules') or {},
        allowed_tools=body.get('allowed_tools') or [],
        is_builtin=False,
    )
    storage.personas().upsert(persona)
    return jsonify(_persona_to_dict(persona)), 201


@api_bp.route('/personas/<persona_id>', methods=['PUT'])
def update_persona(persona_id):
    import storage
    from storage.base import Persona
    p = storage.personas().get(persona_id)
    if p is None:
        return jsonify({'error': 'not_found'}), 404
    if p.is_builtin:
        return jsonify({'error': 'cannot edit builtin persona'}), 403
    body = request.get_json(silent=True) or {}

    updated = Persona(
        id=p.id,
        name=body.get('name', p.name),
        style_desc=body.get('style_desc', p.style_desc),
        system_prompt=body.get('system_prompt', p.system_prompt),
        default_pool=body.get('default_pool', p.default_pool),
        pool_filter=body.get('pool_filter', p.pool_filter),
        default_schedule=body.get('default_schedule', p.default_schedule),
        default_rules=body.get('default_rules', p.default_rules),
        allowed_tools=body.get('allowed_tools', p.allowed_tools),
        is_builtin=False,
    )
    storage.personas().upsert(updated)

    # If system_prompt changed, bump prompt_version for every referencing agent
    if updated.system_prompt != p.system_prompt:
        for a in storage.agents().list_all():
            if a.persona_id == persona_id:
                pv = storage.prompt_versions().insert(
                    agent_id=a.id,
                    system_prompt=updated.system_prompt,
                    note=f'persona.{persona_id} system_prompt updated',
                )
                storage.agents().set_current_prompt_version(a.id, pv.id)

    return jsonify(_persona_to_dict(updated))


@api_bp.route('/personas/<persona_id>', methods=['DELETE'])
def delete_persona(persona_id):
    import storage
    p = storage.personas().get(persona_id)
    if p is None:
        return jsonify({'error': 'not_found'}), 404
    if p.is_builtin:
        return jsonify({'error': 'cannot delete builtin persona'}), 403
    for a in storage.agents().list_all():
        if a.persona_id == persona_id:
            return jsonify({
                'error': f'persona {persona_id!r} is referenced by agent {a.id!r}',
            }), 409
    storage.personas().delete(persona_id)
    return '', 204
