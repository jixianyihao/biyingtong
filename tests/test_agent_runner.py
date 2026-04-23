"""AgentRunner tool loop + cache + validation integration."""
import pytest


@pytest.fixture
def wired(tmp_path):
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

    for store_cls, setter in [
        (SQLiteRedLineStore, 'set_redline'),
        (SQLiteStockStatusStore, 'set_stock_status'),
        (SQLiteAuditStore, 'set_audit'),
        (SQLiteLLMDecisionCache, 'set_llm_cache'),
        (SQLitePersonaStore, 'set_personas'),
        (SQLiteAgentStore, 'set_agents'),
        (SQLitePromptVersionStore, 'set_prompt_versions'),
        (SQLiteModelStore, 'set_models'),
    ]:
        inst = store_cls(tmp_path=tmp_path)
        inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()

    from validation import rules
    rules.reset()
    # Re-register every handler after reset.  A bare `import validation.handlers`
    # is a no-op on the 2nd+ test (Python import cache), so we instantiate each
    # Handler class directly — the same pattern used in test_validation_engine.py.
    from validation.handlers.position_max_pct import Handler as _PositionMaxPctHandler
    from validation.handlers.ban_st import Handler as _BanStHandler
    from validation.handlers.max_holdings import Handler as _MaxHoldingsHandler
    from validation.handlers.daily_loss_limit_pct import Handler as _DailyLossLimitPctHandler
    rules.register(_PositionMaxPctHandler())
    rules.register(_BanStHandler())
    rules.register(_MaxHoldingsHandler())
    rules.register(_DailyLossLimitPctHandler())

    storage.redline().set({**DEFAULT_REDLINES, 'position_max_pct': 15.0})
    return storage


@pytest.fixture
def seeded_agent(wired):
    from personas import seed as seed_personas
    seed_personas()
    agent = wired.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='TestAgent',
    )
    return agent


def _mock_llm_with_decision(code='600519.SH', shares=100, price=None):
    from llm.mock import MockLLM
    inp = {
        'action': 'buy', 'code': code, 'qty': shares,
        'reason': 'fundamentals strong, valuation reasonable today',
        'thinking': 'analysis details',
    }
    if price is not None:
        inp['price'] = price
    return MockLLM([{
        'tool_calls': [{'id': 'call_1', 'name': 'place_decision', 'input': inp}],
        'stop_reason': 'tool_use',
    }])


def test_first_run_calls_llm_and_caches(wired, seeded_agent):
    from agents.runner import AgentRunner
    llm = _mock_llm_with_decision()
    runner = AgentRunner(llm=llm)
    out = runner.run_day(
        agent_id=seeded_agent.id,
        date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={},
        mark_prices={'600519.SH': 100.0},
    )
    assert len(llm.calls) == 1
    assert len(out) == 1
    assert out[0]['action'] == 'buy'
    assert out[0]['code'] == '600519.SH'


def test_rerun_uses_cache_no_new_llm_call(wired, seeded_agent):
    from agents.runner import AgentRunner
    llm = _mock_llm_with_decision()
    runner = AgentRunner(llm=llm)
    common_args = dict(
        agent_id=seeded_agent.id, date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 100.0},
    )
    runner.run_day(**common_args)
    assert len(llm.calls) == 1
    runner.run_day(**common_args)
    assert len(llm.calls) == 1  # no new call, cache hit


def test_rejected_decision_is_not_in_output(wired, seeded_agent):
    """ValidationEngine rejects; runner returns empty list + audit row exists."""
    from storage.base import StockStatusRow
    import storage
    from agents.runner import AgentRunner
    storage.stock_status().upsert(StockStatusRow(
        code='ST.SH', name='*ST X', is_st=True,
        is_suspended=False, is_delisted=False,
    ))
    llm = _mock_llm_with_decision(code='ST.SH', shares=100, price=10.0)
    runner = AgentRunner(llm=llm)
    out = runner.run_day(
        agent_id=seeded_agent.id, date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'ST.SH': 10.0},
    )
    assert out == []
    rows = storage.audit().query_by_agent(seeded_agent.id)
    assert len(rows) >= 1
    assert rows[0]['details']['outcome'] == 'rejected'


def test_modified_decision_reflects_shrunk_shares(wired, seeded_agent):
    """Buy 1000 shares that exceeds 15% cap → shrunk to 600 (rounded to lot).

    The LLM explicitly includes price=237 in the decision so position_max_pct
    handler can compute the post-trade value and shrink shares accordingly.
    """
    from agents.runner import AgentRunner
    # 1000 shares × 237 = 237k > 150k cap → shrink to 632 → lot-round to 600
    llm = _mock_llm_with_decision(code='600519.SH', shares=1000, price=237.0)
    runner = AgentRunner(llm=llm)
    out = runner.run_day(
        agent_id=seeded_agent.id, date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 237.0},
    )
    assert len(out) == 1
    assert out[0]['shares'] == 600
