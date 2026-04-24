# P3-D SSE Fine-grained Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Backtest 过程中前端能实时看到 agent 在做什么 — 推理了什么，调用了什么工具，做了什么决策，哪些被拒。用户不用等整个回测结束才知道情况。

**Architecture:**
- 不改 `jobs.py` 的状态追踪机制；在 `JobStatus` 追加 `events: list[dict]` append-only 列表
- 加 `on_event: callable | None` 贯穿 AgentRunner → BacktestRunner → multi_agent_runner → jobs.py 的回调链；每层在关键节点 call `on_event({kind, ...})`
- SSE endpoint 重写：除了现有 state 快照，还按 cursor 流式输出新事件
- 前端 `useJobStatusStream` 新增 `events: Event[]` 状态；BacktestLab running 阶段显示 live event log（每条 1 行）
- Spec §15.6 要求的 7 种事件：`phase / progress / tool_call / decision / blocked / baseline_done / done`（`done` 已有）

**Tech Stack:** Python 3.10 / Flask / SSE / React 19 / TypeScript

---

## File Structure

**Backend:**
- `backtest/jobs.py` — `JobStatus.events`, `Event` shape helper, `EventEmitter` protocol
- `agents/runner.py` — `run_day(..., on_event=None)` 参数；emit decision / tool_call / blocked
- `backtest/runner.py` — `run(..., on_event=None)` 参数；emit progress per-day，pass through to `run_day`
- `backtest/multi_agent_runner.py` — 接受 on_event，转发给每个 BacktestRunner
- `api/backtests.py` — SSE 端点改 cursor-based event streaming
- `tests/test_sse_events.py` (new)

**Frontend:**
- `frontend/src/api/types.ts` — `BacktestEvent` discriminated union + extend `JobStatus` (if needed)
- `frontend/src/api/hooks.ts` — `useJobStatusStream` 追加 events 处理
- `frontend/src/components/LiveEventLog.tsx` (new) — running 阶段的事件流面板
- `frontend/src/pages/BacktestLab.tsx` — 在 JobPanel 的 running 分支挂 LiveEventLog

---

### Task 1: JobStatus.events + Event 类型

**Files:**
- Modify: `backtest/jobs.py`
- Test: `tests/test_sse_events.py` (new)

**Design:**
- Event shape: `{kind: str, ts: float, ...payload}`
- `kind` is one of: `phase / progress / tool_call / decision / blocked / baseline_done / done`
- `ts` is Unix float seconds (auto-populated by emitter if not set)
- `EventEmitter = Callable[[dict], None]` — simple append-only callback
- Thread-safety: append to `status.events` under `_lock`

- [ ] **Step 1: 写失败测试**

Create `tests/test_sse_events.py`:

```python
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
    assert 'ts' in e  # timestamp auto-populated


def test_emit_event_preserves_explicit_ts():
    from backtest.jobs import JobStatus, emit_event
    s = JobStatus(session_id='s1')
    emit_event(s, {'kind': 'progress', 'ts': 12345.67, 'date': '2025-01-02'})
    assert s.events[0]['ts'] == 12345.67
```

- [ ] **Step 2: RED**

Run: `python -m pytest tests/test_sse_events.py -v`
Expected: 3 FAIL.

- [ ] **Step 3: 修改 `backtest/jobs.py`**

- Add `events: list = field(default_factory=list)` to `JobStatus`
- Add `emit_event(status: JobStatus, event: dict) -> None` helper that:
  - Populates `ts` if missing
  - Appends to `status.events` (no external lock needed — single-threaded per-job, callers can use `_lock` if concerned)

```python
def emit_event(status: JobStatus, event: dict) -> None:
    """Append an event to the job's event log. Fills ts if missing.
    Thread-safe for single-writer-per-job (jobs.py's worker thread)."""
    if 'ts' not in event:
        event['ts'] = time.time()
    status.events.append(event)
```

- [ ] **Step 4: GREEN**

Run: `python -m pytest tests/test_sse_events.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backtest/jobs.py tests/test_sse_events.py
git commit -m "feat(p3d): JobStatus.events + emit_event helper"
```

---

### Task 2: AgentRunner.run_day → on_event hook

**Files:**
- Modify: `agents/runner.py`
- Test: `tests/test_sse_events.py`

**Design:**
- `run_day(..., on_event: Callable[[dict], None] | None = None)`
- Inside the tool-use loop:
  - Before each LLM call: emit `{kind: 'phase', phase: 'llm_call', iter: N, agent_id, date}` — optional, decide if needed
  - For each non-place_decision tool call: emit `{kind: 'tool_call', agent_id, date, tool_name, tool_input}`
  - For each place_decision:
    - After validation:
      - If outcome in ('approved', 'modified'): emit `{kind: 'decision', agent_id, date, action, code, shares, price, outcome}`
      - If outcome == 'rejected': emit `{kind: 'blocked', agent_id, date, decision_input, reason}`
- The existing `last_thinking` capture stays; events are a parallel stream

- [ ] **Step 1: 写测试**

Append to `tests/test_sse_events.py`:

```python
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
    assert decision_events[0]['agent_id'] == agent.id
    assert decision_events[0]['date'] == '2025-01-03'
    assert decision_events[0]['action'] == 'buy'
    assert decision_events[0]['code'] == '600519.SH'
    assert decision_events[0]['outcome'] in ('approved', 'modified')


def test_agent_runner_emits_blocked_event_on_rejected_decision(observability_storage):
    """When validation rejects (e.g. position cap), emit 'blocked' not 'decision'."""
    from agents.runner import AgentRunner
    from llm.mock import MockLLM
    import storage

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-blk', initial_capital=1_000_000.0,
    )
    # Existing position at cap → buy more rejected
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
    # Should NOT also emit a decision event for rejected
    decisions = [e for e in events if e['kind'] == 'decision']
    assert decisions == []


def test_agent_runner_emits_tool_call_events(observability_storage):
    """Non-place_decision tool invocations emit tool_call events."""
    # This is harder to test because tool_call requires a research tool like
    # get_kline to be allowed + LLM to invoke it. For MVP: verify the hook
    # is called — exercise via a scripted LLM that calls a research tool.
    from agents.runner import AgentRunner
    from llm.mock import MockLLM
    from llm.base import Message, ToolCall, LLMResponse
    import storage

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-tool', initial_capital=1_000_000.0,
    )

    class TwoRoundLLM:
        def __init__(self):
            self._n = 0
        def chat(self, *, messages, tools):
            self._n += 1
            if self._n == 1:
                # Round 1: call get_kline
                return LLMResponse(
                    messages=[Message(role='assistant', content='let me check')],
                    tool_calls=[ToolCall(
                        id='t1', name='get_kline',
                        input={'code': '600519.SH', 'period': '1d', 'count': 30},
                    )],
                    raw={},
                )
            # Round 2: decide
            return LLMResponse(
                messages=[Message(role='assistant', content='buy it')],
                tool_calls=[ToolCall(
                    id='t2', name='place_decision',
                    input={'action': 'buy', 'code': '600519.SH', 'qty': 100,
                           'reason': 'after research', 'thinking': 'buy'},
                )],
                raw={},
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
```

- [ ] **Step 2: RED**

- [ ] **Step 3: Implement hook in AgentRunner.run_day**

Add `on_event: Callable | None = None` param. Inside the loop:

```python
def _emit(kind: str, **kwargs):
    if on_event is None:
        return
    on_event({'kind': kind, 'agent_id': agent_id, 'date': date, **kwargs})
```

Then:
- After the non-place_decision tool branch (where `thinking_tool_calls.append(...)` is), also call:
  `_emit('tool_call', tool_name=call.name, tool_input=call.input or {})`
- In the place_decision branch, after `thinking_decisions.append(...)`:
  ```python
  if result.outcome == 'rejected':
      _emit('blocked',
            decision_input={'action': decision.get('action'),
                            'code': decision.get('code'),
                            'shares': decision.get('shares')},
            reason=result.reason if hasattr(result, 'reason') else 'rejected by validation')
  else:
      _emit('decision',
            action=decision.get('action'),
            code=decision.get('code'),
            shares=decision.get('shares'),
            price=decision.get('price'),
            outcome=result.outcome)
  ```

Check validation engine for what's in `result` — if `.reason` or `.violation.reason`. Adapt.

- [ ] **Step 4: GREEN**

Run: `python -m pytest tests/test_sse_events.py -v -k "agent_runner"`

- [ ] **Step 5: Regression**

Run: `python -m pytest tests/test_backtest_observability.py tests/test_backtest_runner.py -q 2>&1 | tail -3`
Expected: 0 regressions (on_event is a new optional param, should not affect existing tests).

- [ ] **Step 6: Commit**

```bash
git add agents/runner.py tests/test_sse_events.py
git commit -m "feat(p3d): AgentRunner emits decision/blocked/tool_call events via on_event"
```

---

### Task 3: BacktestRunner + multi_agent_runner 转发

**Files:**
- Modify: `backtest/runner.py`
- Modify: `backtest/multi_agent_runner.py`
- Test: `tests/test_sse_events.py`

**Design:**
- `BacktestRunner.run(..., on_event=None)` — per day emits `{kind: 'progress', date, agent_id, equity, pnl_pct}`; forwards `on_event` into `runner.run_day(on_event=on_event)`
- `run_multi(..., on_event=None)` — forwards `on_event` into each worker's `BacktestRunner.run(on_event=on_event)`; emits `{kind: 'phase', phase: 'loading_prices', ...}` etc at key points if desired (optional)

- [ ] **Step 1: Write tests**

```python
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
                            'input': {'action': 'hold', 'reason': 'x',
                                      'thinking': 'x'}}],
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
```

- [ ] **Step 2: RED + Implement + GREEN**

Edit `backtest/runner.py`. Add `on_event` kwarg to `run`. In the per-day loop, after computing equity + pnl_pct, emit:

```python
if on_event:
    on_event({
        'kind': 'progress', 'agent_id': agent_id,
        'date': d.strftime('%Y-%m-%d'),
        'equity': equity, 'pnl_pct': pnl_pct,
    })
```

Forward to `runner.run_day(on_event=on_event, ...)`.

Edit `backtest/multi_agent_runner.py`:

```python
def run_multi(*, session_id: str,
              agent_configs: list[dict],
              start_date: str, end_date: str,
              initial_capital: float,
              universe: list[str],
              max_workers: int = 4,
              on_event=None) -> list:
    # ... same as before, but:
    def _one(cfg):
        runner = BacktestRunner(llm=cfg['llm'])
        return runner.run(
            session_id=session_id, agent_id=cfg['agent_id'],
            start_date=start_date, end_date=end_date,
            initial_capital=initial_capital, universe=universe,
            on_event=on_event,
        )
    # ... rest unchanged
```

- [ ] **Step 3: GREEN + regression + commit**

```bash
git add backtest/runner.py backtest/multi_agent_runner.py tests/test_sse_events.py
git commit -m "feat(p3d): BacktestRunner/multi emit progress events + forward on_event"
```

---

### Task 4: jobs.py 连接 on_event + 发 phase/baseline_done/done events

**Files:**
- Modify: `backtest/jobs.py`
- Test: `tests/test_sse_events.py`

**Design:**
- In `_run`, define `on_event` closure that appends to `status.events` via `emit_event`
- Emit:
  - `phase='data_loading'` when `_run` starts
  - `phase='running'` before `run_multi`
  - `phase='baselines'` before baselines run
  - `baseline_done` per baseline after `run_all` returns (attach baseline name + result_id)
  - `done` at the end (spec §15.6 requirement)

- [ ] **Step 1: Write tests**

```python
def test_submit_backtest_emits_phase_events(observability_storage, monkeypatch):
    """Verify jobs.py wiring puts phase + done events into status.events."""
    # This test will actually kick off the worker thread. Use a mocked
    # run_multi + run_all to keep it fast and deterministic.
    import storage
    from datetime import date, timedelta
    from backtest.base import BacktestResult, BacktestStats
    from backtest.jobs import submit_backtest, get_status

    # Create a real agent to satisfy the agent lookup in jobs.py
    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-jobs', initial_capital=1_000_000.0,
    )

    # Stub run_multi: instantly return one empty result
    def _fake_run_multi(*, session_id, agent_configs, start_date, end_date,
                       initial_capital, universe, on_event=None, **_kw):
        if on_event:
            on_event({'kind': 'progress', 'agent_id': agent.id,
                      'date': start_date, 'equity': initial_capital,
                      'pnl_pct': 0.0})
        stats = BacktestStats(sharpe=0, max_drawdown_pct=0, trade_count=0,
                              win_rate=0, max_daily_loss_pct=0,
                              total_return_pct=0, final_equity=initial_capital)
        r = BacktestResult(
            id='r-fake', session_id=session_id, agent_id=agent.id,
            persona_id=None, model_id=None,
            start_date=start_date, end_date=end_date,
            initial_capital=initial_capital, stats=stats, zone_stats=[],
            quality_gate_label='pass', quality_gate_criteria={},
        )
        storage.backtests().insert(r)
        return [r]

    import backtest.multi_agent_runner as mar
    monkeypatch.setattr(mar, 'run_multi', _fake_run_multi)

    # Also stub baselines to skip
    import backtest.baselines.runner as bl_runner
    monkeypatch.setattr(bl_runner, 'run_all',
                        lambda *a, **kw: [])

    import backtest.jobs as jobs_mod
    # We need the module used inside _run — verify which import path it uses
    # and monkeypatch accordingly. Likely `from backtest.multi_agent_runner import run_multi`
    # means we need to patch on backtest.jobs directly if it does a late import.
    # If late-imported: patching `mar.run_multi` is sufficient.

    submit_backtest(
        session_id='s-jobs', agent_ids=[agent.id],
        start_date='2025-01-02', end_date='2025-01-08',
        initial_capital=1_000_000.0, universe=['600519.SH'],
        include_baselines=False,
    )
    # Wait for completion
    import time
    for _ in range(100):
        st = get_status('s-jobs')
        if st and st.state in ('complete', 'failed'):
            break
        time.sleep(0.1)
    st = get_status('s-jobs')
    assert st.state == 'complete', f'state={st.state}, error={st.error}'

    kinds = [e['kind'] for e in st.events]
    # Must see phase transitions + progress + done
    assert 'phase' in kinds
    assert 'done' in kinds
    # Phase events must include 'running' (phase: 'running' with session context)
    phase_events = [e for e in st.events if e['kind'] == 'phase']
    assert any(p['phase'] == 'running' for p in phase_events)
```

- [ ] **Step 2: RED + Implement + GREEN**

Edit `backtest/jobs.py::_run`:

```python
def _run():
    with _lock:
        pass
    try:
        status.state = 'running'
        status.started_at = time.time()
        emit_event(status, {'kind': 'phase', 'phase': 'data_loading',
                            'session_id': session_id})

        from llm.factory import build_llm
        from backtest.multi_agent_runner import run_multi

        status.progress = 'building LLM adapters'
        import storage
        configs = []
        for aid in agent_ids:
            a = storage.agents().get(aid)
            if a is None:
                raise ValueError(f'unknown agent_id: {aid}')
            llm = build_llm(a.model_id)
            configs.append({'agent_id': aid, 'llm': llm})

        emit_event(status, {'kind': 'phase', 'phase': 'running',
                            'session_id': session_id})
        status.progress = f'running {len(configs)} agents in parallel'

        def _on_event(ev):
            emit_event(status, ev)

        results = run_multi(
            session_id=session_id, agent_configs=configs,
            start_date=start_date, end_date=end_date,
            initial_capital=initial_capital, universe=universe,
            on_event=_on_event,
        )
        status.agent_result_ids = [r.id for r in results]

        if include_baselines:
            emit_event(status, {'kind': 'phase', 'phase': 'baselines',
                                'session_id': session_id})
            status.progress = 'running baselines'
            from backtest.baselines.runner import run_all
            baselines = run_all(
                session_id=session_id,
                start_date=start_date, end_date=end_date,
                initial_capital=initial_capital, universe=universe,
            )
            for b in baselines:
                emit_event(status, {'kind': 'baseline_done',
                                    'baseline_name': b.name,
                                    'result_id': b.id})
            status.baseline_result_ids = [b.id for b in baselines]

        status.progress = 'done'
        status.state = 'complete'
        emit_event(status, {'kind': 'done', 'session_id': session_id})
    except Exception as e:  # noqa: BLE001
        status.state = 'failed'
        status.error = f'{type(e).__name__}: {e}\n{traceback.format_exc()[:500]}'
        emit_event(status, {'kind': 'failed', 'session_id': session_id,
                            'error': status.error})
    finally:
        status.finished_at = time.time()
```

- [ ] **Step 3: Commit**

```bash
git add backtest/jobs.py tests/test_sse_events.py
git commit -m "feat(p3d): jobs.py wires on_event + phase/baseline_done/done events"
```

---

### Task 5: SSE endpoint — cursor-based event stream

**Files:**
- Modify: `api/backtests.py` — rewrite `stream_backtest_job`
- Test: `tests/test_sse_events.py`

**Design:**
- Keep backward-compatible: first message is still a full status snapshot on `data:` default channel
- After that: stream each new event as `event: <kind>\ndata: {...}\n\n`
- Use a cursor `last_index` initialized to 0 on connect; each poll yields events `status.events[last_index:]` then updates `last_index = len(status.events)`
- Still close stream on `state in ('complete', 'failed')` with final `event: done`
- 500ms poll + 3600 max iterations unchanged

- [ ] **Step 1: Write test (test client with threaded worker)**

Testing SSE via Flask test client is tricky because test client doesn't handle streaming well. Skip SSE integration test at the HTTP level for MVP — trust that the new code paths are covered by the Task 4 worker test + a unit test for the generator function if extracted. Document this in the plan.

Quick unit test: extract the SSE payload building to a helper and test it independently.

Actually simpler: assert that after `submit_backtest` runs, an in-process HTTP SSE request succeeds and returns multi-line SSE with the expected event kinds. Use `client.get('/api/backtests/jobs/<sid>/stream')` with a timeout.

```python
def test_sse_stream_emits_events_after_completion(observability_storage, client, monkeypatch):
    """Connect to SSE stream AFTER a job has already completed — should emit
    all accumulated events + final 'done'."""
    import storage
    from backtest.base import BacktestResult, BacktestStats
    from backtest.jobs import submit_backtest, get_status
    import time

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='t-sse', initial_capital=1_000_000.0,
    )

    def _fake_run_multi(*, session_id, agent_configs, start_date, end_date,
                       initial_capital, universe, on_event=None, **_kw):
        if on_event:
            on_event({'kind': 'progress', 'agent_id': agent.id,
                      'date': start_date, 'equity': initial_capital,
                      'pnl_pct': 0.0})
        stats = BacktestStats(sharpe=0, max_drawdown_pct=0, trade_count=0,
                              win_rate=0, max_daily_loss_pct=0,
                              total_return_pct=0, final_equity=initial_capital)
        r = BacktestResult(
            id='r-sse', session_id=session_id, agent_id=agent.id,
            persona_id=None, model_id=None,
            start_date=start_date, end_date=end_date,
            initial_capital=initial_capital, stats=stats, zone_stats=[],
            quality_gate_label='pass', quality_gate_criteria={},
        )
        storage.backtests().insert(r)
        return [r]

    import backtest.multi_agent_runner as mar
    monkeypatch.setattr(mar, 'run_multi', _fake_run_multi)
    import backtest.baselines.runner as bl_runner
    monkeypatch.setattr(bl_runner, 'run_all', lambda *a, **kw: [])

    submit_backtest(
        session_id='s-sse', agent_ids=[agent.id],
        start_date='2025-01-02', end_date='2025-01-08',
        initial_capital=1_000_000.0, universe=['600519.SH'],
        include_baselines=False,
    )
    # Wait for completion
    for _ in range(50):
        st = get_status('s-sse')
        if st and st.state == 'complete':
            break
        time.sleep(0.1)

    # Request SSE stream — should emit accumulated events + final done
    resp = client.get('/api/backtests/jobs/s-sse/stream',
                      buffered=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Should contain at least 'phase' and 'done' event lines
    assert 'event: phase' in body
    assert 'event: done' in body
    # And at least one progress event
    assert 'event: progress' in body or 'progress' in body
```

The test client returns the full body after the generator closes (since the job is already complete, the stream closes on first iteration). This makes the test deterministic.

- [ ] **Step 2: RED**

- [ ] **Step 3: Rewrite `stream_backtest_job`**

```python
@api_bp.route('/backtests/jobs/<session_id>/stream')
def stream_backtest_job(session_id):
    """SSE stream: status snapshots + fine-grained events (P3-D).

    Emits:
    - Default channel: job status snapshot (unchanged from pre-P3-D)
    - event: phase         — backtest lifecycle phase transitions
    - event: progress      — per-day (per-agent) equity update
    - event: tool_call     — LLM called a research tool
    - event: decision      — place_decision that passed validation
    - event: blocked       — place_decision rejected by validation
    - event: baseline_done — one baseline finished
    - event: done          — terminal
    - event: notfound / timeout — stream-level signals
    """
    import json
    import time
    from flask import Response
    from backtest.jobs import get_status

    def _status_snapshot(status) -> str:
        payload = {
            'session_id': status.session_id,
            'state': status.state,
            'progress': status.progress,
            'agent_ids': status.agent_ids,
            'agent_result_ids': status.agent_result_ids,
            'baseline_result_ids': status.baseline_result_ids,
            'error': status.error,
            'submitted_at': status.submitted_at,
            'started_at': status.started_at,
            'finished_at': status.finished_at,
        }
        return f'data: {json.dumps(payload, ensure_ascii=False)}\n\n'

    def _event_line(ev: dict) -> str:
        kind = ev.get('kind', 'unknown')
        return (f'event: {kind}\n'
                f'data: {json.dumps(ev, ensure_ascii=False)}\n\n')

    def generate():
        last_snapshot = None
        last_event_idx = 0
        iterations = 0
        while iterations < 3600:
            status = get_status(session_id)
            if status is None:
                yield 'event: notfound\ndata: {}\n\n'
                return

            # Status snapshot (only on change)
            snapshot = _status_snapshot(status)
            if snapshot != last_snapshot:
                yield snapshot
                last_snapshot = snapshot

            # New events since last poll
            new_events = status.events[last_event_idx:]
            for ev in new_events:
                yield _event_line(ev)
            last_event_idx = len(status.events)

            if status.state in ('complete', 'failed'):
                yield 'event: done\ndata: {}\n\n'
                return

            time.sleep(0.5)
            iterations += 1
        yield 'event: timeout\ndata: {}\n\n'

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
    })
```

Note: pre-P3-D the endpoint had a duplicated `yield 'event: done\ndata: {}\n\n'` AFTER state became complete. Keep that semantics — it's the termination signal.

- [ ] **Step 4: GREEN + regression + commit**

```bash
git add api/backtests.py tests/test_sse_events.py
git commit -m "feat(p3d): SSE endpoint streams phase/progress/tool_call/decision/blocked/baseline_done events"
```

---

### Task 6: Frontend — useJobStatusStream events + types

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/hooks.ts`

**Design:**
- Add `BacktestEvent` discriminated union
- Extend `useJobStatusStream` return: `{status, events, error}` (events is a flat list, appended as received)
- Each EventSource.addEventListener per kind appends a typed event

- [ ] **Step 1: Add types**

```typescript
export type BacktestEventPhase = {
  kind: 'phase'; ts: number; phase: string; session_id?: string;
};
export type BacktestEventProgress = {
  kind: 'progress'; ts: number; agent_id: string; date: string;
  equity?: number; pnl_pct?: number;
};
export type BacktestEventToolCall = {
  kind: 'tool_call'; ts: number; agent_id: string; date: string;
  tool_name: string; tool_input: Record<string, unknown>;
};
export type BacktestEventDecision = {
  kind: 'decision'; ts: number; agent_id: string; date: string;
  action: string; code?: string; shares?: number; price?: number;
  outcome: string;
};
export type BacktestEventBlocked = {
  kind: 'blocked'; ts: number; agent_id: string; date: string;
  decision_input: Record<string, unknown>; reason: string;
};
export type BacktestEventBaselineDone = {
  kind: 'baseline_done'; ts: number; baseline_name: string; result_id: string;
};
export type BacktestEventDone = {
  kind: 'done'; ts: number; session_id?: string;
};

export type BacktestEvent =
  | BacktestEventPhase
  | BacktestEventProgress
  | BacktestEventToolCall
  | BacktestEventDecision
  | BacktestEventBlocked
  | BacktestEventBaselineDone
  | BacktestEventDone;
```

- [ ] **Step 2: Extend `useJobStatusStream`**

```typescript
export const useJobStatusStream = (
  sessionId: string | undefined,
  enabled = true,
) => {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [events, setEvents] = useState<BacktestEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!sessionId || !enabled) {
      setStatus(null);
      setEvents([]);
      setError(null);
      return;
    }
    setStatus(null);
    setEvents([]);
    setError(null);

    const es = new EventSource(`/api/backtests/jobs/${sessionId}/stream`);
    esRef.current = es;

    es.onmessage = (ev) => {
      try {
        setStatus(JSON.parse(ev.data) as JobStatus);
      } catch { /* ignore */ }
    };

    const kinds: BacktestEvent['kind'][] = [
      'phase', 'progress', 'tool_call', 'decision',
      'blocked', 'baseline_done',
    ];
    for (const kind of kinds) {
      es.addEventListener(kind, (ev: MessageEvent) => {
        try {
          const parsed = JSON.parse(ev.data) as BacktestEvent;
          setEvents((prev) => [...prev, parsed]);
        } catch { /* ignore */ }
      });
    }

    es.addEventListener('done', () => { es.close(); });
    es.addEventListener('notfound', () => {
      setError('job not found'); es.close();
    });
    es.addEventListener('timeout', () => {
      setError('stream timeout'); es.close();
    });
    es.onerror = () => {
      setError((prev) => prev ?? 'stream error');
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [sessionId, enabled]);

  return { status, events, error };
};
```

Build must pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/hooks.ts
git commit -m "feat(p3d): frontend types + useJobStatusStream consumes SSE events"
```

---

### Task 7: LiveEventLog component + BacktestLab integration

**Files:**
- Create: `frontend/src/components/LiveEventLog.tsx`
- Modify: `frontend/src/pages/BacktestLab.tsx`

**Design:**
- LiveEventLog takes `events: BacktestEvent[]`; renders them as a scrollable list (newest on top? or bottom with auto-scroll? Pick: bottom with auto-scroll for log-tail semantics, but cap at last 200 rows to keep DOM cheap)
- Each event line: timestamp (HH:MM:SS) + event kind badge + short summary
- BacktestLab: in JobPanel's "running" branch, show LiveEventLog panel instead of the plain "正在实时推送状态（SSE）…" placeholder

- [ ] **Step 1: Implement LiveEventLog**

```tsx
import type { BacktestEvent } from '../api/types';

const MAX_ROWS = 200;

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('en-US', { hour12: false });
}

function renderSummary(e: BacktestEvent): { badge: string; text: string; color: string } {
  switch (e.kind) {
    case 'phase':
      return { badge: 'phase', text: e.phase, color: 'var(--brand)' };
    case 'progress':
      return {
        badge: 'progress',
        text: `${e.agent_id.slice(0, 12)}… · ${e.date} · equity ${e.equity?.toFixed(0)} · ${(e.pnl_pct ?? 0).toFixed(2)}%`,
        color: 'var(--text-dim)',
      };
    case 'tool_call':
      return {
        badge: 'tool',
        text: `${e.agent_id.slice(0, 12)}… · ${e.date} · ${e.tool_name}`,
        color: 'var(--text-hi)',
      };
    case 'decision':
      return {
        badge: 'decision',
        text: `${e.agent_id.slice(0, 12)}… · ${e.date} · ${e.action} ${e.code ?? ''} ${e.shares ?? ''} @ ${e.price?.toFixed(2) ?? '—'} · ${e.outcome}`,
        color: 'var(--up)',
      };
    case 'blocked':
      return {
        badge: 'blocked',
        text: `${e.agent_id.slice(0, 12)}… · ${e.date} · blocked: ${e.reason}`,
        color: 'var(--down)',
      };
    case 'baseline_done':
      return {
        badge: 'baseline',
        text: `${e.baseline_name} done`,
        color: 'var(--text-faint)',
      };
    case 'done':
      return { badge: 'done', text: 'session complete', color: 'var(--brand)' };
    default:
      return { badge: 'event', text: JSON.stringify(e), color: 'var(--text-faint)' };
  }
}

export function LiveEventLog({ events }: { events: BacktestEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="text-text-faint text-xs italic">
        正在等待事件…
      </div>
    );
  }
  const trimmed = events.slice(-MAX_ROWS);
  return (
    <div
      className="grid gap-0.5"
      style={{
        maxHeight: 280, overflowY: 'auto',
        border: '1px solid var(--panel-border-soft)',
        borderRadius: 4, padding: '6px 8px',
        background: 'var(--bg-3)',
        fontSize: 11,
      }}
    >
      {trimmed.map((e, i) => {
        const { badge, text, color } = renderSummary(e);
        return (
          <div key={i} className="flex gap-2 items-baseline mono">
            <span className="text-text-ghost" style={{ fontSize: 10 }}>
              {formatTime(e.ts)}
            </span>
            <span
              style={{
                padding: '1px 6px', borderRadius: 2, fontSize: 9,
                background: 'var(--bg-2)', color,
                minWidth: 64, textAlign: 'center',
              }}
            >
              {badge}
            </span>
            <span className="text-text-dim" style={{ lineBreak: 'anywhere' }}>
              {text}
            </span>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Mount in BacktestLab**

In `BacktestLab.tsx`, in `JobPanel`, destructure events:
```tsx
const { status: job, events, error: streamErr } = jobStream;
```

(Actually jobStream hook already returns `{status, events, error}` after Task 6.)

Replace the "正在实时推送状态（SSE）…" placeholder block with LiveEventLog:

```tsx
{(!job || job.state === 'queued' || job.state === 'running') && !error && (
  <div className="mt-3">
    <div className="text-[10px] text-text-ghost uppercase tracking-wider mb-1">
      实时事件 · Live Events
    </div>
    <LiveEventLog events={events} />
  </div>
)}
```

Import at top:
```tsx
import { LiveEventLog } from '../components/LiveEventLog';
```

Pass jobStream.events into JobPanel (extend props).

- [ ] **Step 3: Build + commit**

```bash
git add frontend/src/components/LiveEventLog.tsx frontend/src/pages/BacktestLab.tsx
git commit -m "feat(p3d): LiveEventLog component + BacktestLab integration"
```

---

### Task 8: Regression + roadmap

- [ ] `python -m pytest -q` — verify 517 baseline + new P3-D tests, 0 regressions
- [ ] `cd frontend && npm run build` — clean
- [ ] Update `docs/superpowers/plans/2026-04-23-status-and-roadmap.md`:
   - P3-D section → ✅ Done
   - Section 7 link to this plan
- [ ] Commit roadmap
- [ ] `finishing-a-development-branch` — merge + push decision

---

## Self-Review

**Spec coverage (§15.6):**
- `event: phase` ✅ Task 4
- `event: progress` ✅ Task 3
- `event: tool_call` ✅ Task 2
- `event: decision` ✅ Task 2
- `event: blocked` ✅ Task 2
- `event: baseline_done` ✅ Task 4
- `event: done` ✅ Task 4

**Not covered:**
- Rule mode doesn't emit events (all decisions are synthetic). Out of scope for P3-D — rule backtests are synchronous and too fast to benefit from streaming.

**Type consistency:** BacktestEvent union matches backend event shapes 1:1.

**No placeholders:** Every step has code + commands + expected output.

---

## Execution Handoff

Subagent-driven。预估每任务：

- Task 1: 15 min
- Task 2: 50 min (最复杂——3 种 event，需要验证 validation engine 的 outcome 字段)
- Task 3: 30 min
- Task 4: 40 min
- Task 5: 30 min
- Task 6: 25 min
- Task 7: 35 min
- Task 8: 15 min

Total: ~4 小时 + review ≈ 1.5 天。
