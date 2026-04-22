def test_place_decision_spec_shape():
    from tools.place_decision import SPEC
    assert SPEC.name == 'place_decision'
    s = SPEC.input_schema
    assert set(s['properties']['action']['enum']) == {'buy', 'sell', 'hold'}
    assert set(s['required']) == {'action', 'reason', 'thinking'}


def test_place_decision_returns_terminator():
    from tools.place_decision import call
    r = call({'action': 'buy', 'code': '600519.SH', 'qty': 100,
              'reason': 'PE below historical median, good entry',
              'thinking': 'Details...'})
    assert r['action'] == 'buy'
    assert r['_terminator'] is True


def test_place_decision_hold_allows_empty_code():
    from tools.place_decision import call
    r = call({'action': 'hold',
              'reason': 'No clear signal today in this market',
              'thinking': 'noise'})
    assert r['action'] == 'hold'
    assert r.get('code', '') == ''


def test_place_decision_rejects_missing_required():
    from tools.place_decision import call
    import pytest
    with pytest.raises(ValueError, match='reason'):
        call({'action': 'buy', 'thinking': 'x'})


def test_place_decision_short_reason():
    from tools.place_decision import call
    import pytest
    with pytest.raises(ValueError, match='at least 20'):
        call({'action': 'buy', 'reason': 'short', 'thinking': 'x'})
