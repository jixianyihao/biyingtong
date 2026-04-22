"""Importing this package registers every built-in rule handler.

Subagents: add `from . import <new_handler>` here when you add a handler
module, so tests and the engine both see it via the registry.
"""
from . import position_max_pct  # noqa: F401
from . import ban_st  # noqa: F401
from . import max_holdings  # noqa: F401
