# 必赢通 · 项目现状与 P3 路线图

**日期：** 2026-04-23
**目的：** 在 P2e/P2f 多分支密集开发后，重新对齐"实际交付 vs spec §15+§16 要求"，并定义 P3 阶段的前进路线。

> **取代以下分散信息：** P2e-prep / P2e-api / P2e-api-mutations / P2e-ui-scaffold / P2e-ui-phase2 / P2e-tauri / P2f-quick-wins / P2f-rating-zone-sse 这 8 个分支均无 plan 文档；本文是它们的事后总账 + 下一步唯一前进规划。

---

## 1. 已交付（按 spec 章节核对）

| Spec 章节 | 实交付 | 状态 |
|---|---|---|
| §3 TDX 集成 | tdx_service.py + scripts/setup/load_kline + load_index + load_financial + refresh_stock_status | ✅ |
| §4 Agent 设计（persona×model×rules） | 6 personas + 10 models + AgentStore.create_from_persona | ✅ |
| §5 LLM 集成（vendor-neutral） | 4 adapters: ClaudeLLM (含 base_url+auth_token) / OpenAILLM (含 extra_body) / GeminiLLM / MockLLM + factory.build_llm | ✅ |
| §6.1-6.2 Backtest 引擎 (LLM 模式) | Legacy BacktestRunner + **新 VnpyBacktestRunner (Batch B framework-first)** — `?engine=vnpy` 走 vnpy.BacktestingEngine + LLMPortfolioStrategy | ✅ |
| §6.3 Backtest 引擎 (Rule 模式) | — | ❌ |
| §6.4 Baselines | buy_and_hold + equal_weight + csi300 + 并行 run_all | ✅ |
| §7 两层 Validation 规则 | RedLine + 4 handlers (position_max_pct/ban_st/max_holdings/daily_loss_limit_pct) + audit log | ✅ |
| §8 Agent Health & Trust Rating | compute_health + classify_rating + AgentStore.update_health | ✅ |
| §9 Strategy Rating（5 子分数） | rating/strategy_rating.py + GET /api/backtests/:id/rating | ✅ |
| §10 Prompt 版本 | PromptVersionStore + auto-versioning + GET /api/agents/:id/prompt_versions + diff UI | ⚠ 缺 rollback |
| §11 知识泄漏防御 | cross-cutoff zone 分类 + compute_divergence + Zone-Bifurcated UI | ⚠ 缺 §11.5 in-prompt disclaimer |
| §12 Intraday | intraday_t0 persona 已建，但数据路径仅日线 | ⏸ 数据待补 |
| §13 Agent 生命周期 + subprocess | 单进程 + ThreadPool；状态机未建 | ❌ 用户已确认延后 |
| §15 API 端点 | 22 个 routes，详见下表 | ⚠ |
| §16 前端 | 6 页 + Tauri scaffold | ⚠ |

---

## 2. API 端点覆盖（spec §15 vs 实际）

### §15.2 Personas + Agents

| Spec | 实际 | 状态 |
|---|---|---|
| `GET /api/personas` | ✅ | OK |
| `POST /api/personas` (用户自建) | — | ❌ |
| `PUT /api/personas/{id}` | — | ❌ |
| `DELETE /api/personas/{id}` | — | ❌ |
| `GET /api/agents` | ✅ | OK |
| `POST /api/agents` | ✅ | OK |
| `PUT /api/agents/{id}` (改 rules_override / display_name) | — | ❌ |
| `DELETE /api/agents/{id}` | — | ❌ |
| `POST /api/agents/{id}/deploy` | — | ❌（依赖 §13 subprocess） |
| `POST /api/agents/{id}/stop` | — | ❌（依赖 §13） |
| `POST /api/agents/{id}/approve` (审批待执行交易) | ✅ POST /api/proposals/:id/approve（P3-F-Phase1，Phase 1 仅改 DB 状态不真下单） | ✅ |
| `POST /api/agents/{id}/reject` | ✅ POST /api/proposals/:id/reject（同上） | ✅ |
| `POST /api/agents/{id}/deploy` | ✅ P3-F-Phase1（subprocess + proposal 流） | ✅ |
| `POST /api/agents/{id}/stop` | ✅ P3-F-Phase1 | ✅ |

### §15.3 Prompt 版本

| Spec | 实际 | 状态 |
|---|---|---|
| `GET /api/agents/{id}/prompts` | ✅ as `/prompt_versions`（路径单复数差异） | ⚠ |
| `POST /api/agents/{id}/prompts/rollback` | — | ❌ |

### §15.4 Backtest

| Spec | 实际 | 状态 |
|---|---|---|
| `POST /api/backtest/agent` | `POST /api/backtests`（路径不同，功能等价） | ⚠ |
| `POST /api/backtest/rule` | — | ❌ |
| `GET /api/backtest/{task_id}/stream` | `GET /api/backtests/jobs/:sid/stream`（粗粒度，仅 status 快照） | ⚠ |
| `GET /api/backtest/{task_id}/result` | `GET /api/backtests/:id` | ✅ |
| `GET /api/backtest/{task_id}/trades` | — | ❌ |
| `GET /api/backtest/{task_id}/thinking` | — | ❌ |
| `GET /api/backtest/{task_id}/nav` (每日权益曲线) | — | ❌ |
| `POST /api/backtest/{task_id}/cancel` | — | ❌ |
| `GET /api/backtest/results` (跨 agent 全列) | ✅ `GET /api/backtests` 不带 agent_id 返全局列表（commit `5e12dd5`） | ✅ |

### §15.5 Models + RedLine

| Spec | 实际 | 状态 |
|---|---|---|
| `GET /api/models` | ✅ | OK |
| `GET /api/redline` | ✅ as `/redlines` | OK |
| `PUT /api/redline` | ✅ | OK |

### §15.6 SSE 事件类型

| Spec event | 实际 | 状态 |
|---|---|---|
| `event: phase` (data_loading/running/done) | — | ❌ |
| `event: progress` (per day, snippet) | 仅 `progress: str` 大致描述 | ⚠ |
| `event: tool_call` (per LLM tool 调用) | — | ❌ |
| `event: decision` (per place_decision) | — | ❌ |
| `event: blocked` (validation 拒) | — | ❌ |
| `event: baseline_done` | — | ❌ |
| `event: done` | ✅ | OK |

**SSE 重大差距：** 我们只推 job 状态，spec 要求 7 种事件粒度。当前 SSE 只够"进度条"，做不了"实时 thinking 流"。

### §15.1 / 其他

`/api/status` `/api/market/*` `/api/stocks/*` `/api/account/*` `/api/trade/*` 全是 v1 既有，未在 P2e 范围内动。

### 我们额外加的（spec 未要求但有用）

- `GET /api/backtests/sessions` (Dashboard 用)
- `GET /api/agents/:id/health` (按需重算)
- `GET /api/audit?agent_id=&kind=`
- `GET /api/baselines?session_id=`
- `GET /api/backtests/jobs/:id` (异步任务状态)
- `GET /api/backtests/jobs` (任务列表)

---

## 3. 前端覆盖（spec §16 vs 实际）

### 已实现页面

| 路由 | 实际状态 |
|---|---|
| `/` Dashboard | ✅ 4 stat cards + 最近 sessions + Top performers + 健康分布 |
| `/agent` Agent 管理 | ✅ list + detail + create + scheduler 占位 |
| `/risk` 安全管控 | ✅ 三层防护 + RedLine 配置 + 编辑 Modal + 违规列表 + 变更历史 |
| `/audit` 审计日志 | ✅ filter + timeline + JSON 展开 + 10s 自动刷新 |
| `/screener` 选股器 | ✅ stub 数据 + 客户端筛选 + 行业/市值分布 |
| `/editor` 策略研发 | ✅ stub 迭代轨迹 + 指标卡 + agent 工作流 |
| `/backtest` 回测实验室 | ✅ 表单 + agent vs 3 baselines + zones 区间 + divergence banner |
| `/agent/:id/prompts` Prompt 历史 | ✅ list + diff |
| `/live` 实盘交易 | ✅ Phase 1 UI scaffold + Phase 2 真单通路落地（ExecutionAdapter + `BIYINGTONG_EXECUTION_MODE` env 切换 + 2 步 "确认下单" Modal） |

### Spec §16 表格元素覆盖

| 元素 | 实际 |
|---|---|
| Agent cards | ✅ Dashboard top performers |
| AutonomousScheduler 24h timeline | ✅ mock 市场阶段 + 真 per-agent 调度 tick 叠加（commit `ff32e2f`） |
| **Thinking log** (SSE decisions + 持久化) | ✅ P3-A ThinkingDrawer + P3-D LiveEventLog SSE |
| **Positions panel** (vnpy state / TDX) | ❌ |
| **Compare chart 5 curves** (`/nav` per agent) | ✅ P3-A NavChart 4-curve（agent + 3 baselines） |
| Cost stats (Token/¥/ROI) | ❌ 用户在 P1 删除了 token tracking |
| Prompt panel + 版本 v7 风格 | ✅ + diff（无 rollback） |
| Tools list (allowed_tools 复选框) | ✅ Agent 详情展示 |
| Create Agent modal | ✅ |
| **Backtest equity chart 4 curves** | ✅ P3-A NavChart |
| Pollution / Clean split | ✅ Zone UI |
| **Monthly heatmap** (monthly_returns) | ✅ MonthlyHeatmap 组件 + GET `/monthly_returns` endpoint（commit `739224a`+`c9f6315`+`168ecd2`） |
| **Trade log** (`/trades`) | ✅ P3-A TradesTable |
| Strategy rating A+/A/B/C + 5 子分数 | ✅ P3-A StrategyRatingPanel |
| **Quality gate panel** (per criterion) | ✅ P3-A QualityGatePanel |
| **RedLineBar** (顶部实时用量) | ✅ TopBar 显示限值 chips（实时用量待 LiveTrading 接入） |
| RedLineConfigModal | ✅ |
| RiskMonitor → 健康度 | ✅ |
| RiskMonitor → 三层防护 | ✅ |
| RiskMonitor → 审计日志 | ✅ 独立 /audit 页 |
| **RiskMonitor → 待审批** (pending trades) | ✅ P3-F-Phase1 ProposalsPanel 挂在 /risk 顶部 + 每 agent detail |
| LiveTrading → AI 风控提示 | ❌（spec 标 Phase 2） |
| Dashboard → AI 今日贡献 | ❌（spec 标 Phase 2） |
| Marketplace | ❌（spec 标 Phase 2+） |

---

## 4. 决策日志（已确认延后/排除）

| 项 | 决策日期 | 原因 |
|---|---|---|
| Token / ¥ 成本追踪 | P1 期间 | 用户："不是重点" |
| 数据存储抽象 (Protocol) | P1 期间 | 用户主动加，已交付 |
| Subprocess 架构 (§13.2) | 当前 session | 用户："没 live 之前不做" |
| Skills / 外挂 agent (Claude SDK / Hermes) | 当前 session | 用户："留以后实现" |
| LiveTrading AI 风控提示 | spec | spec 自标 Phase 2 |
| Marketplace | spec | spec 自标 Phase 2+ |
| News 源 / 多 agent 协作 / 事件触发调度 | spec §19 | Phase 2+ |
| Intraday 1m/5m bars | P0 verification | 数据路径未通，延后 |

---

## 5. P3 路线图

按"用户体验阻塞度"与"前置依赖"排序。每一阶段独立可交付。

### ✅ P3-A：回测可观察性 — Done 2026-04-23

**问题：** BacktestLab 跑完只有最终汇总。用户问"那天到底买了啥 / 为什么决策 / 曲线长啥样"全没法回答。系统停留在 demo 阶段。

**包含：**

- `GET /api/backtests/:id/nav` — 返回每日权益曲线 [{date, equity, cash, pnl_pct}]。BacktestRunner 已有 daily_records，需新增持久化字段 daily_records_json + 端点。
- `GET /api/backtests/:id/trades` — 返回每笔交易 [{date, code, action, shares, price, fee, decision_audit_id}]。Book.fills 需要持久化。
- `GET /api/backtests/:id/thinking` — 返回每个决策点的 LLM 思考过程（已在 audit_log 里，用 join 查询返回结构化）。
- 前端 BacktestLab 加：
  - **NAV 4-curves 对比图** (agent + 3 baselines) — Recharts 或 lightweight-charts
  - **Trade 流水表** — 排序、过滤、点击跳转 audit
  - **Thinking 抽屉** — 点 trade 看 LLM reasoning + tool_calls
  - **Quality gate 聚焦面板** — 7 项 pass/fail 一栏
  - **Strategy rating 5 子分数面板** — rating endpoint 已有，前端展示

**完成判据：** 跑一次回测后，用户能完整复盘每天发生了什么，为什么。✅

**交付（commit 范围 bb7135e..5da1f57）：**
- Backend: 3 JSON 列（backtest_results + baseline_results）+ migration helpers + AgentRunner.last_thinking + Runner trades/daily_records/thinking 序列化
- API: `GET /api/backtests/:id/nav|trades|thinking`（已对接 baselines daily_records 接入点）
- Frontend: NavChart(lightweight-charts) + TradesTable + ThinkingDrawer + QualityGatePanel + StrategyRatingPanel，挂 BacktestLab
- 测试: 22 P3-A 新增 + 0 回归（`pytest -q` = 451 passed；frontend build 清洁）
- 详细 plan: `2026-04-23-p3a-backtest-observability.md`

---

### ✅ P3-B：Agent + Persona CRUD — Done 2026-04-23

**问题：** 创建后无法编辑/删除。用户被锁死在 6 个内置 persona + 一次性 agent 配置。

**包含：**

- `PUT /api/agents/:id` (display_name, rules_override)
- `DELETE /api/agents/:id`
- `POST /api/personas` (用户自建)
- `PUT /api/personas/:id` (改 prompt → 自动 bump prompt version)
- `DELETE /api/personas/:id` (有依赖 agent 时拒)
- `POST /api/agents/:id/prompts/rollback` (Spec §10.3)
- 前端：
  - Agent.tsx 加"编辑"/"删除"按钮 + Modal
  - Persona 创建表单（基于现有 Persona 结构）
  - PromptHistory 加"回滚到此版本"按钮

**完成判据：** 用户能完整管理 agent 和 persona 生命周期，包括 prompt 回滚。✅

**交付（commits f842cb0..a9b7c13 on feature/p3b-crud，13 commits）：**
- Backend: Protocol 扩展（AgentStore/PersonaStore/PromptVersionStore）+ 6 endpoints（PUT/DELETE agents、POST/PUT/DELETE personas、POST prompts/rollback）+ system_prompt 变更时对所有引用 agent 自动 bump prompt_version
- Frontend: AgentEditModal + AgentDeleteDialog + PersonaFormModal(create+edit) + PromptHistory 回滚按钮 + Agent.tsx 集成（edit/delete agent + Persona 管理 section）
- 内置 persona 保护：PUT/DELETE 返 403；被 agent 引用时 DELETE 返 409
- 测试: 21 P3-B 新增（5 Protocol + 10 Agent store + 2 Persona delete + 3 rollback + 10 agent API + 11 persona API）+ 0 回归（`pytest -q` = 492 passed；frontend build 清洁）
- 详细 plan: `2026-04-23-p3b-crud.md`

---

### ✅ P3-C：Rule mode 回测对照 — Done 2026-04-23

**问题：** 没法回答"LLM 真比硬编码 MA 金叉强吗"——所有回测都走 LLMStrategy。

**包含：**

- `backtest/rule_runner.py` — 接受 vnpy CtaTemplate 子类 + 参数 + 回测窗口
- 内置 2-3 个示例策略：MACrossover / RSIBreakout / MACDDivergence
- `POST /api/backtest/rule` (Spec §15.4)
- BacktestResult 加 `kind: 'agent' | 'rule'` 区分
- 前端 BacktestLab 加 tab："Agent 模式 / 规则模式"
- 同 session 可同时跑 agent + rule strategies + baselines，结果三方对比

**完成判据：** 可在同一 session 里 head-to-head: linyuan agent vs MA crossover vs csi300 baseline。✅

**交付（commits cded3ec..0137ed6 on feature/p3c-rule-mode，9 commits）：**
- Backend: `backtest/strategies/` 新模块（Strategy Protocol + StrategyDescriptor + registry）+ 3 策略（MACrossover / RSIBreakout / MACDDivergence，state-based）+ `RuleRunner`（镜像 BacktestRunner 结构）+ schema 加 `kind_str` 列 + 2 endpoints（POST /rule、GET /strategies）+ `_result_to_dict` 加 `kind` 字段
- Frontend: types + client + hooks + BacktestLab tab 切换（Agent / Rule）+ RuleBacktestForm + ResultsTable kind-aware pill
- 偏离 spec §6.3：不使用 vnpy `CtaTemplate`/`BacktestingEngine`，自写 Strategy Protocol 复用 Book 使数据出口统一（可 head-to-head 对比）
- MACD 语义调整：用 MACD 线 vs 零轴（非 histogram 符号）— 更贴合趋势跟随
- 测试: 27 P3-C 新增（4 schema + 4 MA + 7 RSI/MACD/registry + 3 RuleRunner + 3 storage + 6 API）+ 0 新回归（`pytest -q` = 517 passed，2 pre-existing TDX 失败与 P3-C 无关；frontend build 清洁）
- 详细 plan: `2026-04-23-p3c-rule-mode.md`

---

### ✅ P3-D：SSE 细粒度事件 — Done 2026-04-23

**问题：** 当前 SSE 只发 job 状态。spec §15.6 要 7 种事件 (phase / progress per-day / tool_call / decision / blocked / baseline_done / done)。

**包含：**

- AgentRunner.run_day 改成 generator/callback 模式，逐步 yield 事件
- BacktestRunner 在串联多日时聚合事件
- jobs.py 改成事件队列模型而非状态快照
- SSE endpoint 重写按 spec 7 种事件分发
- 前端 BacktestLab 加"实时 thinking 流"区域，实时展示 agent 调了哪些工具、做了什么决策

**完成判据：** 用户回测过程中能实时看到 agent 在干什么，不用等结束。✅

**交付（commits c30a9f0..4bea154 on feature/p3d-sse-events，8 commits）：**
- Backend: `JobStatus.events` append-only list + `emit_event` helper；`on_event: callable` 贯穿 AgentRunner → BacktestRunner → multi_agent_runner → jobs.py 回调链；jobs.py 发 phase/baseline_done/done 等关键节点事件；SSE endpoint 重写 cursor 流式输出 spec §15.6 的 7 种事件
- Frontend: `BacktestEvent` discriminated union 7 种 + `useJobStatusStream` 加 `events` 状态 + `LiveEventLog` 组件 + BacktestLab running 阶段实时事件流面板
- 测试: 16 P3-D 新增（3 emit helper + 4 AgentRunner events + 3 BacktestRunner forward + 2 jobs.py phase/baseline_done + 2 SSE endpoint + manual UI smoke 待做）+ 0 回归（`pytest -q` = 533 passed；frontend build 清洁）
- 详细 plan: `2026-04-23-p3d-sse-events.md`

---

### ✅ P3-E + Quickwins — Done 2026-04-23

**包含 3 个并行 deliverable（commits ac00263 + 5e12dd5 + 9519696 on feature/p3e-quickwins）：**
- **P3-E in-prompt disclaimer (spec §11.5)**：`prompt_builder.build_messages` 加 `model_cutoff` 参数，AgentRunner 自动传 model.training_cutoff，system_prompt 末尾追加 "今天是 X，你的训练截止于 Y..."。会使 LLMDecisionCache 旧条目失效（intended）。
- **GET /api/backtests 全局列表**：不带 `?agent_id=` 现在返回最近全部 backtest（spec §15.4 gap 关闭）。`BacktestResultStore.list_all(limit)` Protocol + SQLite impl。
- **RedLineBar 顶部 widget**：所有页面 TopBar 显示当前 RedLine 配置 chips（位置上限/最大持仓/止损/禁ST 等）。实时用量值待 P3-F LiveTrading 接入。

**测试**: 9 新（4 disclaimer + 5 global list）+ 1 obsolete test 改写 + 0 回归（`pytest -q` = 542 passed；frontend build 清洁）

**剩余 P3-E："Quality gate UI 闭环"** — P3-A QualityGatePanel 已经做了，无独立工作。

---

### 🟢 P3-E archived row (旧描述，仅供参考)：In-prompt disclaimer + Quality gate UI 闭环 (~0.5 天小修)

- Spec §11.5 — prompt_builder 在 system_prompt 末尾加："今天是 X，你的训练截止是 Y" 让 LLM 自我警觉
- BacktestLab 加 Quality gate 面板（7 criteria 通过/失败/数值）—— P3-A 包含中可合并

---

### 🟡 P3-F Phase 1 — Done 2026-04-23（部署 + 审批 infra，零真金险）

**交付（12 commits on feature/p3f-prep）：**
- Backend: schemas + Protocols + SQLite stores（TradeProposal / DeployedAgent）+ `runner/agent_process.py` subprocess + 8 endpoints（deploy/stop/deploy_status/proposals CRUD+approve+reject）+ Flask startup crash recovery
- Frontend: types + 6 hooks + ProposalsPanel + DeployButton + 挂在 Agent.tsx detail + Risk.tsx 全局 inbox
- **安全承诺：approve 仅改 DB 状态，`NEVER 调 TDX place_order`**。subprocess 也不 import tdx_service
- UI 里 2 处显式警告横幅（DeployButton + ProposalsPanel 顶部）
- 测试：43+ 新 P3-F 测试 + 5 crash recovery + 0 回归（`pytest -q` = 616 passed；frontend build 清洁）
- 详细 plan: `2026-04-23-p3f-phase1-deploy-no-money.md`

---

### ✅ P3-F Phase 2 — Done 2026-04-24（用户明确授权真金险 + 多层 guardrail）

**交付（10 commits on `feature/p3f-phase2-execution`，commit 范围 `ca9ab47..1748fce`）：**
- **Backend execution 抽象层**（commits `7263c1f..b8c9f07`）：`execution/` 新 package = `ExecutionAdapter` Protocol + `ExecutionResult` dataclass + `MockExecutionAdapter` (dry_run) + `TDXExecutionAdapter` (live, 包 `tdx_service.place_order`) + `get_adapter()` 工厂读 `BIYINGTONG_EXECUTION_MODE`
- **Schema + approve endpoint**（commits `aec250f` + `1748fce`）：`trade_proposals` 加 6 列 (`execution_mode`/`execution_order_id`/`execution_error`/`executed_at`/`filled_qty`/`filled_price`) + idempotent `ALTER TABLE`；`POST /api/proposals/:id/approve` 现在调 adapter.place_order 并持久化结果；新 endpoint `GET /api/execution/mode`
- **Frontend**（commits `8bd76de` + `dad60da` + `133c121`）：`useExecutionMode` hook + `ExecutionModeBadge` (TopBar, dry-run 灰 / LIVE 红脉冲) + `LiveApproveModal` 要求输入 `确认下单` 字符串才能 enable 提交按钮
- **多层安全 guardrail：**
  1. 默认 `dry_run`，env 不设就走 Mock
  2. Typo（如 `prod-yolo`）fall back dry_run + stderr warning，绝不 silent live
  3. `tdx_service.place_order` 只在 `execution/tdx.py` 一处被调用（grep-verify），单点审计
  4. Live 模式下 approve 按钮打开 Modal，必须精准输入 `确认下单`（`===` strict，无 trim/case-fold）才能 enable
  5. TopBar 全时显示脉冲红 `● LIVE` badge
  6. 执行失败不回滚 approved 状态；`execution_error` 暴露给 UI
- **测试：** `pytest -q` = 685 passed（+20 本批新增：10 execution core + 4 schema + 5 api + 1 Protocol compliance）；frontend build 清洁
- **详细 plan：** `2026-04-24-p3f-phase2-execution.md`

**Phase 2.5 / 后续 polish（非本批）：**
- Order status 轮询 / fill tracking over time
- Partial-fill handling
- Cancel-order UI
- 真实持仓同步（现在 approve 乐观记 `filled_qty=shares`）

---

## 6. 推荐执行顺序

```
P3-A (回测可观察性)  ← 立即开做
   │
   ├──> 完成后 ──> P3-B (CRUD)  ← 独立可并行
   │                  │
   │                  └──> 完成后 ──> P3-C (Rule mode)
   │
   └──> 并行做 ──> P3-D (SSE 细粒度)
                      │
                      └──> 完成后 ──> P3-E (disclaimer + QG)
```

P3-A → B → C → D → E 串到底，**预估 8-10 天单人工时**。
P3-F 等用户明确同意 + 独立排期。

---

## 7. 历史 plan 档案

- `2026-04-22-p0-infrastructure-spikes.md` ✅ Done
- `2026-04-22-p1-llm-layer.md` ✅ Done
- `2026-04-22-p2a-personas-and-agents.md` ✅ Done
- `2026-04-22-p2b-validation-engine.md` ✅ Done
- `2026-04-22-p2c-llm-strategy-backtest.md` ✅ Done
- `2026-04-22-p2d-baselines-rating.md` ✅ Done
- `2026-04-22-p2e-speedup.md` ✅ Done
- `2026-04-23-p3a-backtest-observability.md` ✅ Done 2026-04-23
- `2026-04-23-p3b-crud.md` ✅ Done 2026-04-23
- `2026-04-23-p3c-rule-mode.md` ✅ Done 2026-04-23
- `2026-04-23-p3d-sse-events.md` ✅ Done 2026-04-23
- P3-E + quickwins (no dedicated plan — 3 parallel subagents on `feature/p3e-quickwins`) ✅ Done 2026-04-23
- `2026-04-23-p3f-phase1-deploy-no-money.md` ✅ Done 2026-04-23（零真金险 infra）
- **Framework-first 硬约束**（2026-04-24 用户 audit，memory/framework_first_principle.md）：
  - Batch A ✅ Done：`get_technical` talib/numpy + `load_financial` 启动流程自动加载
  - Batch B ✅ Done：VnpyBacktestRunner 并存路径 + `engine=legacy|vnpy` toggle + parity test
  - Batch C ✅ Done 2026-04-24（`feature/framework-first-batch-c`，8 commits `300533b..08d98f3`）：
    - `tq.subscribe_hq` 推送替换 `push_quotes` 3 秒轮询 + `tdx_service` 加 `get_gpjy_value`/`get_bkjy_value`/`get_stock_list_in_sector`/`get_sector_list` 薄包装
    - `tools/get_stock_list` 动态板块股池工具 + `tools/get_capital_flow` 个股/板块资金流工具（两者入 `ALL_TOOLS`）
    - 5m bar 支持：`storage/sqlite_kline._interval` 加 `5m`/`1m` + `scripts/setup/load_kline_intraday.py`
    - ⚠ 本地 vnpy 版本缺 `Interval.MINUTE_5`，当前 fallback 到 `MINUTE`；5m 与 1m 复用同 interval 列，intraday 正式跑前需升 vnpy 或分表
    - 测试：`pytest -q` = 654 passed（+19 本批新增：6 subscribe_hq + 5 get_stock_list + 4 get_capital_flow + 2 kline_intraday + 2 registry 扩展）；frontend build 清洁

P2e-prep / P2e-api / P2e-api-mutations / P2e-ui-scaffold / P2e-ui-phase2 / P2e-tauri / P2f-quick-wins / P2f-rating-zone-sse 共 8 个分支**未事先写 plan，直接编码 + 事后 review**。这是节奏权衡：分支小、确定性高时跳过 plan 加速；本文是它们的事后总账。

P3 阶段恢复"先 plan 后做"节律——本文是 P3 的入口，每个 P3-X 启动前再写细节 plan。

---

## 8. 测试与质量门禁

- pytest: 663 passed (2026-04-24) ✅
- frontend build: ✅
- 跨 subagent 并行编辑同一分支：本 session 验证有效，但需要 code-reviewer 兜底（已成习惯）
- 已知 minor 债待清理：
  - ✅ SSE `time.sleep(0.5)` 修（2026-04-24，commit `4181c6a`，改 `socketio.sleep` + lazy import fallback）
  - ✅ `api/backtests.py` 已拆出 `api/backtest_jobs.py` + `api/rating.py`（P2e 时期完成）
  - 未知 model 警告去重已修；其他 audit 类型暂未去重（需具体 flooding 证据后再做）
  - `compute_monthly_returns` 时序 bug ✅ 修（2026-04-24，commit `a315ddf`）
