"""Run two personas on the same window; compare results via session_id."""
from datetime import date, timedelta
import pytest


@pytest.fixture
def wired_full(tmp_path):
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.sqlite_audit import SQLiteAuditStore
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    from storage.sqlite_personas import SQLitePersonaStore
    from storage.sqlite_agents import SQLiteAgentStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    from storage.sqlite_models import SQLiteModelStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_calendar import SQLiteCalendarStore
    from validation.base import DEFAULT_REDLINES

    for cls, setter in [
        (SQLiteRedLineStore,        'set_redline'),
        (SQLiteStockStatusStore,    'set_stock_status'),
        (SQLiteAuditStore,          'set_audit'),
        (SQLiteLLMDecisionCache,    'set_llm_cache'),
        (SQLitePersonaStore,        'set_personas'),
        (SQLiteAgentStore,          'set_agents'),
        (SQLitePromptVersionStore,  'set_prompt_versions'),
        (SQLiteModelStore,          'set_models'),
        (SQLiteBacktestResultStore, 'set_backtests'),
        (SQLiteCalendarStore,       'set_calendar'),
    ]:
        inst = cls(tmp_path=tmp_path)
        inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()

    from validation import rules
    rules.reset()
    from validation.handlers.position_max_pct import Handler as H1
    from validation.handlers.ban_st import Handler as H2
    from validation.handlers.max_holdings import Handler as H3
    from validation.handlers.daily_loss_limit_pct import Handler as H4
    rules.register(H1())
    rules.register(H2())
    rules.register(H3())
    rules.register(H4())

    storage.redline().set({**DEFAULT_REDLINES, 'position_max_pct': 15.0})
    from personas import seed as seed_personas
    seed_personas()
    return storage


def _run_one(agent_id, session_id, llm_script, days, prices, monkeypatch):
    from backtest.runner import BacktestRunner
    import backtest.runner as mod
    from llm.mock import MockLLM
    monkeypatch.setattr(mod, '_load_daily_closes', lambda c, s, e: prices)
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    return BacktestRunner(llm=MockLLM(llm_script)).run(
        session_id=session_id, agent_id=agent_id,
        start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )


def test_two_personas_same_session(wired_full, monkeypatch):
    """Two agents → two result rows with same session_id."""
    import storage
    agent_a = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='林园 · Claude',
    )
    agent_b = wired_full.agents().create_from_persona(
        persona_id='buffet', model_id='claude-opus-4-7',
        display_name='Buffet · Claude',
    )

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    # Use price 100 so 100-share buy = 10k (under 15% cap)
    prices = [(d, 100.0 + 0.5 * i) for i, d in enumerate(days)]

    buy = {'tool_calls': [{'id': 'c', 'name': 'place_decision',
           'input': {'action': 'buy', 'code': '600519.SH', 'qty': 100,
                     'reason': 'fundamental value with reasonable entry',
                     'thinking': 't'}}],
           'stop_reason': 'tool_use'}
    hold = {'tool_calls': [{'id': 'c', 'name': 'place_decision',
            'input': {'action': 'hold',
                      'reason': 'positioned correctly, staying put',
                      'thinking': 't'}}],
            'stop_reason': 'tool_use'}

    _run_one(agent_a.id, 'multi-1', [buy] + [hold] * 4, days, prices, monkeypatch)
    _run_one(agent_b.id, 'multi-1', [hold] * 5, days, prices, monkeypatch)

    rows = storage.backtests().list_for_session('multi-1')
    assert len(rows) == 2
    agents = {r.agent_id for r in rows}
    assert agents == {agent_a.id, agent_b.id}

    # Linyuan bought at day 1, Buffet never traded — their final_equity differs.
    by_agent = {r.agent_id: r for r in rows}
    assert by_agent[agent_a.id].stats.trade_count == 1
    assert by_agent[agent_b.id].stats.trade_count == 0
    assert by_agent[agent_a.id].final_equity != by_agent[agent_b.id].final_equity
