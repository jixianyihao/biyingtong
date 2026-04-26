"""P2d E2E — agent + baselines + rating."""
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
    from storage.sqlite_baselines import SQLiteBaselineResultStore
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
        (SQLiteBaselineResultStore, 'set_baselines'),
        (SQLiteCalendarStore,       'set_calendar'),
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


def test_e2e_agent_plus_baselines_plus_rating(wired_full, monkeypatch):
    import storage
    from backtest.runner import BacktestRunner
    from backtest.baselines.runner import run_all
    from agents.rating import compute_health, classify_rating
    from llm.mock import MockLLM

    agent = wired_full.agents().create_from_persona(
        persona_id='quant_neutral', model_id='claude-opus-4-7',
        display_name='E2E',
    )

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    stock_prices = [(d, 100.0 + i * 0.5) for i, d in enumerate(days)]
    index_prices = [(d, 1000.0 + i) for i, d in enumerate(days)]

    import backtest.runner as run_mod
    import backtest.baselines.buy_and_hold as bh_mod
    import backtest.baselines.equal_weight as ew_mod
    import backtest.baselines.csi300 as csi_mod
    monkeypatch.setattr(run_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(run_mod, '_load_daily_closes', lambda c, s, e: stock_prices)
    monkeypatch.setattr(bh_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(bh_mod, '_load_prices', lambda c, s, e: stock_prices)
    monkeypatch.setattr(ew_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(ew_mod, '_load_prices', lambda c, s, e: stock_prices)
    monkeypatch.setattr(csi_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(csi_mod, '_load_index_series', lambda s, e: index_prices)

    hold = {'tool_calls': [{'id': 'c', 'name': 'place_decision',
                            'input': {'action': 'hold',
                                      'reason': 'nothing to trade today',
                                      'thinking': 't'}}],
            'stop_reason': 'tool_use'}
    llm = MockLLM([hold] * 5)
    agent_result = BacktestRunner(llm=llm).run(
        session_id='e2e-p2d', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )

    baselines = run_all(
        session_id='e2e-p2d',
        start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )

    # Assert 1: all 3 baselines persisted under the session
    assert len(storage.baselines().list_for_session('e2e-p2d')) == 3

    # Assert 2: agent backtest persisted
    assert storage.backtests().get(agent_result.id) is not None

    # Assert 3: health + rating computed and persisted
    health = compute_health(agent.id)
    rating = classify_rating(health)
    storage.agents().update_health(agent.id, health=health, rating=rating)

    reloaded = storage.agents().get(agent.id)
    assert reloaded.health_score == health
    assert reloaded.trust_rating == rating
