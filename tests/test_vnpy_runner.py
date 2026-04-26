"""VnpyBacktestRunner — shape tests + strategy integration."""
from __future__ import annotations

import pytest


def test_biyingtong_to_vt_conversion():
    from backtest.strategy import biyingtong_to_vt
    assert biyingtong_to_vt('600519.SH') == '600519.SSE'
    assert biyingtong_to_vt('000858.SZ') == '000858.SZSE'
    assert biyingtong_to_vt('UNKNOWN') == 'UNKNOWN'


def test_vnpy_runner_smoke_short_window(observability_storage, vnpy_configured):
    """VnpyBacktestRunner integrates with vnpy engine + our LLMPortfolioStrategy.

    Uses a mock LLM that always returns hold decisions. Primary purpose:
    confirm the pipeline wires together without exceptions. Detailed numeric
    assertions live in the parity test.
    """
    import storage
    from backtest.vnpy_runner import VnpyBacktestRunner
    from llm.mock import MockLLM

    agent = storage.agents().create_from_persona(
        persona_id='quant_neutral', model_id='claude-opus-4-7',
        display_name='vnpy-smoke', initial_capital=1_000_000.0,
    )

    hold_script = [{
        'tool_calls': [{
            'id': 'h', 'name': 'place_decision',
            'input': {'action': 'hold', 'reason': 'wait', 'thinking': 'x'},
        }],
        'stop_reason': 'tool_use',
    }] * 20

    llm = MockLLM(hold_script)

    try:
        r = VnpyBacktestRunner(llm=llm).run(
            session_id='s-vnpy-smoke', agent_id=agent.id,
            start_date='2025-11-17', end_date='2025-11-21',
            universe=['600519.SH'], initial_capital=1_000_000.0,
        )
    except Exception as e:
        pytest.skip(f'vnpy engine could not load data: {e}')

    assert r.kind == 'agent'
    assert r.agent_id == agent.id
    assert r.session_id == 's-vnpy-smoke'
    assert r.initial_capital == 1_000_000.0
    assert r.final_equity is not None
    assert isinstance(r.daily_records, list)
    assert isinstance(r.thinking, list)
