"""P3-D SSE fine-grained events — Event shape, emitter, runner hooks."""
from __future__ import annotations

import pytest


def test_job_status_has_events_list():
    from backtest.jobs import JobStatus
    s = JobStatus(session_id='s1')
    assert hasattr(s, 'events')
    assert s.events == []


def test_emit_event_appends_to_status():
    from backtest.jobs import JobStatus, emit_event
    s = JobStatus(session_id='s1')
    emit_event(s, {'kind': 'phase', 'phase': 'running'})
    assert len(s.events) == 1
    e = s.events[0]
    assert e['kind'] == 'phase'
    assert e['phase'] == 'running'
    assert 'ts' in e


def test_emit_event_preserves_explicit_ts():
    from backtest.jobs import JobStatus, emit_event
    s = JobStatus(session_id='s1')
    emit_event(s, {'kind': 'progress', 'ts': 12345.67, 'date': '2025-01-02'})
    assert s.events[0]['ts'] == 12345.67


def test_agent_runner_emits_decision_event(observability_storage):
    from agents.runner import AgentRunner
    from llm.mock import MockLLM
    import storage

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-evt', initial_capital=1_000_000.0,
    )
    script = [{
        'text': 'decision',
        'tool_calls': [{
            'id': 'c1', 'name': 'place_decision',
            'input': {'action': 'buy', 'code': '600519.SH', 'qty': 100,
                      'reason': 'test', 'thinking': 'buy'},
        }],
        'stop_reason': 'tool_use',
    }]
    events = []
    runner = AgentRunner(llm=MockLLM(script))
    runner.run_day(
        agent_id=agent.id, date='2025-01-03',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 100.0},
        on_event=events.append,
    )
    decision_events = [e for e in events if e['kind'] == 'decision']
    assert len(decision_events) == 1
    e = decision_events[0]
    assert e['agent_id'] == agent.id
    assert e['date'] == '2025-01-03'
    assert e['action'] == 'buy'
    assert e['code'] == '600519.SH'
    assert e['outcome'] in ('approved', 'modified')


def test_agent_runner_emits_blocked_event_on_rejected_decision(observability_storage):
    from agents.runner import AgentRunner
    from llm.mock import MockLLM
    import storage

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-blk', initial_capital=1_000_000.0,
    )
    # Existing position at cap → buy more rejected (observability_storage sets
    # position_max_pct=15%, so 2000 shares @ 100 = 200k ≥ 150k cap)
    portfolio = {
        'cash': 800_000, 'equity': 1_000_000,
        'positions': {'600519.SH': {'shares': 2000, 'avg_price': 100.0}},
    }
    script = [{
        'text': 'buy more',
        'tool_calls': [{
            'id': 'r1', 'name': 'place_decision',
            'input': {'action': 'buy', 'code': '600519.SH', 'qty': 100,
                      'reason': 'x', 'thinking': 'x'},
        }],
        'stop_reason': 'tool_use',
    }]
    events = []
    AgentRunner(llm=MockLLM(script)).run_day(
        agent_id=agent.id, date='2025-01-03',
        portfolio=portfolio, market_context={},
        mark_prices={'600519.SH': 100.0},
        on_event=events.append,
    )
    blocked = [e for e in events if e['kind'] == 'blocked']
    assert len(blocked) == 1
    assert blocked[0]['agent_id'] == agent.id
    assert blocked[0]['date'] == '2025-01-03'
    assert 'reason' in blocked[0]
    assert len(blocked[0]['reason']) > 0  # non-empty reason from violation
    # Rejected decisions should NOT also emit 'decision'
    decisions = [e for e in events if e['kind'] == 'decision']
    assert decisions == []


def test_agent_runner_emits_tool_call_events(observability_storage):
    """Non-place_decision tool invocations emit tool_call events."""
    from agents.runner import AgentRunner
    from llm.base import Message, ToolCall, LLMResponse, Usage
    import storage

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-tool', initial_capital=1_000_000.0,
    )

    _usage = Usage(input_tokens=0, output_tokens=0)

    class TwoRoundLLM:
        def __init__(self):
            self._n = 0
        def chat(self, *, messages, tools):
            self._n += 1
            if self._n == 1:
                return LLMResponse(
                    messages=[Message(role='assistant', content='let me check')],
                    tool_calls=[ToolCall(
                        id='t1', name='get_kline',
                        input={'code': '600519.SH', 'period': '1d', 'count': 30},
                    )],
                    stop_reason='tool_use',
                    usage=_usage,
                )
            return LLMResponse(
                messages=[Message(role='assistant', content='buy it')],
                tool_calls=[ToolCall(
                    id='t2', name='place_decision',
                    input={'action': 'buy', 'code': '600519.SH', 'qty': 100,
                           'reason': 'after research', 'thinking': 'buy'},
                )],
                stop_reason='tool_use',
                usage=_usage,
            )

    events = []
    AgentRunner(llm=TwoRoundLLM()).run_day(
        agent_id=agent.id, date='2025-01-03',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 100.0},
        on_event=events.append,
    )
    tool_call_events = [e for e in events if e['kind'] == 'tool_call']
    assert len(tool_call_events) >= 1
    assert tool_call_events[0]['tool_name'] == 'get_kline'
    assert tool_call_events[0]['agent_id'] == agent.id
    assert tool_call_events[0]['date'] == '2025-01-03'


def test_agent_runner_on_event_none_is_noop(observability_storage):
    """Default on_event=None shouldn't raise; existing tests still work."""
    from agents.runner import AgentRunner
    from llm.mock import MockLLM
    import storage

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-noop', initial_capital=1_000_000.0,
    )
    script = [{
        'text': 'x',
        'tool_calls': [{
            'id': 'c1', 'name': 'place_decision',
            'input': {'action': 'hold', 'reason': 'x', 'thinking': 'x'},
        }],
        'stop_reason': 'tool_use',
    }]
    runner = AgentRunner(llm=MockLLM(script))
    # No on_event passed — should not raise
    runner.run_day(
        agent_id=agent.id, date='2025-01-03',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 100.0},
    )


def test_backtest_runner_emits_progress_per_day(observability_storage, monkeypatch):
    from datetime import date, timedelta
    import storage
    from backtest.runner import BacktestRunner
    import backtest.runner as runner_mod
    from llm.mock import MockLLM

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-prog', initial_capital=1_000_000.0,
    )
    days = [date(2025, 1, 2) + timedelta(days=i) for i in range(5)]
    bars = [(d, 100.0 + i * 0.1) for i, d in enumerate(days)]
    monkeypatch.setattr(runner_mod, '_load_daily_closes',
                        lambda code, start, end: bars)
    monkeypatch.setattr(runner_mod, '_trading_days',
                        lambda start, end: days)

    hold = {'tool_calls': [{'id': 'h', 'name': 'place_decision',
                            'input': {'action': 'hold',
                                      'reason': 'x', 'thinking': 'x'}}],
            'stop_reason': 'tool_use'}
    events = []
    BacktestRunner(llm=MockLLM([hold]*5)).run(
        session_id='s-prog', agent_id=agent.id,
        start_date='2025-01-02', end_date='2025-01-06',
        universe=['600519.SH'], initial_capital=1_000_000.0,
        on_event=events.append,
    )
    progress = [e for e in events if e['kind'] == 'progress']
    assert len(progress) == 5
    assert progress[0]['date'] == '2025-01-02'
    assert progress[0]['agent_id'] == agent.id
    assert 'equity' in progress[0]
    assert 'pnl_pct' in progress[0]


def test_multi_agent_runner_forwards_on_event(observability_storage, monkeypatch):
    """run_multi passes on_event into each BacktestRunner.run."""
    from datetime import date, timedelta
    import storage
    from backtest.multi_agent_runner import run_multi
    import backtest.runner as runner_mod
    from llm.mock import MockLLM
    from llm.factory import build_llm  # noqa: just to confirm import

    a1 = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-multi-1', initial_capital=1_000_000.0,
    )
    a2 = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-multi-2', initial_capital=1_000_000.0,
    )
    days = [date(2025, 1, 2) + timedelta(days=i) for i in range(3)]
    bars = [(d, 100.0 + i * 0.1) for i, d in enumerate(days)]
    monkeypatch.setattr(runner_mod, '_load_daily_closes',
                        lambda code, start, end: bars)
    monkeypatch.setattr(runner_mod, '_trading_days',
                        lambda start, end: days)

    hold = {'tool_calls': [{'id': 'h', 'name': 'place_decision',
                            'input': {'action': 'hold',
                                      'reason': 'x', 'thinking': 'x'}}],
            'stop_reason': 'tool_use'}
    events = []
    run_multi(
        session_id='s-multi',
        agent_configs=[
            {'agent_id': a1.id, 'llm': MockLLM([hold]*3)},
            {'agent_id': a2.id, 'llm': MockLLM([hold]*3)},
        ],
        start_date='2025-01-02', end_date='2025-01-04',
        initial_capital=1_000_000.0, universe=['600519.SH'],
        on_event=events.append,
    )
    progress = [e for e in events if e['kind'] == 'progress']
    # 2 agents × 3 days = 6 progress events
    assert len(progress) == 6
    agent_ids_in_events = {e['agent_id'] for e in progress}
    assert agent_ids_in_events == {a1.id, a2.id}


def test_backtest_runner_on_event_none_is_noop(observability_storage, monkeypatch):
    """Default on_event=None should not break existing flow."""
    from datetime import date, timedelta
    import storage
    from backtest.runner import BacktestRunner
    import backtest.runner as runner_mod
    from llm.mock import MockLLM

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-noop', initial_capital=1_000_000.0,
    )
    days = [date(2025, 1, 2) + timedelta(days=i) for i in range(3)]
    bars = [(d, 100.0) for d in days]
    monkeypatch.setattr(runner_mod, '_load_daily_closes',
                        lambda code, start, end: bars)
    monkeypatch.setattr(runner_mod, '_trading_days',
                        lambda start, end: days)
    hold = {'tool_calls': [{'id': 'h', 'name': 'place_decision',
                            'input': {'action': 'hold',
                                      'reason': 'x', 'thinking': 'x'}}],
            'stop_reason': 'tool_use'}
    # No on_event passed — should not raise
    r = BacktestRunner(llm=MockLLM([hold]*3)).run(
        session_id='s-noop', agent_id=agent.id,
        start_date='2025-01-02', end_date='2025-01-04',
        universe=['600519.SH'], initial_capital=1_000_000.0,
    )
    assert r is not None
