"""POST a trade proposal to Flask. Uses shared-secret token for auth."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone


def emit_proposal(flask_url: str, agent_id: str, decision: dict) -> dict:
    """POST decision as a proposal. Returns server response JSON.

    Shared secret via env BIYINGTONG_PROPOSAL_TOKEN (Flask checks matching).
    """
    import requests
    token = os.environ.get('BIYINGTONG_PROPOSAL_TOKEN', '')
    payload = {
        'id': str(uuid.uuid4()),
        'agent_id': agent_id,
        'decision_at': datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds'),
        'action': decision.get('action', 'hold'),
        'code': decision.get('code'),
        'shares': decision.get('shares'),
        'price': decision.get('price'),
        'reason': decision.get('reason'),
        'thinking': decision.get('thinking'),
    }
    resp = requests.post(
        f'{flask_url.rstrip("/")}/api/proposals',
        json=payload,
        headers={'X-Proposal-Token': token} if token else {},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
