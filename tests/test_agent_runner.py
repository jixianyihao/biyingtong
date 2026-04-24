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


def test_run_day_accepts_market_snapshot(wired, seeded_agent):
    from agents.runner import AgentRunner
    from llm.mock import MockLLM
    llm = MockLLM([{
        'tool_calls': [{'id': 'c', 'name': 'place_decision',
                        'input': {'action': 'hold',
                                  'reason': 'saw the snapshot, staying put for today',
                                  'thinking': 't'}}],
        'stop_reason': 'tool_use',
    }])
    runner = AgentRunner(llm=llm)
    snap = {'date': '2025-11-17',
            'stocks': {'600519.SH': {'kline_summary': {'latest_close': 1600.0}}}}
    runner.run_day(
        agent_id=seeded_agent.id, date='2025-11-17',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 1600.0},
        market_snapshot=snap,
    )
    # The snapshot must end up in the prompt the LLM sees
    first_call = llm.calls[0]
    user_msg = [m for m in first_call['messages'] if m.role == 'user'][0]
    assert '1600' in user_msg.content


def test_run_day_honors_agent_current_prompt_version_id(wired, seeded_agent):
    """agents/runner.py must resolve system_prompt via agent.current_prompt_version_id.

    Regression guard for the 'current_prompt_version_id 指针失效' bug: the runner
    used storage.prompt_versions().get_latest() which silently defeats rollback
    and any path that inserts a version without also pinning it (or pins to a
    non-latest version).

    Setup: agent is seeded with v1 (persona default). Insert a v2 via store
    WITHOUT updating agents.current_prompt_version_id — now latest=v2, pin=v1.
    The LLM prompt must contain v1's content, not v2's.
    """
    import storage
    from agents.runner import AgentRunner
    from llm.mock import MockLLM

    pinned_marker = 'PINNED_V1_MARKER_9f2c'
    latest_marker = 'LATEST_V2_MARKER_4a7b'
    # Overwrite v1 in place by inserting v2 with a detectable marker,
    # but first pin v1 so current != latest after the v2 insert.
    v1 = storage.prompt_versions().get_latest(seeded_agent.id)
    assert v1 is not None
    # Replace v1's body with the pinned_marker via rollback semantics:
    # simplest approach is to insert a NEW v_pinned and point current_prompt_version_id there.
    v_pinned = storage.prompt_versions().insert(
        agent_id=seeded_agent.id,
        system_prompt=f'You are a test agent. {pinned_marker}',
        note='test pinned version',
    )
    storage.agents().set_current_prompt_version(seeded_agent.id, v_pinned.id)
    # Now insert a LATER version but do NOT pin it. Pin stays at v_pinned.
    storage.prompt_versions().insert(
        agent_id=seeded_agent.id,
        system_prompt=f'You are a test agent. {latest_marker}',
        note='unpinned latest — runner must NOT use this',
    )

    llm = MockLLM([{
        'tool_calls': [{'id': 'c', 'name': 'place_decision',
                        'input': {'action': 'hold',
                                  'reason': 'staying put for the regression test',
                                  'thinking': 't'}}],
        'stop_reason': 'tool_use',
    }])
    runner = AgentRunner(llm=llm)
    runner.run_day(
        agent_id=seeded_agent.id, date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 100.0},
    )
    first_call = llm.calls[0]
    system_msgs = [m for m in first_call['messages'] if m.role == 'system']
    assert system_msgs, 'expected at least one system message'
    system_text = '\n'.join(m.content for m in system_msgs)
    assert pinned_marker in system_text, (
        f"system prompt should contain pinned marker but did not. "
        f"System text: {system_text[:200]!r}"
    )
    assert latest_marker not in system_text, (
        f"system prompt contains the UNPINNED latest marker — "
        f"runner is using get_latest() instead of current_prompt_version_id."
    )


def test_agent_rules_override_reaches_validation(wired, seeded_agent):
    """agents/runner.py must pass agent.rules_override to ValidationEngine.validate().

    Regression guard for the 'rules_override 断链' bug: prior to fix, per-agent
    rules were silently dropped and every agent ran under the global RedLine,
    defeating persona-level 风控 differentiation.

    Setup: global RedLine position_max_pct=15% (set in fixture). Override this
    specific agent to 5%. A buy of 1000 shares @ 237 = 237k (23.7% of 1M equity)
    must shrink based on the TIGHTER 5% cap, not the 15% global.
    """
    import storage
    from agents.runner import AgentRunner
    storage.agents().update(
        seeded_agent.id, rules_override={'position_max_pct': 5.0},
    )
    llm = _mock_llm_with_decision(code='600519.SH', shares=1000, price=237.0)
    runner = AgentRunner(llm=llm)
    out = runner.run_day(
        agent_id=seeded_agent.id, date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 237.0},
    )
    # 5% cap → 50k → 50_000 / 237 ≈ 210.97 → lot-round down to 200 shares.
    # Without the fix (15% global applied), result would be 600 shares.
    assert len(out) == 1
    assert out[0]['shares'] == 200, (
        f"Expected 200 shares (5% override applied) but got {out[0]['shares']}. "
        f"Got 600 means rules_override wasn't passed to validate()."
    )
