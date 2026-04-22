"""ban_st handler — blocks trades on ST stocks."""
from validation.base import ValidationRequest


def _req(code, ban=True, action='buy'):
    return ValidationRequest(
        agent_id='a1',
        decision={'action': action, 'code': code, 'shares': 100, 'price': 10.0},
        portfolio={'equity': 1_000_000, 'positions': {}},
        market_context={}, rules={'ban_st': ban},
    )


def _wire(tmp_path):
    import storage
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    storage.set_stock_status(s)
    return s


def test_pass_when_code_not_st(tmp_path):
    from storage.base import StockStatusRow
    from validation.handlers.ban_st import Handler
    s = _wire(tmp_path)
    s.upsert(StockStatusRow(code='600519.SH', name='贵州茅台',
                            is_st=False, is_suspended=False, is_delisted=False))
    assert Handler().check(_req('600519.SH')) is None


def test_reject_when_code_is_st(tmp_path):
    from storage.base import StockStatusRow
    from validation.handlers.ban_st import Handler
    s = _wire(tmp_path)
    s.upsert(StockStatusRow(code='000666.SZ', name='*ST 经纬',
                            is_st=True, is_suspended=False, is_delisted=False))
    v = Handler().check(_req('000666.SZ'))
    assert v is not None
    assert v.severity == 'reject'
    assert 'ST' in v.reason


def test_pass_when_toggle_false(tmp_path):
    from storage.base import StockStatusRow
    from validation.handlers.ban_st import Handler
    s = _wire(tmp_path)
    s.upsert(StockStatusRow(code='X.SH', name='*ST X',
                            is_st=True, is_suspended=False, is_delisted=False))
    assert Handler().check(_req('X.SH', ban=False)) is None


def test_pass_when_unknown_code(tmp_path):
    """No row → not flagged → trade allowed (fail-open on missing data)."""
    from validation.handlers.ban_st import Handler
    _wire(tmp_path)
    assert Handler().check(_req('NOTINDB.SH')) is None


def test_sell_is_allowed_even_on_st(tmp_path):
    """Spec: ban_st blocks new buys; selling existing holdings remains allowed."""
    from storage.base import StockStatusRow
    from validation.handlers.ban_st import Handler
    s = _wire(tmp_path)
    s.upsert(StockStatusRow(code='Y.SH', name='*ST Y',
                            is_st=True, is_suspended=False, is_delisted=False))
    assert Handler().check(_req('Y.SH', action='sell')) is None


def test_registered_on_import():
    from validation import rules
    import validation.handlers.ban_st  # noqa: F401
    assert rules.get('ban_st') is not None
