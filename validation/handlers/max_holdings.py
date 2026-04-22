"""Caps number of distinct positions (new-opening rejection only)."""
from __future__ import annotations

from validation.base import ValidationRequest, Violation
from validation import rules as _rules


RULE_ID = 'max_holdings'


def _active_codes(positions: dict) -> set:
    return {c for c, p in (positions or {}).items()
            if int(p.get('shares', 0) or 0) > 0}


class Handler:
    RULE_ID = RULE_ID

    def check(self, req: ValidationRequest) -> Violation | None:
        cap = req.rules.get('max_holdings')
        if cap is None:
            return None
        action = (req.decision.get('action') or '').lower()
        if action != 'buy':
            return None
        code = req.decision.get('code')
        active = _active_codes(req.portfolio.get('positions', {}))
        if code in active:
            return None
        if len(active) < cap:
            return None
        return Violation(
            rule_id=RULE_ID, severity='reject',
            reason=(f'already holding {len(active)} positions ≥ cap {cap}; '
                    f'cannot open new position in {code}'),
        )


_rules.register(Handler())
