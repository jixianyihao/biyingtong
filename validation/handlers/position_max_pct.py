"""Constrains single-stock value as % of equity.

Policy:
  - BUY that would bring position over cap  →  auto-modify, shrink shares
  - BUY when existing holding already over cap → reject
  - cap == 0 → reject any buy
  - SELL / non-buy → pass through
"""
from __future__ import annotations

import math

from validation.base import ValidationRequest, Violation
from validation import rules as _rules


RULE_ID = 'position_max_pct'


class Handler:
    RULE_ID = RULE_ID

    def check(self, req: ValidationRequest) -> Violation | None:
        cap_pct = req.rules.get('position_max_pct')
        if cap_pct is None:
            return None
        action = (req.decision.get('action') or '').lower()
        if action != 'buy':
            return None

        equity = float(req.portfolio.get('equity', 0.0))
        if equity <= 0:
            return None
        price = float(req.decision.get('price', 0.0))
        if price <= 0:
            return None

        code = req.decision.get('code')
        held = int(req.portfolio.get('positions', {}).get(code, {}).get('shares', 0))
        shares_req = int(req.decision.get('shares', 0))

        max_value = equity * (float(cap_pct) / 100.0)
        if max_value <= 0:
            return Violation(
                rule_id=RULE_ID, severity='reject',
                reason=f'position_max_pct={cap_pct} forbids any buy',
            )

        held_value = held * price
        if held_value >= max_value:
            return Violation(
                rule_id=RULE_ID, severity='reject',
                reason=(f'existing holding value {held_value:.0f} already '
                        f'≥ cap {max_value:.0f}'),
            )

        post_value = (held + shares_req) * price
        if post_value <= max_value:
            return None

        allowed_additional = int(math.floor((max_value - held_value) / price))
        # A-share lot: must be multiple of 100
        allowed_additional = (allowed_additional // 100) * 100
        if allowed_additional < 100:
            return Violation(
                rule_id=RULE_ID, severity='reject',
                reason=(f'cap allows only {allowed_additional} shares; '
                        f'below A-share minimum lot of 100'),
            )
        if allowed_additional < shares_req:
            return Violation(
                rule_id=RULE_ID, severity='modify',
                reason=(f'post-trade value > cap {max_value:.0f}; '
                        f'shrink to {allowed_additional} shares '
                        f'(rounded to lot of 100)'),
                modification={'shares': allowed_additional},
            )
        return None


_rules.register(Handler())
