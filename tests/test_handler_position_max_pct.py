"""position_max_pct handler — auto-shrink when over-cap."""
from validation.base import ValidationRequest


def _make_req(*, action, shares, price, code='600519.SH',
              held_shares=0, cash=1_000_000, equity=1_000_000,
              max_pct=15.0):
    return ValidationRequest(
        agent_id='a1',
        decision={'action': action, 'code': code,
                  'shares': shares, 'price': price},
        portfolio={
            'cash': cash,
            'equity': equity,
            'positions': {code: {'shares': held_shares, 'avg_price': price}},
        },
        market_context={},
        rules={'position_max_pct': max_pct},
    )


def test_passes_when_under_cap():
    from validation.handlers.position_max_pct import Handler
    req = _make_req(action='buy', shares=100, price=1000.0)
    assert Handler().check(req) is None


def test_shrinks_when_over_cap():
    from validation.handlers.position_max_pct import Handler
    req = _make_req(action='buy', shares=200, price=1000.0)
    v = Handler().check(req)
    assert v is not None
    assert v.rule_id == 'position_max_pct'
    assert v.severity == 'modify'
    assert v.modification == {'shares': 100}


def test_accounts_for_existing_holding():
    from validation.handlers.position_max_pct import Handler
    req = _make_req(action='buy', shares=100, price=1000.0, held_shares=100)
    v = Handler().check(req)
    assert v is not None
    assert v.severity == 'reject'


def test_existing_holding_already_over_cap_rejects_buy():
    from validation.handlers.position_max_pct import Handler
    req = _make_req(action='buy', shares=10, price=1000.0, held_shares=200)
    v = Handler().check(req)
    assert v is not None
    assert v.severity == 'reject'


def test_sell_is_always_ok():
    from validation.handlers.position_max_pct import Handler
    req = _make_req(action='sell', shares=50, price=1000.0, held_shares=200)
    assert Handler().check(req) is None


def test_zero_cap_rejects_any_buy():
    from validation.handlers.position_max_pct import Handler
    req = _make_req(action='buy', shares=1, price=1000.0, max_pct=0.0)
    v = Handler().check(req)
    assert v is not None
    assert v.severity == 'reject'


def test_missing_rule_is_noop():
    from validation.handlers.position_max_pct import Handler
    req = ValidationRequest(
        agent_id='a1', decision={'action': 'buy', 'code': 'X', 'shares': 1, 'price': 1.0},
        portfolio={'equity': 1.0, 'positions': {}}, market_context={}, rules={},
    )
    assert Handler().check(req) is None


def test_shrink_rounds_down_to_lot_100():
    """Auto-shrink must produce a multiple of 100."""
    from validation.handlers.position_max_pct import Handler
    from validation.base import ValidationRequest
    # 1M equity * 15% cap = 150k. price=237 → allowed_additional = 632 (before rounding)
    # After lot rounding → 600 shares
    req = ValidationRequest(
        agent_id='a1',
        decision={'action': 'buy', 'code': 'X.SH', 'shares': 1000,
                  'price': 237.0},
        portfolio={'equity': 1_000_000.0, 'positions': {}},
        market_context={},
        rules={'position_max_pct': 15.0},
    )
    v = Handler().check(req)
    assert v is not None
    assert v.severity == 'modify'
    assert v.modification == {'shares': 600}


def test_shrink_below_one_lot_rejects():
    """If the allowed quantity would be < 100, reject instead."""
    from validation.handlers.position_max_pct import Handler
    from validation.base import ValidationRequest
    # 100k equity * 0.05% cap = 50. price=1000 → allowed_additional = 0
    req = ValidationRequest(
        agent_id='a1',
        decision={'action': 'buy', 'code': 'X.SH', 'shares': 100,
                  'price': 1000.0},
        portfolio={'equity': 100_000.0, 'positions': {}},
        market_context={},
        rules={'position_max_pct': 0.05},
    )
    v = Handler().check(req)
    assert v is not None
    assert v.severity == 'reject'


def test_registered_on_import():
    from validation import rules
    import validation.handlers.position_max_pct  # noqa: F401
    assert rules.get('position_max_pct') is not None
