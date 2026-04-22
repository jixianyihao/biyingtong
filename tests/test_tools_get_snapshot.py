def test_spec_shape():
    from tools.get_snapshot import SPEC
    assert SPEC.name == 'get_snapshot'


def test_returns_five_level_quote(tdx_ready):
    from tools.get_snapshot import call
    r = call({'code': '600519.SH'})
    assert r['price'] > 0
    assert 'bid1' in r
    assert 'ask1' in r


def test_handles_bare_code(tdx_ready):
    from tools.get_snapshot import call
    r = call({'code': '600519'})
    assert r['price'] > 0


def test_unknown_stock(tdx_ready):
    from tools.get_snapshot import call
    # 000000.SH is a truly non-existent code (999999.SH is the SSE Composite Index)
    r = call({'code': '000000.SH'})
    assert r.get('price', 0) == 0 or 'error' in r
