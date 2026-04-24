# Batch B — Migrate BacktestRunner to vnpy.BacktestingEngine (Parallel Path)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** 兑现"框架先用"原则 — 把 LLM 回测主路径从手写 `BacktestRunner` 迁移到 `vnpy_portfoliostrategy.BacktestingEngine`，复用 vnpy 的 position tracking + `calculate_statistics()` + 撮合/佣金模型。旧路径先保留并存，新路径跟旧的**数值对齐**后才能切换。

**Strategy:** 新建 `VnpyBacktestRunner` 类，复用既有的 `LLMPortfolioStrategy`（已继承 `StrategyTemplate`，只是没被调用）。API 通过一个 toggle / 新端点选路径。旧 `BacktestRunner` 保留直到数值对齐验证通过，再独立任务删除。

**CRITICAL — 风险：**
- 新旧两条路径可能因撮合模型、T+1 细节、费用计算差异导致 result 不同
- vnpy 的 `calculate_statistics()` 跟我们手写 `stats.py` 对 Sharpe/MaxDD 的定义可能不一致（年化因子、benchmark-rel/absolute）
- P3-A 的 `daily_records / trades / thinking` 字段必须仍能生成（不能丢前端对接能力）
- 616+ 个现存测试基于旧 runner — 不能破坏

**Mitigation:**
- 数值 parity test：相同输入 + 同一 MockLLM script 跑两路径 → 对比关键 stat 在容差内
- 旧路径保留
- 新 runner 输出同样的 `BacktestResult` 形状（包含 `kind`、`daily_records`、`trades`、`thinking`）

---

## File Structure

**新增：**
- `backtest/vnpy_runner.py` — `VnpyBacktestRunner` 类
- `backtest/strategy.py` — 可能需要补 `on_bars` 的完整逻辑（目前是半成品）
- `api/backtests.py` — 新 endpoint `POST /api/backtests/vnpy` 或在现有 POST 加 `?engine=vnpy` 参数
- `tests/test_vnpy_runner.py` — 专门测 vnpy 路径
- `tests/test_runner_parity.py` — 对比新旧路径数值一致性

**不动：**
- `backtest/runner.py`（旧 BacktestRunner 保留）
- `backtest/book.py`（保留，新路径不用）
- `backtest/stats.py`（保留，老路径依赖；新路径用 `engine.calculate_statistics()`）
- `backtest/rule_runner.py`（Rule mode 独立，不在本批范围）

---

### Task 1: Survey + design confirmation

**Files:** 仅读，无改动 + 写一份简短 Design Memo

探查：
1. `backtest/strategy.py::LLMPortfolioStrategy` 当前状态 —`on_init/on_start/on_bars/_process_bars` 具体做什么
2. `vnpy_portfoliostrategy.BacktestingEngine`：`load_data`/`add_strategy`/`run_backtesting`/`calculate_result`/`calculate_statistics`/`get_all_trades`/`get_all_daily_results` API
3. vnpy 如何把我们的 `storage.kline()` 存的 BarData 喂给 engine —— 应该走 `vnpy_sqlite` 的 `BarOverview` / engine.load_data() 读数据库
4. vnpy 的 T+1 约束：portfoliostrategy 默认支不支持 A 股 T+1？如不支 → strategy 里自己做限制
5. vnpy 的撮合：`cross_limit_order` / `cross_stop_order` —— 是下根 bar 撮合（推荐）还是本 bar？我们的 Book 是当日收盘撮合，要让 vnpy 也这样

Design Memo 回答：
- 怎样把 `AgentRunner.run_day` 的输出（`{action, code, shares}` 决策 list）转成 vnpy 的 `buy/sell/short/cover` order
- 怎样从 `engine.get_all_daily_results()` + `get_all_trades()` 生成 `daily_records / trades / thinking`
- Rating zone cutoff 怎么做：`engine.calculate_statistics` 没有分区能力，zone_stats 仍需我们手写后处理
- 撮合时间点：用 close price（简化），不是 intraday

Commit Design Memo as `docs/superpowers/plans/2026-04-24-vnpy-runner-design-memo.md`.

---

### Task 2: Complete LLMPortfolioStrategy integration

**Files:** `backtest/strategy.py`

当前 `on_bars` 调 `AgentRunner.run_day` 生成 decisions，但 **没有**把 decisions 转成 vnpy orders（`self.buy/sell(vt_symbol, price, volume)`）。补齐：

```python
def on_bars(self, bars: dict):
    day_decisions = self._process_bars(bars)
    date_str = self._extract_date(bars)
    self.daily_decisions.append((date_str, day_decisions))

    # NEW: translate decisions → vnpy orders
    for dec in day_decisions:
        code = dec.get('code')
        action = dec.get('action')
        shares = int(dec.get('shares') or 0)
        if shares <= 0 or not code or action not in ('buy', 'sell'):
            continue
        # biyingtong code '600519.SH' → vt_symbol '600519.SSE' (or similar)
        vt_symbol = _biyingtong_to_vt(code)
        bar = bars.get(vt_symbol)
        if bar is None:
            continue
        price = float(bar.close_price)
        if action == 'buy':
            # T+1 check: can only buy if not already held from today
            self.buy(vt_symbol, price, shares)
        elif action == 'sell':
            held_today = self._bought_today.get(vt_symbol, 0)
            sellable = self.get_pos(vt_symbol) - held_today
            if sellable >= shares:
                self.sell(vt_symbol, price, shares)

    # Track same-day buys for T+1 next day
    # (reset at end of on_bars — track what was bought today)
```

T+1 simple enforcement:
- Track `self._bought_today: dict[vt_symbol, int]` — reset each day
- When action='sell', subtract today's buy shares from sellable

NOTE: this is a simplification. Production would use vnpy's own position management that respects `buy`/`short`/`cover` semantics. For MVP, wrap manually.

Tests:
- `test_strategy_translates_buy_to_vnpy_order` — mock engine, verify self.buy called with right vt_symbol + shares
- `test_strategy_t1_blocks_same_day_sell` — buy then try sell same day → rejected

---

### Task 3: VnpyBacktestRunner

**Files:** `backtest/vnpy_runner.py` (new) + `tests/test_vnpy_runner.py` (new)

```python
"""VnpyBacktestRunner — uses vnpy.BacktestingEngine + LLMPortfolioStrategy.

Replaces the hand-rolled BacktestRunner for LLM-agent backtests. Reuses
vnpy's position tracking, matching, and calculate_statistics.
"""

class VnpyBacktestRunner:
    def __init__(self, llm): ...

    def run(self, *, session_id, agent_id, start_date, end_date,
            initial_capital, universe, notes=None) -> BacktestResult:
        # 1. Setup engine
        engine = BacktestingEngine()
        engine.set_parameters(
            vt_symbols=[_biyingtong_to_vt(c) for c in universe],
            interval=Interval.DAILY,
            start=datetime.strptime(start_date, '%Y-%m-%d'),
            end=datetime.strptime(end_date, '%Y-%m-%d'),
            rates={vt: 0.0003 for vt in vt_symbols},  # commission
            slippages={vt: 0 for vt in vt_symbols},
            sizes={vt: 1 for vt in vt_symbols},
            priceticks={vt: 0.01 for vt in vt_symbols},
            capital=initial_capital,
        )

        # 2. Add strategy
        engine.add_strategy(LLMPortfolioStrategy, {
            'agent_id': agent_id,
            'llm': self._llm,
            'initial_capital': initial_capital,
        })

        # 3. Load data from our vnpy_sqlite store
        engine.load_data()

        # 4. Run
        engine.run_backtesting()

        # 5. Extract results
        df = engine.calculate_result()
        stats = engine.calculate_statistics(df, output=False)
        trades = engine.get_all_trades()
        daily_results = engine.get_all_daily_results()

        # 6. Convert to our BacktestResult format
        return _engine_output_to_backtest_result(
            session_id, agent_id, start_date, end_date, initial_capital,
            stats=stats, trades=trades, daily_results=daily_results,
            strategy=engine.strategy,  # to get daily_decisions / thinking
        )
```

Helper `_engine_output_to_backtest_result`:
- `final_equity` = stats `end_balance`
- `BacktestStats` fields: map from vnpy stats dict (`sharpe_ratio` → sharpe; `max_ddpercent` → max_drawdown_pct; `total_trade_count` → trade_count; etc.)
- `daily_records`: for each DailyResult, extract `date + balance + pnl + trade_count`
- `trades`: for each TradeData, extract to our flat shape
- `thinking`: from strategy's `daily_decisions` + runner's `last_thinking` per day
- `zone_stats`: run our existing `aggregate()` or compute via post-processing (cutoff split still needed — TODO mark this explicitly)

`kind='agent'` (same as old runner).

Tests:
- `test_vnpy_runner_returns_backtest_result` — shape test
- `test_vnpy_runner_persists_via_storage` — integration
- `test_vnpy_runner_daily_records_populated`
- `test_vnpy_runner_trades_match_decisions`

Commit.

---

### Task 4: Parity test (old runner vs vnpy runner)

**Files:** `tests/test_runner_parity.py` (new)

Same MockLLM script + same universe + same window run through BOTH runners. Compare:
- `total_return_pct` within 0.5% tolerance
- `trade_count` exactly equal
- `final_equity` within 1% tolerance

Known divergence sources (document in test docstring):
- vnpy uses next-bar open by default for fills vs our close — may need to tune
- Commission model differences
- T+1 edge case handling

If tolerances too tight → loosen + document why; if OK → snapshot as regression guard.

Commit.

---

### Task 5: API endpoint to pick engine

**Files:** `api/backtests.py`

Add query param `?engine=vnpy` to `POST /api/backtests`:

```python
engine = request.args.get('engine', 'legacy')  # legacy | vnpy
if engine == 'vnpy':
    # route through jobs.py submit_vnpy_backtest
    ...
```

Or simpler: new endpoint `POST /api/backtests/vnpy` that explicitly runs vnpy path, reusing `submit_backtest` but swapping in `VnpyBacktestRunner`.

Frontend can surface this as a toggle in BacktestLab form: "回测引擎 · Legacy (默认) / vnpy (新)". Mark vnpy option as "Beta".

Tests:
- `test_post_backtests_vnpy_endpoint` — 202 + result eventually present
- `test_default_engine_is_legacy` — backward compat

Commit.

---

### Task 6: Replace `backtest/stats.py` usage in VnpyBacktestRunner

Instead of calling our `aggregate()`, use `engine.calculate_statistics()` exclusively. The zone-bifurcated stats (pollution/buffer/clean) must be done via post-processing — extract zones via cutoff date, then compute stats per zone from `engine.get_all_daily_results()` sliced.

Helper `_zone_stats_from_daily_results(daily_results, cutoff) -> list[ZoneStats]`.

Tests:
- `test_vnpy_runner_uses_engine_calculate_statistics` (verify stats.sharpe ≠ our hand-rolled value — use an engine spy)
- `test_vnpy_runner_zone_stats_respects_cutoff`

Commit.

---

### Task 7: Frontend — engine toggle in BacktestLab

**Files:** `frontend/src/pages/BacktestLab.tsx`

Add dropdown in agent-mode form: "回测引擎 · Legacy / vnpy (Beta)". Pass `?engine=vnpy` on submit when selected.

Small change, ~20 LOC.

Commit.

---

### Task 8: Roadmap + regression + UI smoke

- `pytest -q` full — all 630+ plus new tests
- `cd frontend && npm run build`
- Update status-and-roadmap marking Batch B done (but NOT removing old runner yet — leave for independent task after 1 week of parity observation)
- Commit

---

## Self-Review

**架构约束检查：**
- ✅ 用 vnpy.BacktestingEngine 而非手写 loop
- ✅ 用 engine.calculate_statistics 而非手写 stats
- ✅ 用 vnpy position tracking 而非 Book (Book 留给旧路径)
- ⚠ LLMPortfolioStrategy 当前未填满 order translation，本批 Task 2 补齐
- ⚠ zone_stats 仍是我们后处理（vnpy 不提供 cross-cutoff split） — 这是合理 domain-specific extension

**风险：**
- Parity test 容差可能需要反复调 — 测试逻辑里留配置项
- 数据 path：vnpy engine 期待 vnpy_sqlite 格式的 Bar — 我们已经用 vnpy_sqlite 存了 kline，应该兼容。但需验证 vt_symbol 映射正确

**不在本批范围：**
- 删除旧 BacktestRunner/Book/stats（独立后续任务）
- Rule mode 走 vnpy（RuleRunner 保留手写 — 规则策略是 one-off 对照）
- Multi-agent parallel 适配 vnpy（旧 multi_agent_runner 仍对接旧 BacktestRunner；新 VnpyBacktestRunner 先单 agent 跑通）

---

## Execution

Subagent-driven。task 粒度：

- Task 1 (Design Memo): 20 min — 1 subagent
- Task 2 (Strategy 补齐): 30 min — 1 subagent
- Task 3 (VnpyBacktestRunner): 60 min — 1 subagent
- Task 4 (Parity): 40 min — 1 subagent
- Task 5 (API): 25 min
- Task 6 (stats 替换): 30 min — 融入 Task 3 可能更省时
- Task 7 (Frontend): 15 min
- Task 8 (Roadmap): 10 min

Total: ~4 hours。

并行：Task 2 + Task 4 script 可以准备（Task 4 test data）。Task 1 必须先串行（提供 Design Memo 给后续参考）。Task 3 依赖 Task 1 + 2。Task 5/6/7 可部分并行。
