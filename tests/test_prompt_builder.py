"""Prompt builder for agent LLM calls."""


def test_system_prompt_from_version():
    from agents.prompt_builder import build_messages
    msgs = build_messages(
        system_prompt='你是一位价值投资者。',
        date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000,
                   'positions': {}},
        market_context={},
        default_pool=['600519.SH'],
    )
    assert msgs[0].role == 'system'
    assert msgs[0].content == '你是一位价值投资者。'


def test_user_message_contains_date_and_pool():
    from agents.prompt_builder import build_messages
    msgs = build_messages(
        system_prompt='X',
        date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={},
        default_pool=['600519.SH', '000858.SZ'],
    )
    user = msgs[1].content
    assert '2024-03-15' in user
    assert '600519.SH' in user
    assert '000858.SZ' in user


def test_user_message_shows_positions():
    from agents.prompt_builder import build_messages
    msgs = build_messages(
        system_prompt='X', date='2024-03-15',
        portfolio={'cash': 500_000, 'equity': 1_000_000,
                   'positions': {'600519.SH': {'shares': 300,
                                               'avg_price': 1600.0}}},
        market_context={},
        default_pool=['600519.SH'],
    )
    user = msgs[1].content
    assert '600519.SH' in user
    assert '300' in user


def test_prompt_hash_stable_for_same_inputs():
    from agents.prompt_builder import build_messages, prompt_hash
    args = dict(
        system_prompt='X', date='2024-03-15',
        portfolio={'cash': 1, 'equity': 1, 'positions': {}},
        market_context={}, default_pool=['X.SH'],
    )
    h1 = prompt_hash(build_messages(**args))
    h2 = prompt_hash(build_messages(**args))
    assert h1 == h2


def test_prompt_hash_differs_for_different_dates():
    from agents.prompt_builder import build_messages, prompt_hash
    base = dict(
        system_prompt='X',
        portfolio={'cash': 1, 'equity': 1, 'positions': {}},
        market_context={}, default_pool=['X.SH'],
    )
    h1 = prompt_hash(build_messages(date='2024-03-15', **base))
    h2 = prompt_hash(build_messages(date='2024-03-16', **base))
    assert h1 != h2
