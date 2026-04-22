"""Rejects buys on ST stocks when the toggle is on."""
from __future__ import annotations

from validation.base import ValidationRequest, Violation
from validation import rules as _rules


RULE_ID = 'ban_st'


class Handler:
    RULE_ID = RULE_ID

    def check(self, req: ValidationRequest) -> Violation | None:
        if not req.rules.get('ban_st'):
            return None
        action = (req.decision.get('action') or '').lower()
        if action != 'buy':
            return None
        code = req.decision.get('code')
        if not code:
            return None
        import storage
        if storage.stock_status().is_st(code):
            return Violation(
                rule_id=RULE_ID, severity='reject',
                reason=f'{code} is ST — ban_st toggle rejects buy',
            )
        return None


_rules.register(Handler())
