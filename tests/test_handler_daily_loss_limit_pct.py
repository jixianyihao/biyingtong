"""daily_loss_limit_pct / daily_loss_max_pct — circuit breaker."""
from validation.base import ValidationRequest


def _req(pnl_today_pct, *, action='buy', limit_pct=3.0, alt_key=False):
    key = 'daily_loss_max_pct' if alt_key else 'daily_loss_limit_pct'
    return ValidationRequest(
        agent_id='a1',
        decision={'action': action, 'code': 'X.SH', 'shares': 1, 'price': 1.0},
        portfolio={'equity': 1, 'positions': {}},
        market_context={'pnl_today_pct': pnl_today_pct},
        rules={key: limit_pct},
    )


def test_pass_when_pnl_above_limit():
    from validation.handlers.daily_loss_limit_pct import Handler
    assert Handler().check(_req(-1.5)) is None  # -1.5% > -3%


def test_reject_when_pnl_below_limit():
    from validation.handlers.daily_loss_limit_pct import Handler
    v = Handler().check(_req(-3.5))  # -3.5% ≤ -3%
    assert v is not None
    assert v.severity == 'reject'


def test_reject_at_exact_limit():
    """Inclusive: hitting -limit exactly trips the breaker."""
    from validation.handlers.daily_loss_limit_pct import Handler
    v = Handler().check(_req(-3.0))
    assert v is not None
    assert v.severity == 'reject'


def test_reject_sells_too():
    """Breaker blocks all trades, not just buys."""
    from validation.handlers.daily_loss_limit_pct import Handler
    v = Handler().check(_req(-5.0, action='sell'))
    assert v is not None
    assert v.severity == 'reject'


def test_positive_pnl_always_ok():
    from validation.handlers.daily_loss_limit_pct import Handler
    assert Handler().check(_req(2.5)) is None


def test_accepts_spec_key_daily_loss_max_pct():
    from validation.handlers.daily_loss_limit_pct import Handler
    v = Handler().check(_req(-4.0, limit_pct=3.0, alt_key=True))
    assert v is not None
    assert v.severity == 'reject'


def test_missing_pnl_in_context_passes():
    """Conservatively pass when pnl unknown — engine audit still records."""
    from validation.handlers.daily_loss_limit_pct import Handler
    req = ValidationRequest(
        agent_id='a1',
        decision={'action': 'buy', 'code': 'X', 'shares': 1, 'price': 1.0},
        portfolio={'equity': 1, 'positions': {}},
        market_context={}, rules={'daily_loss_limit_pct': 3.0},
    )
    assert Handler().check(req) is None


def test_registered_on_import():
    from validation import rules
    import validation.handlers.daily_loss_limit_pct  # noqa: F401
    assert rules.get('daily_loss_limit_pct') is not None
