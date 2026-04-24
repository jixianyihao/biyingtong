"""Trade proposal endpoints (P3-F Phase 1).

approve/reject are DB state changes ONLY — there is no TDX integration in
Phase 1. Phase 2 (separate consent plan) wires real execution.

Auth model:
  POST /api/proposals is the internal endpoint called by the agent
  subprocess. It reads the BIYINGTONG_PROPOSAL_TOKEN env var:
    - env set   → X-Proposal-Token header must match exactly (else 403)
    - env unset → any token (or none) is accepted; intended for dev
"""
from __future__ import annotations

import os

from flask import jsonify, request

from . import api_bp


def _proposal_to_dict(p) -> dict:
    return {
        'id': p.id,
        'agent_id': p.agent_id,
        'created_at': p.created_at,
        'decision_at': p.decision_at,
        'action': p.action,
        'code': p.code,
        'shares': p.shares,
        'price': p.price,
        'reason': p.reason,
        'thinking': p.thinking,
        'status': p.status,
        'decided_by': p.decided_by,
        'decided_at': p.decided_at,
    }


@api_bp.route('/proposals', methods=['POST'])
def create_proposal():
    """Internal endpoint — called by the agent subprocess.

    Auth: when BIYINGTONG_PROPOSAL_TOKEN is set, X-Proposal-Token header
    must match. When unset (dev mode), any token is accepted.
    """
    import storage
    from storage.base import TradeProposal

    expected_token = os.environ.get('BIYINGTONG_PROPOSAL_TOKEN')
    if expected_token:
        got_token = request.headers.get('X-Proposal-Token', '')
        if got_token != expected_token:
            return jsonify({'error': 'invalid proposal token'}), 403

    body = request.get_json(silent=True) or {}
    required = ['id', 'agent_id', 'decision_at', 'action']
    missing = [k for k in required if not body.get(k)]
    if missing:
        return jsonify({'error': f'missing: {missing}'}), 400

    p = TradeProposal(
        id=body['id'], agent_id=body['agent_id'],
        decision_at=body['decision_at'], action=body['action'],
        code=body.get('code'), shares=body.get('shares'),
        price=body.get('price'),
        reason=body.get('reason'), thinking=body.get('thinking'),
        status='pending',
    )
    storage.proposals().insert(p)
    return jsonify(_proposal_to_dict(p)), 201


@api_bp.route('/proposals')
def list_proposals():
    """List proposals. Defaults to status=pending.

    Query params:
      status=pending|approved|rejected|expired  (default: pending)
      agent_id=<id>                              (optional filter)
      limit=N                                    (default 100)

    To avoid leaking cross-agent data, a non-'pending' status requires
    agent_id to be provided.
    """
    import storage
    status = request.args.get('status', 'pending')
    agent_id = request.args.get('agent_id')
    limit = int(request.args.get('limit', '100'))
    if status == 'pending':
        rows = storage.proposals().list_pending(agent_id=agent_id, limit=limit)
    elif agent_id:
        rows = [p for p in storage.proposals().list_for_agent(agent_id, limit=limit)
                if p.status == status]
    else:
        return jsonify({'error': 'agent_id or status=pending required'}), 400
    return jsonify([_proposal_to_dict(p) for p in rows])


@api_bp.route('/proposals/<proposal_id>')
def get_proposal(proposal_id):
    import storage
    p = storage.proposals().get(proposal_id)
    if p is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify(_proposal_to_dict(p))


@api_bp.route('/proposals/<proposal_id>/approve', methods=['POST'])
def approve_proposal(proposal_id):
    """Phase 1: flip status to 'approved' in DB. NO TDX CALL.

    Phase 2 (a separate plan, not this task) will wire actual TDX
    execution here. For now we only record intent — user must manually
    execute any approved trade.
    """
    import storage
    p = storage.proposals().get(proposal_id)
    if p is None:
        return jsonify({'error': 'not_found'}), 404
    if p.status != 'pending':
        return jsonify({'error': f'already {p.status}'}), 409
    storage.proposals().update_status(proposal_id, 'approved',
                                      decided_by='user')
    return jsonify(_proposal_to_dict(storage.proposals().get(proposal_id)))


@api_bp.route('/proposals/<proposal_id>/reject', methods=['POST'])
def reject_proposal(proposal_id):
    """Phase 1: flip status to 'rejected' in DB."""
    import storage
    p = storage.proposals().get(proposal_id)
    if p is None:
        return jsonify({'error': 'not_found'}), 404
    if p.status != 'pending':
        return jsonify({'error': f'already {p.status}'}), 409
    storage.proposals().update_status(proposal_id, 'rejected',
                                      decided_by='user')
    return jsonify(_proposal_to_dict(storage.proposals().get(proposal_id)))
