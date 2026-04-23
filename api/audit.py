"""GET /api/audit — filtered audit log query."""
from __future__ import annotations

from flask import jsonify, request

from . import api_bp


@api_bp.route('/audit')
def query_audit():
    """Query audit_log. Must provide either agent_id OR kind.

    Optional ?limit=100 (default).
    """
    import storage
    agent_id = request.args.get('agent_id')
    kind = request.args.get('kind')
    limit = int(request.args.get('limit', '100'))
    if agent_id:
        rows = storage.audit().query_by_agent(agent_id, limit=limit)
    elif kind:
        rows = storage.audit().query_by_kind(kind, limit=limit)
    else:
        return jsonify({'error': 'agent_id or kind query param required'}), 400
    return jsonify(rows)
