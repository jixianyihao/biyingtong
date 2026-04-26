"""AgentRunner invokes non-terminator tools for real (not ack stubs)."""
import json
import pytest


@pytest.fixture
def wired(tmp_path):
    """Minimal wiring for agent runner: stores + handler registry + one agent."""
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.sqlite_audit import SQLiteAuditStore
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    from storage.sqlite_personas import SQLitePersonaStore
    from storage.sqlite_agents import SQLiteAgentStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    from storage.sqlite_models import SQLiteModelStore
    from validation.base import DEFAULT_REDLINES

    for cls, setter in [
        (SQLiteRedLineStore, 'set_redline'),
        (SQLiteStockStatusStore, 'set_stock_status'),
        (SQLiteAuditStore, 'set_audit'),
        (SQLiteLLMDecisionCache, 'set_llm_cache'),
        (SQLitePersonaStore, 'set_personas'),
        (SQLiteAgentStore, 'set_agents'),
        (SQLitePromptVersionStore, 'set_prompt_versions'),
        (SQLiteModelStore, 'set_models'),
    ]:
        inst = cls(tmp_path=tmp_path); inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()

    from validation import rules
    rules.reset()
    from validation.handlers.position_max_pct import Handler as H1
    from validation.handlers.ban_st import Handler as H2
    from validation.handlers.max_holdings import Handler as H3
    from validation.handlers.daily_loss_limit_pct import Handler as H4
    rules.register(H1()); rules.register(H2())
    rules.register(H3()); rules.register(H4())

    storage.redline().set({**DEFAULT_REDLINES, 'position_max_pct': 15.0})
    from personas import seed as seed_personas
    seed_personas()
    return storage


def test_non_terminator_tool_is_executed(wired, monkeypatch):
    """When LLM calls get_kline, AgentRunner should invoke the real tool
    and return its result — not a {'ack': true} stub."""
    from agents.runner import AgentRunner
    from llm.mock import MockLLM

    agent = wired.agents().create_from_persona(
        persona_id='quant_neutral', model_id='claude-opus-4-7',
        display_name='Tool-Exec-Test',
    )

    # Monkeypatch the tool's call function so we don't need real kline data
    from tools import get_kline as gk_mod
    captured_input = {}
    def fake_call(inp):
        captured_input.update(inp)
        return {'code': inp.get('code'), 'bars': [{'date': '2025-11-17',
                                                    'close': 123.45}]}
    monkeypatch.setattr(gk_mod, 'call', fake_call)

    # Script: LLM first calls get_kline, then place_decision after seeing result
    llm = MockLLM([
        {'tool_calls': [{'id': 'tk1', 'name': 'get_kline',
                         'input': {'code': '600519.SH', 'period': '1d',
                                   'count': 5}}],
         'stop_reason': 'tool_use'},
        {'tool_calls': [{'id': 'pd1', 'name': 'place_decision',
                         'input': {'action': 'hold',
                                   'reason': 'price looks reasonable based on recent bars',
                                   'thinking': 'saw close 123.45'}}],
         'stop_reason': 'tool_use'},
    ])

    runner = AgentRunner(llm=llm)
    decisions = runner.run_day(
        agent_id=agent.id, date='2025-11-17',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 1600.0},
    )

    # Assert 1: the real tool's call() was invoked (not stubbed)
    assert captured_input == {'code': '600519.SH', 'period': '1d', 'count': 5}

    # Assert 2: place_decision's hold decision was recorded
    assert len(decisions) == 1
    assert decisions[0]['action'] == 'hold'

    # Assert 3: the LLM got a REAL tool result in its convo
    assert len(llm.calls) == 2
    second_call_messages = llm.calls[1]['messages']
    # Last message should be the user/tool_result turn
    last = second_call_messages[-1]
    assert last.role == 'user'
    assert isinstance(last.content, list)
    tool_result_block = last.content[0]
    assert tool_result_block['type'] == 'tool_result'
    assert tool_result_block['tool_use_id'] == 'tk1'
    # tool_result.content should be JSON-serialized real tool output
    parsed = json.loads(tool_result_block['content'])
    assert parsed['code'] == '600519.SH'
    assert parsed['bars'][0]['close'] == 123.45


def test_tool_exception_becomes_error_tool_result(wired, monkeypatch):
    """If a tool raises, surface the error in tool_result content instead
    of crashing the whole run_day."""
    from agents.runner import AgentRunner
    from llm.mock import MockLLM

    agent = wired.agents().create_from_persona(
        persona_id='quant_neutral', model_id='claude-opus-4-7',
        display_name='Tool-Error-Test',
    )

    from tools import get_kline as gk_mod
    def boom(_inp):
        raise RuntimeError('tqcenter offline')
    monkeypatch.setattr(gk_mod, 'call', boom)

    llm = MockLLM([
        {'tool_calls': [{'id': 'tk1', 'name': 'get_kline',
                         'input': {'code': 'X.SH', 'period': '1d',
                                   'count': 5}}],
         'stop_reason': 'tool_use'},
        {'tool_calls': [{'id': 'pd1', 'name': 'place_decision',
                         'input': {'action': 'hold',
                                   'reason': 'kline unavailable, standing pat for today',
                                   'thinking': 'no data'}}],
         'stop_reason': 'tool_use'},
    ])

    runner = AgentRunner(llm=llm)
    decisions = runner.run_day(
        agent_id=agent.id, date='2025-11-17',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'X.SH': 10.0},
    )

    # Runner should survive; LLM sees the error as tool_result with is_error marker
    assert len(decisions) == 1
    last = llm.calls[1]['messages'][-1]
    block = last.content[0]
    assert block['type'] == 'tool_result'
    assert block.get('is_error') is True
    assert 'tqcenter offline' in block['content']
