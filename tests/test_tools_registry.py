def test_all_tools_registered():
    from tools import ALL_TOOLS
    assert set(ALL_TOOLS.keys()) == {
        'place_decision', 'get_kline', 'get_snapshot', 'get_financials',
        'get_technical', 'get_index', 'get_portfolio', 'get_news',
        'get_stock_list', 'get_capital_flow', 'get_forward_pe',
    }


def test_spec_name_matches_registry_key():
    from tools import ALL_TOOLS
    for key, (spec, _) in ALL_TOOLS.items():
        assert spec.name == key


def test_all_schemas_are_object_type():
    from tools import ALL_TOOLS
    for key, (spec, _) in ALL_TOOLS.items():
        assert spec.input_schema.get('type') == 'object', f'{key} not object-type'


def test_filter_allowed_always_includes_place_decision():
    from tools import filter_allowed
    r = filter_allowed([])
    assert 'place_decision' in r
    assert set(r.keys()) == {'place_decision'}


def test_filter_allowed_subset():
    from tools import filter_allowed
    r = filter_allowed(['get_kline', 'get_financials'])
    assert set(r.keys()) == {'place_decision', 'get_kline', 'get_financials'}


def test_filter_allowed_drops_unknown():
    from tools import filter_allowed
    r = filter_allowed(['get_kline', 'fake_tool'])
    assert 'get_kline' in r
    assert 'fake_tool' not in r
