"""Core types for the validation engine.

Two layers per Spec § 7:
  Layer 1 — RedLine (single-row `redlines` table, immutable ceiling)
  Layer 2 — Agent rules_override (stricter-only, merged via apply_override)

Handlers consume the merged dict and each check a single rule.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_REDLINES: dict[str, Any] = {
    # hard upper-bound limits (override may only lower)
    'daily_loss_max_pct':    3.0,
    'position_max_pct':      15.0,
    'stock_concentration':   30.0,
    'order_max_value':       200_000,
    'turnover_max_daily':    300.0,
    'same_stock_cooldown_min': 5,
    # hard lower-bound limits (override may only raise)
    'cash_min_pct':          5.0,
    # behavioral toggles (override may only turn on)
    'ban_limit_up':          True,
    'ban_st':                True,
    'ban_limit_down':        True,
    'ban_ipo_30d':           True,
    'require_reason':        True,
    'prompt_injection_check': True,
    'auto_halt_var_2sigma':  True,
}


DEFAULT_QUALITY_GATE: dict[str, Any] = {
    'min_sharpe':            0.3,
    'max_drawdown_pct':     -25.0,
    'min_trade_count':       5,
    'min_win_rate':          30.0,
    'max_daily_loss_pct':   -5.0,
    'min_clean_zone_days':   60,
    'max_divergence_flag':   False,
}


# Keys that are lower-bounds (override may only *raise* them).
_LOWER_BOUND_KEYS = frozenset({'cash_min_pct'})


def apply_override(redline: dict, override: dict | None) -> dict:
    """Merge per-agent override onto RedLine, clamping to RedLine's direction.

    Upper-bound numeric keys      -> min(redline, override)
    Lower-bound numeric keys      -> max(redline, override)
    Boolean keys starting 'ban_'  -> redline OR override (only tighten)
    Unknown keys in override      -> pass through (persona-only rules)
    Keys only in redline          -> kept as-is
    """
    if not override:
        return dict(redline)
    result = dict(redline)
    for k, v in override.items():
        if k not in redline:
            result[k] = v
            continue
        rv = redline[k]
        if isinstance(rv, bool) and k.startswith('ban_'):
            result[k] = bool(rv) or bool(v)
        elif k in _LOWER_BOUND_KEYS:
            result[k] = max(rv, v)
        elif isinstance(rv, (int, float)) and not isinstance(rv, bool):
            result[k] = min(rv, v)
        else:
            result[k] = rv
    return result


@dataclass(frozen=True)
class ValidationRequest:
    """Snapshot of everything a handler needs to judge one decision."""
    agent_id: str
    decision: dict
    portfolio: dict
    market_context: dict
    rules: dict
    persona_id: str | None = None
    model_id: str | None = None


@dataclass(frozen=True)
class Violation:
    rule_id: str
    severity: str
    reason: str
    modification: dict | None = None


@dataclass(frozen=True)
class ValidationResult:
    outcome: str
    decision_out: dict | None
    violations: tuple = ()


@dataclass(frozen=True)
class QualityGateResult:
    label: str
    criteria: dict


@dataclass
class AuditEntry:
    """One row for `audit_log` — `details` is serialized to JSON by the store."""
    kind: str
    agent_id: str | None = None
    persona_id: str | None = None
    model_id: str | None = None
    prompt_version: int | None = None
    details: dict = field(default_factory=dict)
