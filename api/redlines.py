"""GET /api/redlines — current RedLine config.
PUT /api/redlines — update RedLine config (with audit trail)."""
from __future__ import annotations

from flask import jsonify, request

from . import api_bp


@api_bp.route('/redlines')
def get_redlines():
    import storage
    return jsonify(storage.redline().get())


@api_bp.route('/redlines', methods=['PUT'])
def put_redlines():
    """Merge a partial/full RedLine dict into the current config.

    Body: {<redline_key>: <value>, ...}
    Behavior:
      - Empty body -> 400 'empty body'
      - Unknown keys (not in DEFAULT_REDLINES) -> 400 listing them
      - Numeric keys: basic type check (int/float, not bool)
      - ban_*/require_*/*_check/auto_halt_* booleans: coerce to bool
      - Writes merged = {...current, ...body}
      - Logs AuditEntry(kind='redline_changed', details={'before', 'after'})
      - Returns 200 with merged dict
    """
    import storage
    from validation.base import DEFAULT_REDLINES, AuditEntry

    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify({'error': 'empty body'}), 400

    unknown = [k for k in body if k not in DEFAULT_REDLINES]
    if unknown:
        return jsonify({
            'error': f'unknown keys: {sorted(unknown)}',
        }), 400

    # Coerce / validate values
    cleaned: dict = {}
    for k, v in body.items():
        default_v = DEFAULT_REDLINES[k]
        if isinstance(default_v, bool):
            # Boolean toggle key — coerce to bool
            cleaned[k] = bool(v)
        elif isinstance(default_v, (int, float)):
            # Numeric key — must be numeric, not bool
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return jsonify({
                    'error': f'key {k!r} expects numeric, got {type(v).__name__}',
                }), 400
            cleaned[k] = v
        else:
            cleaned[k] = v

    current = storage.redline().get()
    merged = {**current, **cleaned}
    storage.redline().set(merged)

    storage.audit().log(AuditEntry(
        kind='redline_changed',
        agent_id=None,
        details={'before': current, 'after': merged},
    ))

    return jsonify(merged), 200
