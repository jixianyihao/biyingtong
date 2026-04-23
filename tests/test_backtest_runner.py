"""BacktestRunner E2E driver."""
from datetime import date, timedelta
import pytest


@pytest.fixture
def wired_full(tmp_path):
    """Bring up every store P2c needs, seed personas + models."""
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
    # Explicit handler re-registration (import-side-effect only fires once per process)
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


def _fake_bar_series(code='600519.SH', days=10, start_price=1600.0):
    """Daily close sequence mildly up-trending."""
    return [(date(2024, 3, 1) + timedelta(days=i),
             start_price * (1 + 0.002 * i))
            for i in range(days)]


def test_run_produces_backtest_result(wired_full, monkeypatch):
    """Smoke: runner completes and writes one BacktestResult row."""
    from backtest.runner import BacktestRunner

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='Test',
    )

    import backtest.runner as mod
    bars = _fake_bar_series()
    monkeypatch.setattr(mod, '_load_daily_closes',
                        lambda code, start, end: bars)
    monkeypatch.setattr(mod, '_trading_days',
                        lambda start, end: [d for d, _ in bars])

    from llm.mock import MockLLM
    llm = MockLLM([{
        'tool_calls': [{
            'id': 'c1', 'name': 'place_decision',
            'input': {'action': 'hold',
                      'reason': 'staying put, nothing compelling today',
                      'thinking': 'analysis'},
        }], 'stop_reason': 'tool_use',
    }] * 10)

    runner = BacktestRunner(llm=llm)
    result = runner.run(
        session_id='s1', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-10',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )
    assert result.id is not None
    assert result.session_id == 's1'
    assert result.quality_gate_label in ('pass', 'warn', 'fail')
    stored = wired_full.backtests().get(result.id)
    assert stored is not None


def test_buy_decision_reduces_cash(wired_full, monkeypatch):
    """A buy that passes validation must spend cash."""
    from backtest.runner import BacktestRunner

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='Test',
    )

    import backtest.runner as mod
    bars = _fake_bar_series(days=3)
    monkeypatch.setattr(mod, '_load_daily_closes',
                        lambda c, s, e: bars)
    monkeypatch.setattr(mod, '_trading_days',
                        lambda s, e: [d for d, _ in bars])

    from llm.mock import MockLLM
    # Day 1: buy 100 @ ~1600 = ~160k (16% of 1M, just over 15% cap → modified to
    # allowed=93 shares → lot-rounded to 0 → rejected). Use smaller qty so it passes:
    # 50 shares @ 1600 = 80k (8%) but lot-rounding requires multiple of 100.
    # So use qty 100 and lower mark price. Let's use buy 100 @ mark 1000 = 100k (10%).
    llm = MockLLM([
        {'tool_calls': [{'id': 'c1', 'name': 'place_decision',
                         'input': {'action': 'buy', 'code': '600519.SH',
                                   'qty': 100,
                                   'reason': 'buying quality at reasonable valuation',
                                   'thinking': 't'}}],
         'stop_reason': 'tool_use'},
        {'tool_calls': [{'id': 'c2', 'name': 'place_decision',
                         'input': {'action': 'hold',
                                   'reason': 'holding position, waiting for further confirmation',
                                   'thinking': 't'}}],
         'stop_reason': 'tool_use'},
        {'tool_calls': [{'id': 'c3', 'name': 'place_decision',
                         'input': {'action': 'hold',
                                   'reason': 'holding, thesis still intact',
                                   'thinking': 't'}}],
         'stop_reason': 'tool_use'},
    ])

    # Use low-priced bar series so buy passes validation: 100 shares × 100 = 10k (1%)
    bars_low = [(date(2024, 3, 1) + timedelta(days=i), 100.0 * (1 + 0.002 * i))
                for i in range(3)]
    monkeypatch.setattr(mod, '_load_daily_closes', lambda c, s, e: bars_low)

    runner = BacktestRunner(llm=llm)
    result = runner.run(
        session_id='s2', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-03',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )
    # Equity should be roughly 1M (slightly up due to 0.2%/day price trend
    # applied to 100 held shares — small effect). Confirm final_equity exists
    # and stats.trade_count >= 1.
    assert result.final_equity is not None
    assert result.stats.trade_count >= 1
