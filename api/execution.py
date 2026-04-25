"""GET /api/execution/mode — tells the UI which adapter is active.

The UI gates the LIVE-approval 2-step confirmation modal on this value;
when 'live' the TopBar pulses a red badge. Any change to the underlying
BIYINGTONG_EXECUTION_MODE env var takes effect on the next request
because get_adapter() re-reads os.environ every call.
"""
from __future__ import annotations

from flask import jsonify

from . import api_bp


@api_bp.route('/execution/mode')
def get_execution_mode():
    from execution import get_adapter
    return jsonify({'mode': get_adapter().mode})
