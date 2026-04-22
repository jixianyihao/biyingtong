"""Circuit breaker: if today's PnL% ≤ -limit, reject all trades."""
from __future__ import annotations

from validation.base import ValidationRequest, Violation
from validation import rules as _rules


RULE_ID = 'daily_loss_limit_pct'


class Handler:
    RULE_ID = RULE_ID

    def check(self, req: ValidationRequest) -> Violation | None:
        # Accept either spec key: daily_loss_max_pct (RedLine) or daily_loss_limit_pct (persona)
        limit = req.rules.get('daily_loss_limit_pct')
        if limit is None:
            limit = req.rules.get('daily_loss_max_pct')
        if limit is None:
            return None
        pnl = req.market_context.get('pnl_today_pct')
        if pnl is None:
            return None
        if float(pnl) <= -float(limit):
            return Violation(
                rule_id=RULE_ID, severity='reject',
                reason=(f"today's PnL {pnl:.2f}% ≤ -{limit}%; "
                        f'daily loss circuit breaker tripped'),
            )
        return None


_rules.register(Handler())
