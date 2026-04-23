"""GET /api/redlines — current RedLine config."""
from __future__ import annotations

from flask import jsonify

from . import api_bp


@api_bp.route('/redlines')
def get_redlines():
    import storage
    return jsonify(storage.redline().get())
