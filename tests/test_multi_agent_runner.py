"""Multi-agent parallel runner — linear-ish speedup vs serial."""
import time
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
        (SQLiteRedLineStore, 'set_redline'),
        (SQLiteStockStatusStore, 'set_stock_status'),
        (SQLiteAuditStore, 'set_audit'),
        (SQLiteLLMDecisionCache, 'set_llm_cache'),
        (SQLitePersonaStore, 'set_personas'),
        (SQLiteAgentStore, 'set_agents'),
        (SQLitePromptVersionStore, 'set_prompt_versions'),
        (SQLiteModelStore, 'set_models'),
        (SQLiteBacktestResultStore, 'set_backtests'),
        (SQLiteCalendarStore, 'set_calendar'),
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


class _SlowMockLLM:
    """MockLLM-like, but each chat() sleeps 100ms to simulate API latency."""

    provider = 'slow-mock'
    model_id = 'slow-mock'

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self._idx = 0
        self.calls = []

    def chat(self, messages, tools=None, cacheable_prefix_len=0,
             temperature=0.0, max_tokens=2000):
        time.sleep(0.1)
        self.calls.append({'messages': list(messages),
                           'tools': list(tools) if tools else []})
        from llm.base import LLMResponse, ToolCall, Usage, Message
        spec = self._scripted[self._idx]
        self._idx += 1
        return LLMResponse(
            messages=[Message(role='assistant', content=spec.get('text', ''))]
            if spec.get('text') else [],
            tool_calls=[ToolCall(id=t['id'], name=t['name'], input=t['input'])
                        for t in spec.get('tool_calls', [])],
            stop_reason=spec.get('stop_reason', 'end_turn'),
            usage=Usage(input_tokens=1, output_tokens=1),
        )


def test_multi_agent_runs_parallel(wired_full, monkeypatch):
    """3 agents with slow-mock LLM should finish in ~max(single), not 3× single."""
    import backtest.multi_agent_runner as mod
    import backtest.runner as runner_mod

    agent_ids = []
    # Migrated 2026-04-24: linyuan/buffet → quant_neutral/intraday_t0 (3 distinct personas to test parallelism)
    for persona in ['quant_neutral', 'intraday_t0', 'fuyou']:
        a = wired_full.agents().create_from_persona(
            persona_id=persona, model_id='claude-opus-4-7',
            display_name=f'Par-{persona}',
        )
        agent_ids.append(a.id)

    days = [date(2025, 3, 1) + timedelta(days=i) for i in range(3)]
    prices = [(d, 100.0) for d in days]
    monkeypatch.setattr(runner_mod, '_load_daily_closes',
                        lambda c, s, e: prices)
    monkeypatch.setattr(runner_mod, '_trading_days', lambda s, e: days)

    # Stub context_builder so agents don't hit real sqlite
    import agents.context_builder as cb
    monkeypatch.setattr(cb, 'build_market_snapshot',
                        lambda u, d: {'date': d.strftime('%Y-%m-%d'),
                                      'stocks': {}})

    hold = {'tool_calls': [{'id': 'c', 'name': 'place_decision',
                            'input': {'action': 'hold',
                                      'reason': 'holding across all agents',
                                      'thinking': 't'}}],
            'stop_reason': 'tool_use'}

    def make_llm():
        return _SlowMockLLM([hold] * 3)

    configs = [{'agent_id': aid, 'llm': make_llm()} for aid in agent_ids]

    t0 = time.time()
    results = mod.run_multi(
        session_id='multi-par', agent_configs=configs,
        start_date='2025-03-01', end_date='2025-03-03',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )
    elapsed = time.time() - t0

    assert len(results) == 3
    assert {r.agent_id for r in results} == set(agent_ids)
    # Serial: 3 agents × 3 days × 100ms = 900ms. Parallel: ~300ms + overhead.
    assert elapsed < 0.7, f'expected parallel, took {elapsed:.2f}s'


def test_multi_agent_results_isolated(wired_full, monkeypatch):
    """Each agent's decisions land on its OWN BacktestResult row."""
    import backtest.multi_agent_runner as mod
    import backtest.runner as runner_mod
    import agents.context_builder as cb
    from llm.mock import MockLLM

    # Migrated 2026-04-24: linyuan/buffet → quant_neutral/soros (two distinct personas)
    a = wired_full.agents().create_from_persona(
        persona_id='quant_neutral', model_id='claude-opus-4-7',
        display_name='IsoA',
    )
    b = wired_full.agents().create_from_persona(
        persona_id='soros', model_id='claude-opus-4-7',
        display_name='IsoB',
    )

    days = [date(2025, 3, 1) + timedelta(days=i) for i in range(2)]
    prices = [(d, 100.0) for d in days]
    monkeypatch.setattr(runner_mod, '_load_daily_closes',
                        lambda c, s, e: prices)
    monkeypatch.setattr(runner_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(cb, 'build_market_snapshot',
                        lambda u, d: {'date': d.strftime('%Y-%m-%d'),
                                      'stocks': {}})

    buy = {'tool_calls': [{'id': 'c', 'name': 'place_decision',
                           'input': {'action': 'buy', 'code': '600519.SH',
                                     'qty': 100,
                                     'reason': 'agent A buys on day 1 firmly',
                                     'thinking': 't'}}],
           'stop_reason': 'tool_use'}
    hold = {'tool_calls': [{'id': 'c', 'name': 'place_decision',
                            'input': {'action': 'hold',
                                      'reason': 'agent B holds cash no action',
                                      'thinking': 't'}}],
            'stop_reason': 'tool_use'}
    llm_a = MockLLM([buy, hold])
    llm_b = MockLLM([hold, hold])

    configs = [
        {'agent_id': a.id, 'llm': llm_a},
        {'agent_id': b.id, 'llm': llm_b},
    ]
    results = mod.run_multi(
        session_id='iso', agent_configs=configs,
        start_date='2025-03-01', end_date='2025-03-02',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )
    by_agent = {r.agent_id: r for r in results}
    assert by_agent[a.id].stats.trade_count == 1
    assert by_agent[b.id].stats.trade_count == 0
