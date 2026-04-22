def test_spec():
    from tools.get_portfolio import SPEC
    assert SPEC.name == 'get_portfolio'


def test_placeholder():
    from tools.get_portfolio import call
    r = call({})
    assert 'cash' in r
    assert 'positions' in r
    assert isinstance(r['positions'], list)
