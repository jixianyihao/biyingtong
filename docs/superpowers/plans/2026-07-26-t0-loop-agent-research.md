# T0 Loop Agent 研究闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the truth/mutation/memory/orchestration layers of the T0 loop-agent research closed loop: hard gates, holdout windows, mutation operators, a leaderboard executor, and the `t0-research` skill playbook.

**Architecture:** Per spec `docs/superpowers/specs/2026-07-26-t0-loop-agent-research-design.md`. Pure-function modules in `qlib_research/` (gates, holdout, mutations) + one orchestration script (`scripts/research/t0_qlib_leaderboard.py`) that reuses `t0_qlib_replay.run_replay` per candidate. `run_t0_portfolio_backtest` stays the only execution truth. The agent-facing playbook lives in `.claude/skills/t0-research/SKILL.md`.

**Tech Stack:** Python 3.13, pytest, existing `t0/` + `qlib_research/` packages.

## Global Constraints

- `t0/portfolio.py` 是唯一执行真相——本计划**不修改**它；所有回测经 `run_t0_portfolio_backtest`。
- 默认窗口常量：进化窗口 `2026-01-01 → 2026-03-01`;holdout `2026-03-01 → 2026-04-01`（本地 .lc1 数据覆盖至 2026-04-01)。
- 默认变异预算：每轮迭代 `max_evaluations = 12` 次回测调用（进化 + holdout 复测都计入）。
- profile 组合级变异的合法词汇：`signal_mode ∈ {band, hybrid, vwap_deviation, adaptive_vwap, hybrid_adaptive}`;`execution_style ∈ {market, next_bar}`。
- 实验 profile 命名必须带 `exp/` 前缀；`t0/strategy_profiles.py` 的正式注册表**不允许**被修改。
- 每个 commit 用 `git -c user.name="ouyan" -c user.email="ouyan@users.noreply.github.com" commit`。
- `AGENTS.md` 保持 untracked，永不 stage。`data/qlib_research/` 已 gitignore，不提交。
- 测试命令统一 `python -m pytest <files> -q`。

---

### Task 1: 硬关卡模块 `qlib_research/gates.py`

**Files:**
- Create: `qlib_research/gates.py`
- Test: `tests/test_qlib_gates.py`

**Interfaces:**
- Consumes: nothing new (stdlib only)。
- Produces:
  - `T0GateThresholds` dataclass，字段与默认值见 Step 3
  - `GateResult(gate: int, name: str, passed: bool, detail: str)`
  - `GateVerdict(passed: bool, failed_gate: int | None, gates_passed: int, results: tuple[GateResult, ...])`
  - `ResearchBudget(max_evaluations: int = 12)`（预算属真理层，放本模块）
  - `evaluate_gates(metrics: dict, trading_days: int, thresholds: T0GateThresholds = T0GateThresholds()) -> GateVerdict`
  - 消费的 metrics keys:`cost_reduction_pct`、`cost_reduction_positive_days_pct`、`min_cost_reduction_pct`、`alpha_vs_all_in_hold`、`max_drawdown_pct`、`round_trips`（均为 `run_t0_portfolio_backtest` 返回键）。

- [ ] **Step 1: Write the failing tests**

Create `tests/test_qlib_gates.py`:

```python
from qlib_research.gates import ResearchBudget, T0GateThresholds, evaluate_gates


def _passing_metrics():
    return {
        'cost_reduction_pct': 0.84,
        'cost_reduction_positive_days_pct': 72.2,
        'min_cost_reduction_pct': -0.52,
        'alpha_vs_all_in_hold': 11366.33,
        'max_drawdown_pct': -10.63,
        'round_trips': 61,
    }


def test_evaluate_gates_passes_all_four_gates():
    verdict = evaluate_gates(_passing_metrics(), trading_days=36)

    assert verdict.passed is True
    assert verdict.failed_gate is None
    assert verdict.gates_passed == 4
    assert [r.gate for r in verdict.results] == [1, 2, 3, 4]
    assert all(r.passed for r in verdict.results)


def test_gate1_rejects_negative_cost_reduction():
    metrics = {**_passing_metrics(), 'cost_reduction_pct': -0.35}

    verdict = evaluate_gates(metrics, trading_days=36)

    assert verdict.passed is False
    assert verdict.failed_gate == 1
    assert verdict.gates_passed == 0
    assert len(verdict.results) == 1  # short-circuits at first failure


def test_gate1_rejects_unstable_cost_path():
    metrics = {**_passing_metrics(), 'cost_reduction_positive_days_pct': 40.0}

    verdict = evaluate_gates(metrics, trading_days=36)

    assert verdict.failed_gate == 1
    assert 'positive_days' in verdict.results[0].detail


def test_gate2_rejects_alpha_below_hold():
    metrics = {**_passing_metrics(), 'alpha_vs_all_in_hold': -100.0}

    verdict = evaluate_gates(metrics, trading_days=36)

    assert verdict.failed_gate == 2
    assert verdict.gates_passed == 1


def test_gate3_rejects_deep_drawdown():
    metrics = {**_passing_metrics(), 'max_drawdown_pct': -15.0}

    verdict = evaluate_gates(metrics, trading_days=36)

    assert verdict.failed_gate == 3
    assert verdict.gates_passed == 2


def test_gate4_rejects_too_few_round_trips():
    metrics = {**_passing_metrics(), 'round_trips': 5}

    verdict = evaluate_gates(metrics, trading_days=36)

    assert verdict.failed_gate == 4
    assert verdict.gates_passed == 3


def test_gate4_rejects_overtrading_per_day():
    metrics = {**_passing_metrics(), 'round_trips': 200}

    verdict = evaluate_gates(metrics, trading_days=36)

    assert verdict.failed_gate == 4
    assert 'overtrading' in verdict.results[-1].detail


def test_missing_metric_fails_closed():
    metrics = _passing_metrics()
    del metrics['alpha_vs_all_in_hold']

    verdict = evaluate_gates(metrics, trading_days=36)

    assert verdict.passed is False
    assert verdict.failed_gate == 2
    assert 'missing' in verdict.results[-1].detail


def test_thresholds_are_overridable():
    thresholds = T0GateThresholds(max_drawdown_abs_pct=20.0)
    metrics = {**_passing_metrics(), 'max_drawdown_pct': -15.0}

    verdict = evaluate_gates(metrics, trading_days=36, thresholds=thresholds)

    assert verdict.passed is True


def test_research_budget_default():
    assert ResearchBudget().max_evaluations == 12
    assert ResearchBudget(max_evaluations=3).max_evaluations == 3
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_qlib_gates.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'qlib_research.gates'`.

- [ ] **Step 3: Implement gates**

Create `qlib_research/gates.py`:

```python
"""Hard layered gates for the T0 loop-agent research closed loop.

Selection pressure lives here, in code — the agent may propose candidates,
but only these functions decide what survives. See
docs/superpowers/specs/2026-07-26-t0-loop-agent-research-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class T0GateThresholds:
    min_cost_reduction_pct: float = 0.0
    min_cost_reduction_positive_days_pct: float = 55.0
    min_worst_day_cost_reduction_pct: float = -1.0
    min_alpha_vs_all_in_hold: float = 0.0
    max_drawdown_abs_pct: float = 12.0
    min_round_trips: int = 20
    max_round_trips_per_day: float = 4.0


@dataclass(frozen=True)
class ResearchBudget:
    """Evaluation budget per loop iteration (anti-overfitting dimension)."""

    max_evaluations: int = 12


@dataclass(frozen=True)
class GateResult:
    gate: int
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class GateVerdict:
    passed: bool
    failed_gate: int | None
    gates_passed: int
    results: tuple[GateResult, ...]


def _metric(metrics: dict[str, Any], key: str) -> float | None:
    raw = metrics.get(key)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _gate1(metrics: dict[str, Any], t: T0GateThresholds) -> GateResult:
    cost = _metric(metrics, 'cost_reduction_pct')
    pos_days = _metric(metrics, 'cost_reduction_positive_days_pct')
    worst = _metric(metrics, 'min_cost_reduction_pct')
    if cost is None or pos_days is None or worst is None:
        return GateResult(1, 'cost_reduction', False, 'missing cost metrics')
    if cost <= t.min_cost_reduction_pct:
        return GateResult(
            1, 'cost_reduction', False,
            f'cost_reduction_pct={cost} <= {t.min_cost_reduction_pct}',
        )
    if pos_days < t.min_cost_reduction_positive_days_pct:
        return GateResult(
            1, 'cost_reduction', False,
            f'positive_days={pos_days} < {t.min_cost_reduction_positive_days_pct}',
        )
    if worst < t.min_worst_day_cost_reduction_pct:
        return GateResult(
            1, 'cost_reduction', False,
            f'worst_day={worst} < {t.min_worst_day_cost_reduction_pct}',
        )
    return GateResult(
        1, 'cost_reduction', True,
        f'cost={cost}, positive_days={pos_days}, worst_day={worst}',
    )


def _gate2(metrics: dict[str, Any], t: T0GateThresholds) -> GateResult:
    alpha = _metric(metrics, 'alpha_vs_all_in_hold')
    if alpha is None:
        return GateResult(2, 'beat_hold', False, 'missing alpha_vs_all_in_hold')
    if alpha < t.min_alpha_vs_all_in_hold:
        return GateResult(
            2, 'beat_hold', False,
            f'alpha={alpha} < {t.min_alpha_vs_all_in_hold}',
        )
    return GateResult(2, 'beat_hold', True, f'alpha={alpha}')


def _gate3(metrics: dict[str, Any], t: T0GateThresholds) -> GateResult:
    drawdown = _metric(metrics, 'max_drawdown_pct')
    if drawdown is None:
        return GateResult(3, 'drawdown', False, 'missing max_drawdown_pct')
    if drawdown < -t.max_drawdown_abs_pct:
        return GateResult(
            3, 'drawdown', False,
            f'drawdown={drawdown} < -{t.max_drawdown_abs_pct}',
        )
    return GateResult(3, 'drawdown', True, f'drawdown={drawdown}')


def _gate4(metrics: dict[str, Any], trading_days: int, t: T0GateThresholds) -> GateResult:
    trips = _metric(metrics, 'round_trips')
    if trips is None:
        return GateResult(4, 'round_trips', False, 'missing round_trips')
    if trips < t.min_round_trips:
        return GateResult(
            4, 'round_trips', False,
            f'round_trips={int(trips)} < {t.min_round_trips}',
        )
    cap = trading_days * t.max_round_trips_per_day
    if trips > cap:
        return GateResult(
            4, 'round_trips', False,
            f'overtrading: round_trips={int(trips)} > {cap} (days={trading_days})',
        )
    return GateResult(4, 'round_trips', True, f'round_trips={int(trips)}')


def evaluate_gates(
    metrics: dict[str, Any],
    trading_days: int,
    thresholds: T0GateThresholds = T0GateThresholds(),
) -> GateVerdict:
    """Evaluate the four layered gates in order, short-circuiting on failure."""
    checks = (
        _gate1(metrics, thresholds),
        _gate2(metrics, thresholds),
        _gate3(metrics, thresholds),
        _gate4(metrics, trading_days, thresholds),
    )
    results: list[GateResult] = []
    for result in checks:
        results.append(result)
        if not result.passed:
            break
    passed = len(results) == 4 and all(r.passed for r in results)
    gates_passed = sum(1 for r in results if r.passed)
    return GateVerdict(
        passed=passed,
        failed_gate=None if passed else results[-1].gate,
        gates_passed=gates_passed,
        results=tuple(results),
    )
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/test_qlib_gates.py -q`
Expected: `10 passed`.

- [ ] **Step 5: Commit**

```powershell
git add qlib_research/gates.py tests/test_qlib_gates.py
git -c user.name="ouyan" -c user.email="ouyan@users.noreply.github.com" commit -m "feat(qlib): add hard layered gates for T0 research loop"
```

---

### Task 2: 数据分区模块 `qlib_research/holdout.py`

**Files:**
- Create: `qlib_research/holdout.py`
- Test: `tests/test_qlib_holdout.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ResearchWindows(evolution_start: str, evolution_end: str, holdout_start: str, holdout_end: str)`——进化窗口 `[evolution_start, evolution_end)`,holdout `[holdout_start, holdout_end)`,`evolution_end == holdout_start`。
  - `DEFAULT_EVOLUTION_START = '2026-01-01'`、`DEFAULT_HOLDOUT_START = '2026-03-01'`、`DEFAULT_END = '2026-04-01'`
  - `split_windows(start=..., holdout_start=..., end=...) -> ResearchWindows`,`start < holdout_start < end` 否则 `ValueError`。

- [ ] **Step 1: Write the failing tests**

Create `tests/test_qlib_holdout.py`:

```python
import pytest

from qlib_research.holdout import ResearchWindows, split_windows


def test_split_windows_defaults_match_spec():
    windows = split_windows()

    assert windows == ResearchWindows(
        evolution_start='2026-01-01',
        evolution_end='2026-03-01',
        holdout_start='2026-03-01',
        holdout_end='2026-04-01',
    )


def test_split_windows_shifts_as_a_whole():
    windows = split_windows(
        start='2025-10-01', holdout_start='2026-01-01', end='2026-04-01',
    )

    assert windows.evolution_start == '2025-10-01'
    assert windows.evolution_end == '2026-01-01'
    assert windows.holdout_end == '2026-04-01'


def test_split_windows_rejects_inverted_holdout():
    with pytest.raises(ValueError, match='holdout_start'):
        split_windows(start='2026-01-01', holdout_start='2025-12-01', end='2026-04-01')


def test_split_windows_rejects_holdout_past_end():
    with pytest.raises(ValueError, match='end'):
        split_windows(start='2026-01-01', holdout_start='2026-05-01', end='2026-04-01')
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_qlib_holdout.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement holdout**

Create `qlib_research/holdout.py`:

```python
"""Evolution vs holdout window discipline for the T0 research loop.

Iteration (optimize, mutate, evaluate) happens only inside the evolution
window. A candidate graduates solely by passing all gates once more on the
holdout window, which must never feed back into tuning.
"""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_EVOLUTION_START = '2026-01-01'
DEFAULT_HOLDOUT_START = '2026-03-01'
DEFAULT_END = '2026-04-01'


@dataclass(frozen=True)
class ResearchWindows:
    evolution_start: str
    evolution_end: str
    holdout_start: str
    holdout_end: str


def split_windows(
    start: str = DEFAULT_EVOLUTION_START,
    holdout_start: str = DEFAULT_HOLDOUT_START,
    end: str = DEFAULT_END,
) -> ResearchWindows:
    """Split [start, end) into evolution and holdout windows.

    Windows may be shifted, but only as a whole: ``start < holdout_start < end``
    must hold, so the holdout can never be shrunk away or moved before the
    evolution period.
    """
    if not (start < holdout_start):
        raise ValueError(
            f'holdout_start ({holdout_start}) must be after start ({start})'
        )
    if not (holdout_start < end):
        raise ValueError(
            f'holdout_start ({holdout_start}) must be before end ({end})'
        )
    return ResearchWindows(
        evolution_start=start,
        evolution_end=holdout_start,
        holdout_start=holdout_start,
        holdout_end=end,
    )
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/test_qlib_holdout.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```powershell
git add qlib_research/holdout.py tests/test_qlib_holdout.py
git -c user.name="ouyan" -c user.email="ouyan@users.noreply.github.com" commit -m "feat(qlib): add evolution vs holdout window discipline"
```

---

### Task 3: replay 支持 `record=False`、profile 对象与 `days` 指标

**Files:**
- Modify: `scripts/research/t0_qlib_replay.py`
- Test: `tests/test_qlib_replay.py`

**Interfaces:**
- Consumes: `T0StrategyProfile` from `t0/strategy_profiles.py`（已有）。
- Produces（Task 5 依赖）:
  - `run_replay(*, code, start, end, strategy_profile=None, params=None, out_root=..., load_bars=..., run_backtest=..., record=True, profile=None) -> dict`
    - `profile`: 直接传入 `T0StrategyProfile` 对象（实验 profile 用）；给了它就不再按名字查注册表，返回里的 `strategy_profile` 取 `profile.name`。
    - `record=False` 时跳过 `record_research_run`，返回 `record_backend=None, record_path=None`。
  - `summarize_replay_result` 的输出新增 `'days'` 键（取自回测结果的 `days`，即交易日数，Task 1 的 gate 4 需要）。

- [ ] **Step 1: Update existing test + add failing tests**

Modify `tests/test_qlib_replay.py` —— 先在 `test_summarize_replay_result_keeps_cost_and_risk_metrics` 的输入 dict 与期望 dict 中各加一项 `'days': 36`（输入）/ `'days': 36`（期望），然后在文件末尾追加：

```python
def test_run_replay_without_record_skips_recorder(tmp_path: Path):
    bars = [
        _bar('2026-01-05 09:31:00', 100.0),
        _bar('2026-01-05 15:00:00', 101.0, high=101.0, low=99.0),
    ]

    result = run_replay(
        code='600724.SH',
        start='2026-01-01',
        end='2026-04-01',
        strategy_profile='risk_balanced_adaptive_vwap_cost',
        out_root=tmp_path,
        load_bars=lambda code, start=None, end=None: bars,
        record=False,
    )

    assert result['record_backend'] is None
    assert result['record_path'] is None
    assert not list(tmp_path.rglob('*.jsonl'))


def test_run_replay_accepts_profile_object(tmp_path: Path):
    from t0.strategy_profiles import T0StrategyProfile, get_t0_strategy_profile
    from dataclasses import replace

    parent = get_t0_strategy_profile('risk_balanced_adaptive_vwap_cost')
    exp_profile: T0StrategyProfile = replace(
        parent, name='exp/low_base', base_params=parent.build_base_params(
            {'base_position_pct': 0.45},
        ),
    )
    bars = [
        _bar('2026-01-05 09:31:00', 100.0),
        _bar('2026-01-05 15:00:00', 101.0, high=101.0, low=99.0),
    ]

    result = run_replay(
        code='600724.SH',
        start='2026-01-01',
        end='2026-04-01',
        profile=exp_profile,
        out_root=tmp_path,
        load_bars=lambda code, start=None, end=None: bars,
        record=False,
    )

    assert result['strategy_profile'] == 'exp/low_base'
    assert result['params']['base_position_pct'] == 0.45


def test_summarize_replay_result_includes_days():
    summary = summarize_replay_result({'days': 36})

    assert summary['days'] == 36
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_qlib_replay.py -q`
Expected: 新 3 个测试 FAIL(`record` 未定义 / `profile` 未定义 / summary 无 `days`)，旧测试因 `days` 键也 FAIL。

- [ ] **Step 3: Implement replay changes**

In `scripts/research/t0_qlib_replay.py`:

1. `REPLAY_METRIC_KEYS` 末尾加 `'days'`。
2. `run_replay` 签名改为：

```python
def run_replay(
    *,
    code: str,
    start: str,
    end: str,
    strategy_profile: str | None = None,
    params: dict[str, Any] | None = None,
    out_root: str | Path = 'data/qlib_research',
    load_bars: BarLoader = _default_load_bars,
    run_backtest: T0BacktestRunner = _default_run_backtest,
    record: bool = True,
    profile: Any = None,
) -> dict[str, Any]:
```

3. 函数体前两行改为：

```python
    if profile is None:
        from t0.strategy_profiles import get_t0_strategy_profile

        profile = get_t0_strategy_profile(strategy_profile)
```

4. 记录段改为：

```python
    if record:
        record_result = record_research_run(
            ResearchRun(
                experiment='t0-qlib-replay',
                recorder=code,
                params={
                    'code': code,
                    'start': start,
                    'end': end,
                    'strategy_profile': profile.name,
                    'strategy_params': merged_params,
                },
                metrics=metrics,
                artifacts={
                    'daily': result.get('daily', []),
                    'trades': result.get('trades', []),
                },
            ),
            root=out_root,
        )
        record_backend: str | None = record_result['backend']
        record_path: str | None = record_result.get('path')
    else:
        record_backend = None
        record_path = None
```

5. 返回 dict 里 `'record_backend': record_backend, 'record_path': record_path`（替换原来的 `record['backend']` / `record.get('path')`）。

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/test_qlib_replay.py -q`
Expected: `6 passed`。

- [ ] **Step 5: Commit**

```powershell
git add scripts/research/t0_qlib_replay.py tests/test_qlib_replay.py
git -c user.name="ouyan" -c user.email="ouyan@users.noreply.github.com" commit -m "feat(qlib): let replay skip recording and accept profile objects"
```

---

### Task 4: 变异算子 `qlib_research/mutations.py`

**Files:**
- Create: `qlib_research/mutations.py`
- Test: `tests/test_qlib_mutations.py`

**Interfaces:**
- Consumes: `T0StrategyProfile`、`get_t0_strategy_profile`（`t0/strategy_profiles.py`);`ResearchBudget` 不需要。
- Produces（Task 5 依赖）:
  - `SIGNAL_MODES = ('band', 'hybrid', 'vwap_deviation', 'adaptive_vwap', 'hybrid_adaptive')`
  - `EXECUTION_STYLES = ('market', 'next_bar')`
  - `Mutation(profile: T0StrategyProfile, params: dict, hypothesis: str, parent: str)`（frozen dataclass)
  - `mutate_params(profile_name: str, overrides: dict, hypothesis: str) -> Mutation` —— profile 不变，overrides 进 `params`
  - `compose_profile(slug: str, base_on: str, overrides: dict, hypothesis: str, description: str = '') -> Mutation` —— 新 profile（名字 `exp/<slug>`,overrides 烘进 `base_params`),`params={}`，并注册进进程级实验注册表
  - `get_experimental_profile(name: str) -> T0StrategyProfile`
  - 校验：`signal_mode` / `execution_style` 必须在词汇表内；`base_position_pct`、`t_shares_pct`、`take_profit_pct`、`stop_loss_pct`、`high_band`、`low_band`、`vwap_deviation_pct` 必须在 (0, 1);`hypothesis` 非空；`slug` 非空且无空白字符。违规抛 `ValueError`。

- [ ] **Step 1: Write the failing tests**

Create `tests/test_qlib_mutations.py`:

```python
import pytest

from qlib_research.mutations import (
    EXECUTION_STYLES,
    SIGNAL_MODES,
    compose_profile,
    get_experimental_profile,
    mutate_params,
)


def test_vocab_matches_portfolio_capabilities():
    assert SIGNAL_MODES == (
        'band', 'hybrid', 'vwap_deviation', 'adaptive_vwap', 'hybrid_adaptive',
    )
    assert EXECUTION_STYLES == ('market', 'next_bar')


def test_mutate_params_keeps_parent_profile():
    mutation = mutate_params(
        'risk_balanced_adaptive_vwap_cost',
        {'take_profit_pct': 0.5, 'stop_loss_pct': 0.7},
        hypothesis='faster exits should stabilize the cost path',
    )

    assert mutation.profile.name == 'risk_balanced_adaptive_vwap_cost'
    assert mutation.params == {'take_profit_pct': 0.5, 'stop_loss_pct': 0.7}
    assert mutation.parent == 'risk_balanced_adaptive_vwap_cost'
    assert 'faster exits' in mutation.hypothesis


def test_mutate_params_requires_hypothesis():
    with pytest.raises(ValueError, match='hypothesis'):
        mutate_params('adaptive_vwap_cost', {'take_profit_pct': 0.5}, hypothesis='')


def test_mutate_params_rejects_unknown_signal_mode():
    with pytest.raises(ValueError, match='signal_mode'):
        mutate_params(
            'adaptive_vwap_cost',
            {'signal_mode': 'magic'},
            hypothesis='invalid mode must fail',
        )


def test_mutate_params_rejects_out_of_range_pct():
    with pytest.raises(ValueError, match='take_profit_pct'):
        mutate_params(
            'adaptive_vwap_cost',
            {'take_profit_pct': 1.5},
            hypothesis='out of range pct must fail',
        )


def test_compose_profile_bakes_overrides_and_registers():
    mutation = compose_profile(
        slug='low_base_next_bar',
        base_on='adaptive_vwap_cost',
        overrides={
            'base_position_pct': 0.45,
            'execution_style': 'next_bar',
            'signal_mode': 'hybrid_adaptive',
        },
        hypothesis='lower base plus next-bar fills should cut drawdown',
    )

    assert mutation.profile.name == 'exp/low_base_next_bar'
    assert mutation.profile.base_params['base_position_pct'] == 0.45
    assert mutation.profile.base_params['execution_style'] == 'next_bar'
    assert mutation.params == {}
    assert mutation.parent == 'adaptive_vwap_cost'
    assert get_experimental_profile('exp/low_base_next_bar') is mutation.profile


def test_compose_profile_rejects_bad_slug():
    with pytest.raises(ValueError, match='slug'):
        compose_profile(
            slug='has space',
            base_on='adaptive_vwap_cost',
            overrides={},
            hypothesis='bad slug must fail',
        )


def test_compose_profile_rejects_unknown_execution_style():
    with pytest.raises(ValueError, match='execution_style'):
        compose_profile(
            slug='bad_style',
            base_on='adaptive_vwap_cost',
            overrides={'execution_style': 'vwap'},
            hypothesis='bad style must fail',
        )


def test_get_experimental_profile_unknown_raises_key_error():
    with pytest.raises(KeyError):
        get_experimental_profile('exp/does_not_exist')
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_qlib_mutations.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement mutations**

Create `qlib_research/mutations.py`:

```python
"""Mutation operators for the T0 loop-agent research closed loop.

Two sanctioned mutation levels (spec: 变异权限 1+2):

1. parameter-level: new combinations inside an existing profile's vocabulary;
2. profile-composition: new ``exp/`` profiles assembled from the existing
   signal/execution vocabulary, kept in a process-level experimental registry.

Logic-level mutation (new signal code) is deliberately not offered here — it
requires human review before entering ``t0/strategy_profiles.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from t0.strategy_profiles import T0StrategyProfile, get_t0_strategy_profile


SIGNAL_MODES = ('band', 'hybrid', 'vwap_deviation', 'adaptive_vwap', 'hybrid_adaptive')
EXECUTION_STYLES = ('market', 'next_bar')

_PCT_PARAMS = (
    'base_position_pct',
    't_shares_pct',
    'take_profit_pct',
    'stop_loss_pct',
    'high_band',
    'low_band',
    'vwap_deviation_pct',
)

_EXPERIMENTAL_PROFILES: dict[str, T0StrategyProfile] = {}


@dataclass(frozen=True)
class Mutation:
    profile: T0StrategyProfile
    params: dict[str, Any]
    hypothesis: str
    parent: str


def _validate(hypothesis: str, overrides: dict[str, Any]) -> None:
    if not (hypothesis or '').strip():
        raise ValueError('hypothesis must be non-empty (no directionless search)')
    mode = overrides.get('signal_mode')
    if mode is not None and mode not in SIGNAL_MODES:
        raise ValueError(f'signal_mode must be one of {SIGNAL_MODES}, got {mode!r}')
    style = overrides.get('execution_style')
    if style is not None and style not in EXECUTION_STYLES:
        raise ValueError(
            f'execution_style must be one of {EXECUTION_STYLES}, got {style!r}'
        )
    for key in _PCT_PARAMS:
        value = overrides.get(key)
        if value is not None and not (0.0 < float(value) < 1.0):
            raise ValueError(f'{key} must be in (0, 1), got {value!r}')


def mutate_params(
    profile_name: str,
    overrides: dict[str, Any],
    hypothesis: str,
) -> Mutation:
    """Parameter-level mutation: same profile, new parameter combination."""
    _validate(hypothesis, overrides)
    profile = get_t0_strategy_profile(profile_name)
    return Mutation(
        profile=profile,
        params=dict(overrides),
        hypothesis=hypothesis,
        parent=profile.name,
    )


def compose_profile(
    slug: str,
    base_on: str,
    overrides: dict[str, Any],
    hypothesis: str,
    description: str = '',
) -> Mutation:
    """Profile-composition mutation: new exp/ profile from existing vocabulary."""
    token = (slug or '').strip()
    if not token or any(ch.isspace() for ch in token):
        raise ValueError(f'slug must be non-empty without whitespace, got {slug!r}')
    _validate(hypothesis, overrides)
    parent = get_t0_strategy_profile(base_on)
    profile = replace(
        parent,
        name=f'exp/{token}',
        display_name=f'Experiment: {token}',
        description=description or hypothesis,
        base_params=parent.build_base_params(overrides),
    )
    _EXPERIMENTAL_PROFILES[profile.name] = profile
    return Mutation(
        profile=profile,
        params={},
        hypothesis=hypothesis,
        parent=parent.name,
    )


def get_experimental_profile(name: str) -> T0StrategyProfile:
    try:
        return _EXPERIMENTAL_PROFILES[name]
    except KeyError as exc:
        raise KeyError(f'unknown experimental T0 profile: {name}') from exc
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/test_qlib_mutations.py -q`
Expected: `9 passed`。

- [ ] **Step 5: Commit**

```powershell
git add qlib_research/mutations.py tests/test_qlib_mutations.py
git -c user.name="ouyan" -c user.email="ouyan@users.noreply.github.com" commit -m "feat(qlib): add sanctioned T0 mutation operators"
```

---

### Task 5: 榜单执行器 `scripts/research/t0_qlib_leaderboard.py`

**Files:**
- Create: `scripts/research/t0_qlib_leaderboard.py`
- Test: `tests/test_qlib_leaderboard.py`

**Interfaces:**
- Consumes:
  - `evaluate_gates`、`T0GateThresholds`、`ResearchBudget`(Task 1)
  - `ResearchWindows`、`split_windows`(Task 2)
  - `run_replay`(Task 3 版，支持 `profile=` / `record=False`，metrics 含 `days`)
  - `Mutation`(Task 4);`_default_load_bars`(`scripts/research/t0_qlib_spike.py`)
  - `ResearchRun`、`record_research_run`(`qlib_research/recorder.py`)
- Produces:
  - `LeaderboardCandidate(code: str, profile: T0StrategyProfile, params: dict, hypothesis: str = '', parent: str = '', source: str = 'spike')`
  - `candidate_from_mutation(code: str, mutation: Mutation) -> LeaderboardCandidate`
  - `load_spike_candidates(records_path: str | Path) -> list[LeaderboardCandidate]` —— 读 spike JSONL，取每个 `(code, strategy_profile)` 最后一条含 `artifacts.best_params` 的记录
  - `run_leaderboard(*, candidates=None, records_path='data/qlib_research/records/t0-qlib-spike.jsonl', windows=split_windows(), budget=ResearchBudget(), thresholds=T0GateThresholds(), out_root='data/qlib_research', load_bars=_default_load_bars, run_backtest=<同 replay 的默认>) -> dict`
  - 榜单行（dict）含：`code`、`strategy_profile`、`params`、`hypothesis`、`parent`、`source`、`metrics`、`gates_passed`、`passed`、`failed_gate`、`gate_results`(list of dict)、`holdout_metrics`(None 或 dict)、`graduated`(True/False/None)
  - 排序 key（降序）:`(gates_passed, metrics.cost_reduction_pct, metrics.alpha_vs_all_in_hold, metrics.max_drawdown_pct)`，缺失指标按极小值处理
  - 返回：`{'count', 'rows', 'evaluations_used', 'evaluations_dropped', 'windows': asdict(windows), 'record_backend', 'record_path'}`
  - 预算语义：一次 `run_replay` 调用 = 1 次评估；进化阶段截断候选，holdout 阶段预算耗尽则剩余 survivor `graduated=None`；截断/耗尽数量都在返回与记录里如实体现（不许静默）。

- [ ] **Step 1: Write the failing tests**

Create `tests/test_qlib_leaderboard.py`:

```python
import json
from pathlib import Path

from qlib_research.gates import ResearchBudget
from qlib_research.holdout import split_windows
from scripts.research.t0_qlib_leaderboard import (
    LeaderboardCandidate,
    candidate_from_mutation,
    load_spike_candidates,
    run_leaderboard,
)
from scripts.research.t0_qlib_replay import REPLAY_METRIC_KEYS
from t0.strategy_profiles import get_t0_strategy_profile


def _result(cost: float, alpha: float, trips: int, drawdown: float = -5.0, days: int = 40):
    return {
        'final_equity': 1_000_000.0,
        'total_return_pct': 0.0,
        'cost_reduction_pct': cost,
        'min_cost_reduction_pct': -0.2,
        'cost_reduction_positive_days_pct': 70.0,
        'alpha_vs_all_in_hold': alpha,
        'max_drawdown_pct': drawdown,
        'round_trips': trips,
        'win_rate': 60.0,
        'days': days,
        'daily': [],
        'trades': [],
    }


def _candidate(code: str, profile: str = 'adaptive_vwap_cost'):
    return LeaderboardCandidate(
        code=code,
        profile=get_t0_strategy_profile(profile),
        params={'take_profit_pct': 0.55},
        hypothesis='test candidate',
    )


def test_candidate_from_mutation_carries_hypothesis():
    from qlib_research.mutations import mutate_params

    mutation = mutate_params(
        'adaptive_vwap_cost', {'take_profit_pct': 0.5}, hypothesis='faster exits',
    )
    candidate = candidate_from_mutation('300951.SZ', mutation)

    assert candidate.code == '300951.SZ'
    assert candidate.hypothesis == 'faster exits'
    assert candidate.parent == 'adaptive_vwap_cost'
    assert candidate.source == 'mutation'


def test_load_spike_candidates_takes_latest_best_params(tmp_path: Path):
    records = tmp_path / 't0-qlib-spike.jsonl'
    rows = [
        {
            'experiment': 't0-qlib-spike',
            'recorder': '300951.SZ',
            'params': {'code': '300951.SZ', 'strategy_profile': 'adaptive_vwap_cost'},
            'metrics': {},
            'artifacts': {'best_params': {'take_profit_pct': 0.55}},
        },
        {
            'experiment': 't0-qlib-spike',
            'recorder': '300951.SZ',
            'params': {'code': '300951.SZ', 'strategy_profile': 'adaptive_vwap_cost'},
            'metrics': {},
            'artifacts': {'best_params': {'take_profit_pct': 0.75}},
        },
        {
            'experiment': 't0-qlib-spike',
            'recorder': '300951.SZ',
            'params': {'code': '300951.SZ'},  # no profile -> skipped
            'metrics': {},
            'artifacts': {'best_params': {'take_profit_pct': 0.9}},
        },
    ]
    records.write_text(
        '\n'.join(json.dumps(r) for r in rows), encoding='utf-8',
    )

    candidates = load_spike_candidates(records)

    assert len(candidates) == 1
    assert candidates[0].params == {'take_profit_pct': 0.75}
    assert candidates[0].source == 'spike'


def test_run_leaderboard_ranks_by_gates_then_cost(tmp_path: Path):
    outcomes = {
        'PASS.SH': _result(cost=0.8, alpha=500.0, trips=61),
        'FAIL1.SH': _result(cost=-0.3, alpha=500.0, trips=61),
        'FAIL2.SH': _result(cost=0.9, alpha=-10.0, trips=61),
    }
    candidates = [_candidate(code) for code in outcomes]

    result = run_leaderboard(
        candidates=candidates,
        windows=split_windows(),
        out_root=tmp_path,
        load_bars=lambda code, start=None, end=None: [{'date': '2026-01-05'}],
        run_backtest=lambda code, bars, **params: outcomes[code],
    )

    assert result['count'] == 3
    order = [row['code'] for row in result['rows']]
    assert order == ['PASS.SH', 'FAIL2.SH', 'FAIL1.SH']
    top = result['rows'][0]
    assert top['passed'] is True
    assert top['gates_passed'] == 4
    assert top['graduated'] is True  # holdout replay passes too
    assert top['holdout_metrics']['cost_reduction_pct'] == 0.8
    fail2 = result['rows'][1]
    assert fail2['passed'] is False
    assert fail2['failed_gate'] == 2
    assert fail2['graduated'] is None
    assert result['evaluations_used'] == 4  # 3 evolution + 1 holdout
    assert result['record_backend'] == 'jsonl'
    payload = json.loads(
        Path(result['record_path']).read_text(encoding='utf-8').splitlines()[-1]
    )
    assert payload['experiment'] == 't0-qlib-leaderboard'
    assert payload['metrics']['survivors'] == 1
    assert payload['metrics']['graduated'] == 1


def test_run_leaderboard_respects_budget(tmp_path: Path):
    candidates = [_candidate(f'C{i}.SH') for i in range(5)]

    result = run_leaderboard(
        candidates=candidates,
        budget=ResearchBudget(max_evaluations=2),
        out_root=tmp_path,
        load_bars=lambda code, start=None, end=None: [{'date': '2026-01-05'}],
        run_backtest=lambda code, bars, **params: _result(0.8, 500.0, 61),
    )

    assert result['count'] == 2
    assert result['evaluations_used'] == 2  # 2 evolution, no budget left for holdout
    assert result['evaluations_dropped'] == 3
    assert all(row['graduated'] is None for row in result['rows'])


def test_run_leaderboard_marks_holdout_failure(tmp_path: Path):
    calls = {'n': 0}

    def run_backtest(code, bars, **params):
        calls['n'] += 1
        if calls['n'] == 1:  # evolution window passes
            return _result(cost=0.8, alpha=500.0, trips=61)
        return _result(cost=-0.5, alpha=-100.0, trips=61)  # holdout fails gate 1

    result = run_leaderboard(
        candidates=[_candidate('X.SH')],
        out_root=tmp_path,
        load_bars=lambda code, start=None, end=None: [{'date': '2026-01-05'}],
        run_backtest=run_backtest,
    )

    row = result['rows'][0]
    assert row['passed'] is True
    assert row['graduated'] is False
    assert row['holdout_metrics']['cost_reduction_pct'] == -0.5
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_qlib_leaderboard.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement leaderboard**

Create `scripts/research/t0_qlib_leaderboard.py`:

```python
"""One deterministic iteration of the T0 loop-agent research closed loop.

Replays each candidate on the evolution window, applies the hard gates,
replays survivors once on the holdout window (graduation), and records the
full leaderboard. Orchestration-only: execution truth lives in
``t0/portfolio.py``; selection lives in ``qlib_research/gates.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qlib_research.gates import ResearchBudget, T0GateThresholds, evaluate_gates
from qlib_research.holdout import ResearchWindows, split_windows
from qlib_research.recorder import ResearchRun, record_research_run
from scripts.research.t0_qlib_replay import run_replay
from scripts.research.t0_qlib_spike import _default_load_bars
from t0.strategy_profiles import T0StrategyProfile, get_t0_strategy_profile


@dataclass(frozen=True)
class LeaderboardCandidate:
    code: str
    profile: T0StrategyProfile
    params: dict[str, Any]
    hypothesis: str = ''
    parent: str = ''
    source: str = 'spike'


def candidate_from_mutation(code: str, mutation) -> LeaderboardCandidate:
    return LeaderboardCandidate(
        code=code,
        profile=mutation.profile,
        params=dict(mutation.params),
        hypothesis=mutation.hypothesis,
        parent=mutation.parent,
        source='mutation',
    )


def load_spike_candidates(records_path: str | Path) -> list[LeaderboardCandidate]:
    path = Path(records_path)
    if not path.exists():
        return []
    latest: dict[tuple[str, str], LeaderboardCandidate] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        params = payload.get('params') or {}
        artifacts = payload.get('artifacts') or {}
        profile_name = params.get('strategy_profile')
        best_params = artifacts.get('best_params')
        code = params.get('code') or payload.get('recorder')
        if not (profile_name and best_params and code):
            continue
        latest[(code, profile_name)] = LeaderboardCandidate(
            code=code,
            profile=get_t0_strategy_profile(profile_name),
            params=dict(best_params),
            source='spike',
        )
    return list(latest.values())


def _sort_key(row: dict[str, Any]) -> tuple:
    metrics = row['metrics']
    return (
        row['gates_passed'],
        float(metrics.get('cost_reduction_pct') or float('-inf')),
        float(metrics.get('alpha_vs_all_in_hold') or float('-inf')),
        float(metrics.get('max_drawdown_pct') or float('-inf')),
    )


def _replay_candidate(
    candidate: LeaderboardCandidate,
    start: str,
    end: str,
    load_bars: Callable,
    run_backtest: Callable,
) -> dict[str, Any]:
    return run_replay(
        code=candidate.code,
        start=start,
        end=end,
        profile=candidate.profile,
        params=candidate.params,
        load_bars=load_bars,
        run_backtest=run_backtest,
        record=False,
    )


def run_leaderboard(
    *,
    candidates: list[LeaderboardCandidate] | None = None,
    records_path: str | Path = 'data/qlib_research/records/t0-qlib-spike.jsonl',
    windows: ResearchWindows = split_windows(),
    budget: ResearchBudget = ResearchBudget(),
    thresholds: T0GateThresholds = T0GateThresholds(),
    out_root: str | Path = 'data/qlib_research',
    load_bars: Callable[..., list[dict[str, Any]]] = _default_load_bars,
    run_backtest: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if run_backtest is None:
        from scripts.research.t0_qlib_replay import _default_run_backtest

        run_backtest = _default_run_backtest
    pool = list(candidates) if candidates is not None else load_spike_candidates(records_path)

    used = 0
    rows: list[dict[str, Any]] = []
    for candidate in pool:
        if used >= budget.max_evaluations:
            break
        replay = _replay_candidate(
            candidate, windows.evolution_start, windows.evolution_end,
            load_bars, run_backtest,
        )
        used += 1
        metrics = replay['metrics']
        verdict = evaluate_gates(
            metrics, trading_days=int(metrics.get('days') or 0), thresholds=thresholds,
        )
        rows.append({
            'code': candidate.code,
            'strategy_profile': replay['strategy_profile'],
            'params': replay['params'],
            'hypothesis': candidate.hypothesis,
            'parent': candidate.parent,
            'source': candidate.source,
            'metrics': metrics,
            'gates_passed': verdict.gates_passed,
            'passed': verdict.passed,
            'failed_gate': verdict.failed_gate,
            'gate_results': [asdict(r) for r in verdict.results],
            'holdout_metrics': None,
            'graduated': None,
        })
    dropped = len(pool) - len(rows)

    for row in rows:
        if not row['passed']:
            continue
        if used >= budget.max_evaluations:
            break  # remaining survivors stay graduated=None, honestly reported
        holdout_candidate = LeaderboardCandidate(
            code=row['code'],
            profile=get_t0_strategy_profile(row['strategy_profile'])
            if not row['strategy_profile'].startswith('exp/')
            else _experimental_profile(row),
            params=row['params'],
        )
        holdout = _replay_candidate(
            holdout_candidate, windows.holdout_start, windows.holdout_end,
            load_bars, run_backtest,
        )
        used += 1
        metrics = holdout['metrics']
        verdict = evaluate_gates(
            metrics, trading_days=int(metrics.get('days') or 0), thresholds=thresholds,
        )
        row['holdout_metrics'] = metrics
        row['graduated'] = verdict.passed

    rows.sort(key=_sort_key, reverse=True)
    survivors = sum(1 for row in rows if row['passed'])
    graduated = sum(1 for row in rows if row['graduated'] is True)

    record = record_research_run(
        ResearchRun(
            experiment='t0-qlib-leaderboard',
            recorder='t0-leaderboard',
            params={
                'windows': asdict(windows),
                'budget': asdict(budget),
                'thresholds': asdict(thresholds),
            },
            metrics={
                'candidates': len(rows),
                'survivors': survivors,
                'graduated': graduated,
                'evaluations_used': used,
                'evaluations_dropped': dropped,
            },
            artifacts={'rows': rows},
        ),
        root=out_root,
    )

    return {
        'count': len(rows),
        'rows': rows,
        'evaluations_used': used,
        'evaluations_dropped': dropped,
        'windows': asdict(windows),
        'record_backend': record['backend'],
        'record_path': record.get('path'),
    }


def _experimental_profile(row: dict[str, Any]) -> T0StrategyProfile:
    from qlib_research.mutations import get_experimental_profile

    return get_experimental_profile(row['strategy_profile'])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--records-path',
                        default='data/qlib_research/records/t0-qlib-spike.jsonl')
    parser.add_argument('--start', default='2026-01-01')
    parser.add_argument('--holdout-start', default='2026-03-01')
    parser.add_argument('--end', default='2026-04-01')
    parser.add_argument('--max-evaluations', type=int, default=12)
    parser.add_argument('--out-root', default='data/qlib_research')
    args = parser.parse_args()

    result = run_leaderboard(
        records_path=args.records_path,
        windows=split_windows(args.start, args.holdout_start, args.end),
        budget=ResearchBudget(max_evaluations=args.max_evaluations),
        out_root=args.out_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/test_qlib_leaderboard.py -q`
Expected: `5 passed`。

- [ ] **Step 5: Commit**

```powershell
git add scripts/research/t0_qlib_leaderboard.py tests/test_qlib_leaderboard.py
git -c user.name="ouyan" -c user.email="ouyan@users.noreply.github.com" commit -m "feat(qlib): add gated T0 leaderboard executor with holdout graduation"
```

---

### Task 6: t0-research skill playbook

**Files:**
- Create: `.claude/skills/t0-research/SKILL.md`
- Test: `tests/test_t0_research_skill.py`

**Interfaces:**
- Consumes: Task 1-5 的全部产物（skill 是它们的操作手册）。
- Produces: agent 可调用的 skill;`data/qlib_research/journal.md` 的模板（内嵌在 SKILL.md 中，首轮由 agent 创建）。

- [ ] **Step 1: Write the failing test**

Create `tests/test_t0_research_skill.py`:

```python
from pathlib import Path

SKILL_PATH = Path(__file__).resolve().parents[1] / '.claude' / 'skills' / 't0-research' / 'SKILL.md'


def test_t0_research_skill_exists_with_frontmatter():
    text = SKILL_PATH.read_text(encoding='utf-8')

    assert text.startswith('---')
    assert 'name: t0-research' in text
    assert 'description:' in text


def test_t0_research_skill_encodes_the_loop_discipline():
    text = SKILL_PATH.read_text(encoding='utf-8')

    # 记忆层：先读再写研究日志
    assert 'journal.md' in text
    # 反过拟合铁律：预算、holdout、关卡在代码
    assert '12' in text  # default evaluation budget
    assert 'holdout' in text
    assert 'evaluate_gates' in text or 'gates.py' in text
    # 变异权限边界：1+2，且必须带假设
    assert 'mutate_params' in text
    assert 'compose_profile' in text
    assert 'exp/' in text
    assert 'hypothesis' in text.lower() or '假设' in text
    # 毕业不等于上线
    assert 't0/strategy_profiles.py' in text
```

- [ ] **Step 2: Run test to verify RED**

Run: `python -m pytest tests/test_t0_research_skill.py -q`
Expected: FAIL(`SKILL.md` 不存在）。

- [ ] **Step 3: Write the skill**

Create `.claude/skills/t0-research/SKILL.md`:

````markdown
---
name: t0-research
description: Use when iterating on T0 (做T) strategy research — running gated leaderboards, mutating strategy profiles, and maintaining the research journal. Drives one loop iteration of the BiYingTong T0 evolution closed loop.
---

# T0 Research Loop

You are the mutation/judgment layer of an evolutionary research loop. The
**selection layer is code, not you**: `qlib_research/gates.py` (hard gates),
`qlib_research/holdout.py` (window discipline), and the evaluation budget
decide what survives. Your conclusions must cite recorded metrics only —
never impressions.

## Iron rules (anti-overfitting)

1. Gates are evaluated by `evaluate_gates` in code. You cannot argue a
   candidate past a failed gate.
2. Iterate only inside the evolution window (default 2026-01-01 → 2026-03-01).
   The holdout window (2026-03-01 → 2026-04-01) gets exactly one replay per
   survivor — never tune against it.
3. Evaluation budget: **12** backtest evaluations per iteration (evolution +
   holdout replays both count). Plan mutations to fit.
4. Every mutation must carry a written hypothesis. No directionless search.
5. Graduation ≠ shipping. Graduated `exp/` profiles enter
   `t0/strategy_profiles.py` only via human approval.
6. Never modify `t0/portfolio.py` or the shipped profile registry.

## One iteration

1. **Read memory**: `data/qlib_research/journal.md` (create from the template
   below on first run) plus the last record of
   `data/qlib_research/records/t0-qlib-leaderboard.jsonl`.
2. **Propose mutations** (≤ budget) from the journal's 下轮计划 section, using
   only the two sanctioned operators in `qlib_research/mutations.py`:
   - `mutate_params(profile_name, overrides, hypothesis)` — parameter-level
   - `compose_profile(slug, base_on, overrides, hypothesis)` — profile
     composition from existing vocab, names must be `exp/<slug>`
3. **Run the leaderboard** (evolution window + holdout graduation):

   ```powershell
   python -c "import json; from qlib_research.mutations import mutate_params, compose_profile; from scripts.research.t0_qlib_leaderboard import candidate_from_mutation, run_leaderboard; mutations = [...]; result = run_leaderboard(candidates=[candidate_from_mutation('<code>', m) for m in mutations]); print(json.dumps(result, ensure_ascii=False, indent=2, default=str))"
   ```

   Or for the spike-derived baseline pool:
   `python scripts/research/t0_qlib_leaderboard.py --max-evaluations 12`
4. **Read diagnostics**: for each row — `gates_passed`, `failed_gate`,
   `gate_results[].detail`, `graduated`, `holdout_metrics`.
5. **Update `journal.md`** (all four sections, citing run evidence).
6. **Report to the human**: who was eliminated (and at which gate), who came
   closest, who graduated. Recommend — never perform — registry promotion.

## journal.md template

```markdown
# T0 研究日志

## 当前认知
<哪类票适合哪类 profile，附榜单记录证据>

## 已否定的假设
<假设文本 + 否决证据（卡在哪关、detail）>

## 毕业生名单
<(code, profile, params) + 进化/holdout 两个窗口完整指标>

## 下轮计划
<基于当前认知的变异方向，供下一轮 loop 使用>
```
````

- [ ] **Step 4: Run test to verify GREEN**

Run: `python -m pytest tests/test_t0_research_skill.py -q`
Expected: `2 passed`。

- [ ] **Step 5: Commit**

```powershell
git add .claude/skills/t0-research/SKILL.md tests/test_t0_research_skill.py
git -c user.name="ouyan" -c user.email="ouyan@users.noreply.github.com" commit -m "feat(t0): add t0-research loop agent skill playbook"
```

---

### Task 7: 全量验证与真实数据 smoke

**Files:**
- No new files.

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
python -m pytest tests/test_qlib_gates.py tests/test_qlib_holdout.py tests/test_qlib_replay.py tests/test_qlib_mutations.py tests/test_qlib_leaderboard.py tests/test_t0_research_skill.py -q
```

Expected: all pass（约 30 个）。

- [ ] **Step 2: Run full t0/qlib regression**

Run: `python -m pytest tests/ -q -k "t0 or qlib"`
Expected: 全部通过，无回归（此前基线 143 passed)。

- [ ] **Step 3: Real-data leaderboard smoke（spike 候选池）**

Run:

```powershell
python scripts/research/t0_qlib_leaderboard.py --max-evaluations 12
```

Expected:
- exit 0;`count >= 1`;`evaluations_used <= 12`
- 每行含 `gates_passed` / `failed_gate` / `gate_results` 诊断
- 若有 `passed=true` 的行，其 `holdout_metrics` 非空且 `graduated` 为 true/false
- `data/qlib_research/records/t0-qlib-leaderboard.jsonl` 新增一条记录

- [ ] **Step 4: Real-data mutation smoke（profile 组合级变异走完整毕业路径）**

Run:

```powershell
python -c "import json; from qlib_research.mutations import compose_profile; from scripts.research.t0_qlib_leaderboard import candidate_from_mutation, run_leaderboard; m = compose_profile('smoke_low_base', base_on='risk_balanced_adaptive_vwap_cost', overrides={'base_position_pct': 0.45}, hypothesis='lower base should cut drawdown on 600724'); result = run_leaderboard(candidates=[candidate_from_mutation('600724.SH', m)]); print(json.dumps({'rows': [{'code': r['code'], 'profile': r['strategy_profile'], 'passed': r['passed'], 'failed_gate': r['failed_gate'], 'graduated': r['graduated']} for r in result['rows']]}, ensure_ascii=False, indent=2))"
```

Expected: exit 0；一行 `profile='exp/smoke_low_base'`,`passed`/`graduated` 字段齐全（true/false 均可，取决于真实数据）。

- [ ] **Step 5: Check git status**

Run: `git status --short -b`
Expected: 只有预期文件已提交；`AGENTS.md` 保持 untracked 未 stage;`data/qlib_research/` 不出现在 status。

- [ ] **Step 6: Push branch**

```powershell
git push origin codex-a-share-t0
```

Expected: push succeeds。
