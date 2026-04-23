"""P2c E2E — full pipeline smoke test with MockLLM."""
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


def test_e2e_full_pipeline(wired_full, monkeypatch):
    """Smoke: full pipeline end-to-end with buy + holds."""
    from backtest.runner import BacktestRunner
    import backtest.runner as mod
    from llm.mock import MockLLM

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='E2E',
    )

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    # Use price 100 so 100-share buy = 10k (well under 15% cap)
    prices = [(d, 100.0 * (1 + 0.003 * i)) for i, d in enumerate(days)]
    monkeypatch.setattr(mod, '_load_daily_closes',
                        lambda code, s, e: prices)
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)

    buy = {
        'tool_calls': [{'id': 'c1', 'name': 'place_decision',
                        'input': {'action': 'buy', 'code': '600519.SH',
                                  'qty': 100,
                                  'reason': 'value opportunity with solid fundamentals',
                                  'thinking': 'full thinking'}}],
        'stop_reason': 'tool_use',
    }
    hold = {
        'tool_calls': [{'id': 'c', 'name': 'place_decision',
                        'input': {'action': 'hold',
                                  'reason': 'thesis intact, prices reasonable',
                                  'thinking': 't'}}],
        'stop_reason': 'tool_use',
    }
    llm = MockLLM([buy, hold, hold, hold, hold])

    runner = BacktestRunner(llm=llm)
    result = runner.run(
        session_id='e2e-1', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )

    # Assert 1: stored in backtest_results
    import storage
    stored = storage.backtests().get(result.id)
    assert stored is not None
    assert stored.agent_id == agent.id

    # Assert 2: audit log has decision entries
    rows = storage.audit().query_by_agent(agent.id)
    assert len(rows) >= 1
    assert any(r['kind'] == 'validation' for r in rows)

    # Assert 3: quality gate label set
    assert result.quality_gate_label in ('pass', 'warn', 'fail')

    # Assert 4: buy happened
    assert result.stats.trade_count >= 1
    assert result.final_equity is not None


def test_e2e_rerun_uses_cache(wired_full, monkeypatch):
    """Re-running with same inputs uses cache, zero new LLM calls."""
    from backtest.runner import BacktestRunner
    import backtest.runner as mod
    from llm.mock import MockLLM

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='E2E-cache',
    )
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(3)]
    prices = [(d, 100.0) for d in days]
    monkeypatch.setattr(mod, '_load_daily_closes',
                        lambda c, s, e: prices)
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)

    hold = {
        'tool_calls': [{'id': 'c', 'name': 'place_decision',
                        'input': {'action': 'hold',
                                  'reason': 'no reason to trade at this valuation',
                                  'thinking': 't'}}],
        'stop_reason': 'tool_use',
    }
    llm_1 = MockLLM([hold, hold, hold])

    BacktestRunner(llm=llm_1).run(
        session_id='cache-a', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-03',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )
    assert len(llm_1.calls) == 3

    # Second run: fresh empty MockLLM. If cache works, it is never called.
    llm_2 = MockLLM([])
    BacktestRunner(llm=llm_2).run(
        session_id='cache-b', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-03',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )
    assert len(llm_2.calls) == 0


def test_zone_stats_split_across_cutoff(wired_full, monkeypatch):
    """Window straddling a model's training_cutoff must produce zone_stats."""
    from backtest.runner import BacktestRunner
    import backtest.runner as mod
    from llm.mock import MockLLM
    import storage

    # Override the model's cutoff mid-window.
    class _M:
        training_cutoff = '2024-03-10'
    monkeypatch.setattr(storage.models(), 'get', lambda _id: _M())

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='Zones',
    )

    # 30 days straddling 2024-03-10 with 60-day buffer → all days are
    # pollution (day<cutoff) or buffer (<cutoff+60d). None are clean.
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(30)]
    prices = [(d, 100.0) for d in days]
    monkeypatch.setattr(mod, '_load_daily_closes', lambda c, s, e: prices)
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)

    hold = {
        'tool_calls': [{'id': 'c', 'name': 'place_decision',
                        'input': {'action': 'hold',
                                  'reason': 'nothing to do, markets are stable today',
                                  'thinking': 't'}}],
        'stop_reason': 'tool_use',
    }
    llm = MockLLM([hold] * 30)
    result = BacktestRunner(llm=llm).run(
        session_id='zones', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-30',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )

    by_zone = {z.zone: z for z in result.zone_stats}
    assert by_zone['pollution'].days == 9   # 2024-03-01..2024-03-09
    assert by_zone['buffer'].days == 21     # 2024-03-10..2024-03-30
    assert by_zone['clean'].days == 0
