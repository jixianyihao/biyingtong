"""Persona data modules — sanity-check structure."""


def test_all_personas_registered():
    from personas import ALL_PERSONAS
    assert set(ALL_PERSONAS.keys()) == {
        'linyuan', 'fuyou', 'buffet', 'soros', 'quant_neutral',
    }


def test_every_persona_has_required_keys():
    from personas import ALL_PERSONAS
    required = {
        'id', 'name', 'style_desc', 'system_prompt',
        'default_pool', 'pool_filter', 'default_schedule',
        'default_rules', 'allowed_tools', 'is_builtin',
    }
    for key, data in ALL_PERSONAS.items():
        missing = required - set(data.keys())
        assert not missing, f'{key} missing keys: {missing}'


def test_persona_id_matches_registry_key():
    from personas import ALL_PERSONAS
    for key, data in ALL_PERSONAS.items():
        assert data['id'] == key


def test_every_pool_is_non_empty_and_valid_format():
    from personas import ALL_PERSONAS
    for key, data in ALL_PERSONAS.items():
        pool = data['default_pool']
        assert isinstance(pool, list)
        assert len(pool) > 0, f'{key} has empty default_pool'
        for code in pool:
            assert isinstance(code, str)
            assert '.' in code, f'{key}: code {code!r} must be like 600519.SH'
            prefix, suffix = code.split('.', 1)
            assert prefix.isdigit() and len(prefix) == 6
            assert suffix in ('SH', 'SZ'), f'{key}: code {code!r} has bad suffix'


def test_every_schedule_is_valid():
    from personas import ALL_PERSONAS
    valid = {'daily', 'weekly', 'monthly', 'intraday_5m'}
    for key, data in ALL_PERSONAS.items():
        assert data['default_schedule'] in valid, (
            f'{key}: bad schedule {data["default_schedule"]!r}'
        )


def test_every_default_rules_has_position_max_pct():
    """All built-in personas must cap single-position size."""
    from personas import ALL_PERSONAS
    for key, data in ALL_PERSONAS.items():
        rules = data['default_rules']
        assert 'position_max_pct' in rules, f'{key} missing position_max_pct rule'
        assert 0 < rules['position_max_pct'] <= 100


def test_system_prompts_are_substantial():
    """Each persona's prompt should be at least a few sentences."""
    from personas import ALL_PERSONAS
    for key, data in ALL_PERSONAS.items():
        assert len(data['system_prompt']) > 100, (
            f'{key} system_prompt suspiciously short'
        )


def test_allowed_tools_includes_get_kline():
    """Every persona needs K-line access; place_decision is always granted implicitly."""
    from personas import ALL_PERSONAS
    for key, data in ALL_PERSONAS.items():
        assert 'get_kline' in data['allowed_tools'], (
            f'{key} should include get_kline in allowed_tools'
        )
