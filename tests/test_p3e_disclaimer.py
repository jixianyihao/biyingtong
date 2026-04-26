"""P3-E in-prompt disclaimer (spec §11.5)."""
from __future__ import annotations


def test_build_messages_appends_disclaimer_when_cutoff_provided():
    from agents.prompt_builder import build_messages
    msgs = build_messages(
        system_prompt='You are a value investor.',
        date='2026-04-23',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={},
        default_pool=['600519.SH'],
        model_cutoff='2025-04-01',
    )
    sys = msgs[0]
    assert sys.role == 'system'
    # Original prompt preserved at top
    assert 'You are a value investor.' in sys.content
    # Disclaimer appended at end
    assert '2026-04-23' in sys.content
    assert '2025-04-01' in sys.content
    # Has the explicit "today" / "cutoff" framing
    assert '今天' in sys.content or 'today' in sys.content.lower()
    assert '截止' in sys.content or 'cutoff' in sys.content.lower()


def test_build_messages_no_disclaimer_when_cutoff_none():
    """Backward compatible: existing callers without cutoff get unchanged system message."""
    from agents.prompt_builder import build_messages
    msgs = build_messages(
        system_prompt='You are a value investor.',
        date='2026-04-23',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={},
        default_pool=['600519.SH'],
    )
    sys = msgs[0]
    assert sys.content == 'You are a value investor.'  # exact match — nothing appended


def test_build_messages_disclaimer_after_decision_date():
    """Cutoff in the future relative to decision date → still emit disclaimer
    (spec doesn't condition on relative timing). LLM uses both pieces of context."""
    from agents.prompt_builder import build_messages
    msgs = build_messages(
        system_prompt='sys',
        date='2024-01-01',
        portfolio={'cash': 0, 'equity': 0, 'positions': {}},
        market_context={},
        default_pool=[],
        model_cutoff='2026-01-31',
    )
    assert '2024-01-01' in msgs[0].content
    assert '2026-01-31' in msgs[0].content


def test_agent_runner_passes_model_cutoff_to_build_messages(observability_storage):
    """run_day looks up model + forwards training_cutoff."""
    from unittest.mock import patch
    import storage
    from agents.runner import AgentRunner
    from llm.mock import MockLLM

    agent = storage.agents().create_from_persona(
        persona_id='quant_neutral', model_id='claude-opus-4-7',
        display_name='t-disc', initial_capital=1_000_000.0,
    )
    expected_cutoff = storage.models().get('claude-opus-4-7').training_cutoff

    captured = {}
    real_build = None
    from agents import prompt_builder as pb_mod
    real_build = pb_mod.build_messages

    def _spy(*args, **kwargs):
        captured.update(kwargs)
        return real_build(*args, **kwargs)

    script = [{
        'text': 'x',
        'tool_calls': [{
            'id': 'c1', 'name': 'place_decision',
            'input': {'action': 'hold', 'reason': 'x', 'thinking': 'x'},
        }],
        'stop_reason': 'tool_use',
    }]
    with patch('agents.runner.build_messages', side_effect=_spy):
        AgentRunner(llm=MockLLM(script)).run_day(
            agent_id=agent.id, date='2025-01-03',
            portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
            market_context={}, mark_prices={'600519.SH': 100.0},
        )
    assert captured.get('model_cutoff') == expected_cutoff
