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


def test_market_snapshot_renders_in_user_message():
    from agents.prompt_builder import build_messages
    snap = {
        'date': '2025-11-17',
        'stocks': {
            '600519.SH': {
                'kline_summary': {
                    'latest_close': 1600.0,
                    'return_30d_pct': 2.5,
                    'volatility_30d_pct': 1.8,
                    'closes_last_30d': [1600, 1590, 1580],
                },
                'financials': {'pe': 25.0, 'roe': 30.0},
                'technical': {'ma20': 1580.0, 'rsi14': 58.0},
                'capital_flow': {'GP1': 123.4, 'GP2': 456.7},
            },
        },
    }
    msgs = build_messages(
        system_prompt='x', date='2025-11-17',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, default_pool=['600519.SH'],
        market_snapshot=snap,
    )
    user = msgs[1].content
    assert '1600' in user or '1,600' in user
    assert 'pe' in user.lower()
    assert 'roe' in user.lower()
    assert 'CapitalFlow' in user
    assert 'GP1=123.4' in user


def test_short_term_snapshot_still_allows_capital_flow_tools():
    from agents.prompt_builder import build_messages
    snap = {
        'date': '2025-11-17',
        'stocks': {
            '300059.SZ': {
                'kline_summary': {'latest_close': 20.0},
                'financials': None,
                'technical': None,
                'capital_flow': None,
            },
        },
    }
    msgs = build_messages(
        system_prompt='x', date='2025-11-17',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, default_pool=['300059.SZ'],
        market_snapshot=snap,
        allowed_tools=['get_stock_list', 'get_capital_flow', 'place_decision'],
    )
    user = msgs[1].content
    assert 'SHORT-TERM RESEARCH OVERRIDE' in user
    assert 'get_capital_flow' in user
    assert 'use the available tools first' in user


def test_no_snapshot_keeps_old_behavior():
    from agents.prompt_builder import build_messages
    msgs = build_messages(
        system_prompt='x', date='2025-11-17',
        portfolio={'cash': 1, 'equity': 1, 'positions': {}},
        market_context={}, default_pool=['X.SH'],
    )
    user = msgs[1].content
    assert 'latest_close' not in user
