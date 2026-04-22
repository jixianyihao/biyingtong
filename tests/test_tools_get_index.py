def test_spec():
    from tools.get_index import SPEC
    assert SPEC.name == 'get_index'


def test_returns_hs300(tdx_ready):
    from tools.get_index import call
    r = call({'index_code': '000300.SH'})
    assert r['price'] > 0
