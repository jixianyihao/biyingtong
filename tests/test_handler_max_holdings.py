"""max_holdings handler — reject opening a new position when at cap."""
from validation.base import ValidationRequest


def _req(code, action='buy', positions=None, max_holdings=3):
    return ValidationRequest(
        agent_id='a1',
        decision={'action': action, 'code': code, 'shares': 100, 'price': 10.0},
        portfolio={'equity': 1_000_000,
                   'positions': positions or {}},
        market_context={},
        rules={'max_holdings': max_holdings},
    )


def test_open_new_when_below_cap_passes():
    from validation.handlers.max_holdings import Handler
    req = _req('X.SH', positions={'A.SH': {'shares': 100},
                                  'B.SH': {'shares': 100}})
    assert Handler().check(req) is None


def test_open_new_when_at_cap_rejects():
    from validation.handlers.max_holdings import Handler
    req = _req('D.SH', positions={
        'A.SH': {'shares': 100},
        'B.SH': {'shares': 100},
        'C.SH': {'shares': 100},
    })
    v = Handler().check(req)
    assert v is not None
    assert v.severity == 'reject'


def test_add_to_existing_at_cap_is_allowed():
    """Same code → no new position opened → pass even at cap."""
    from validation.handlers.max_holdings import Handler
    req = _req('A.SH', positions={
        'A.SH': {'shares': 100},
        'B.SH': {'shares': 100},
        'C.SH': {'shares': 100},
    })
    assert Handler().check(req) is None


def test_zero_share_position_does_not_count():
    """A stub entry with shares=0 isn't a real position."""
    from validation.handlers.max_holdings import Handler
    req = _req('X.SH', positions={
        'A.SH': {'shares': 100},
        'B.SH': {'shares': 100},
        'C.SH': {'shares': 0},
    })
    assert Handler().check(req) is None


def test_sell_is_noop():
    from validation.handlers.max_holdings import Handler
    req = _req('D.SH', action='sell', positions={
        'A.SH': {'shares': 100}, 'B.SH': {'shares': 100},
        'C.SH': {'shares': 100},
    })
    assert Handler().check(req) is None


def test_no_rule_is_noop():
    from validation.handlers.max_holdings import Handler
    req = ValidationRequest(
        agent_id='a1',
        decision={'action': 'buy', 'code': 'X', 'shares': 1, 'price': 1.0},
        portfolio={'equity': 1, 'positions': {}}, market_context={}, rules={},
    )
    assert Handler().check(req) is None


def test_registered_on_import():
    from validation import rules
    import validation.handlers.max_holdings  # noqa: F401
    assert rules.get('max_holdings') is not None
