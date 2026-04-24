"""P2e REST API — Flask Blueprint for personas/agents/backtests/redlines/audit.

Read-only endpoints. Mutations (create agent, start backtest) come in a
follow-up sub-plan.

Register into app.py via:
    from api import api_bp
    app.register_blueprint(api_bp)
"""
from __future__ import annotations

from flask import Blueprint

api_bp = Blueprint('api_p2e', __name__, url_prefix='/api')

from . import personas      # noqa: F401,E402  side-effect: register routes
from . import models         # noqa: F401,E402
from . import agents         # noqa: F401,E402
from . import backtests      # noqa: F401,E402
from . import backtest_jobs  # noqa: F401,E402
from . import rating         # noqa: F401,E402
from . import baselines      # noqa: F401,E402
from . import redlines       # noqa: F401,E402
from . import audit          # noqa: F401,E402
from . import strategies     # noqa: F401,E402
from . import deploy         # noqa: F401,E402  P3-F Phase 1
from . import proposals      # noqa: F401,E402  P3-F Phase 1
