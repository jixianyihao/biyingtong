# T0 Loop Agent 研究闭环设计

> 状态：已获用户批准（2026-07-26）。变异权限 = 参数级 + profile 组合级。逻辑级变异留给人审核。
> 下一步：superpowers:writing-plans 出实现计划。

## 背景与目标

T0 研究链现状：UI 驱动（T0 Lab 页面 → `/api/t0/*`），人在驾驶位逐步点击；`scripts/research/` 下有 codex 加的离线 CLI 复刻（spike / candidate sweep / replay）。研究 policy（过关标准、改 profile 的思路）只在人脑里，随会话蒸发。

目标：建立一个**无监督自我迭代的研究进化闭环**——agent 驱动 候选→回测→评估→变异→再验证，不断淘汰差算法、保留有效算法，且每轮认知累积到研究记忆里。

本质模型：**进化搜索 + 选择压力**。

- 变异：LLM 提出假设并生成候选（LLM 擅长）
- 选择：硬关卡 + holdout 复测，全部在代码里（LLM 无权绕过）
- 学习：研究日志 + 榜单记录的知识累积（不是模型权重变化）

## 核心风险与纪律

无监督迭代对着同一段回测窗口反复调参，数学上必然收敛到过拟合。约束全部硬化：

1. **选择压力在代码**：关卡判定、holdout 复测均为 python 纯函数判定。
2. **数据分区**：迭代只在进化窗口进行；候选必须在未参与迭代的 holdout 窗口重新过全部关卡才能"毕业"。
3. **变异预算**：每轮 loop 的回测评估次数有上限（默认 12），计数落记录——评估次数本身当作过拟合维度管理。
4. **毕业 ≠ 上线**：毕业 profile 合入正式注册表需人在 UI 拍板（延续 P3-F gated approval 哲学）。
5. **每个变异必须附带假设文本**，落研究日志——防止无方向随机搜索。
6. **agent 的结论只能基于落盘的记录指标**，禁止凭印象。

## 分层架构

```
⑤ 人        UI（T0 Lab / 研究审计）看榜单与毕业生，拍板合入正式注册表
④ 编排层    scripts/research/t0_qlib_leaderboard.py  +  .claude/skills/t0-research/SKILL.md
③ 记忆层    data/qlib_research/journal.md  +  records/t0-qlib-leaderboard.jsonl
② 变异层    qlib_research/mutations.py（参数级 + profile 组合级）
① 真理层    qlib_research/gates.py（硬关卡）+ qlib_research/holdout.py（数据分区）+ 预算
            （底层执行仍是 t0/portfolio.py run_t0_portfolio_backtest，唯一真相）
```

## ① 真理层

### `qlib_research/gates.py`（新）

分层硬关卡，纯函数。`T0GateThresholds` dataclass 承载阈值，全部可覆盖：

| 关卡 | 目标 | 默认判定 |
|---|---|---|
| 1 | 成本持续下降 | `cost_reduction_pct > 0` 且 `cost_reduction_positive_days_pct ≥ 55` 且 `min_cost_reduction_pct ≥ -1.0` |
| 2 | 不输 all-in hold | `alpha_vs_all_in_hold ≥ 0` |
| 3 | 回撤可控 | `max_drawdown_pct ≥ -12` |
| 4 | 防交易次数过拟合 | `round_trips ≥ 20` 且 `round_trips ≤ 交易日数 × 4` |

接口：`evaluate_gates(metrics: dict, thresholds: T0GateThresholds) -> GateVerdict`，其中 `GateVerdict = {passed, failed_gate, gate_results: [{gate, name, passed, detail}]}`。出局诊断必须能回答"卡在哪一关、差多少"。

### `qlib_research/holdout.py`（新）

数据分区纪律：

- 进化窗口：`2026-01-01 → 2026-03-01`（允许迭代、寻优、变异评估）
- holdout 窗口：`2026-03-01 → 2026-04-01`（每个候选**只准复测一次**，不得据此调参）
- `split_windows() -> (evolution, holdout)`，窗口常量集中在此模块，CLI 可覆盖但整体移动（不允许只挪 holdout 起点）

### 变异预算

`ResearchBudget(max_evaluations_per_iteration=12)`。一次"评估" = 一次 `run_t0_portfolio_backtest` 调用。榜单执行器按预算截断候选集，实际消耗计数写入榜单记录。

## ② 变异层：`qlib_research/mutations.py`（新）

两类变异算子，输出均为 `Mutation = {profile, params, hypothesis, parent}`：

1. **参数级**：在既有 profile 的 `optimizer_grid` 词汇内取新组合（可越出 grid 所列值但不得越出参数语义边界，如 pct ∈ (0,1)）。
2. **profile 组合级**：用已有信号词汇拼装新 `T0StrategyProfile`：
   - `signal_mode ∈ {band, hybrid, adaptive_vwap, hybrid_adaptive}`
   - `execution_style ∈ {market, next_bar}`
   - 仓位/band/止盈止损参数取自既有 3 个 profile 已用值的并集
   - 命名 `exp/<slug>`，进入**实验注册表**（mutations 模块内维护，进程级）；`t0/strategy_profiles.py` 的正式注册表**不允许**被 agent 修改
3. 每个 Mutation 必须带 `hypothesis`（为什么这个组合应该更好）与 `parent`（基于哪个 profile / 候选变异而来）。

## ③ 记忆层

### `data/qlib_research/journal.md`（agent 维护）

研究日志，每轮 loop 启动先读、结束更新。固定四节：

1. **当前认知**——哪类票（按 feature summary 特征）适合哪类 profile，附证据链接（榜单记录时间戳）
2. **已否定的假设**——假设文本 + 否决证据（卡在哪关）
3. **毕业生名单**——holdout 通关的 (code, profile, params) 及两个窗口的完整指标
4. **下轮计划**——基于当前认知的变异方向

### 榜单记录

每轮迭代写一条 `t0-qlib-leaderboard` 研究记录（走 `qlib_research.recorder`），artifacts 含完整榜单（每个候选的 metrics + GateVerdict + hypothesis）、预算消耗、窗口配置。

## ④ 编排层

### `scripts/research/t0_qlib_leaderboard.py`（新）

一轮迭代的确定性执行器（CLI + 可注入函数，同 replay 的 orchestration-only 风格）：

- 输入：候选集（code × profile/exp-profile × params × hypothesis）、窗口、预算、阈值
- 执行：逐候选 replay 全回测（复用 `t0_qlib_replay.run_replay`，其新增 `record: bool = True` 参数，批量时置 False）→ 关卡判定 → 按 `(过关数, cost_reduction_pct, alpha, 回撤)` 排序
- 输出：榜单 JSON（stdout）+ 一条 `t0-qlib-leaderboard` 记录
- 默认候选源：`t0-qlib-spike.jsonl` 中每个 (code, strategy_profile) 最新一条的 `artifacts.best_params`

### `.claude/skills/t0-research/SKILL.md`（新）

loop playbook，规定一轮迭代的固定流程：

1. 读 `journal.md` + 最近榜单记录
2. 提出 ≤预算 的变异（每个含假设文本），优先下轮计划一节
3. 调用 leaderboard 执行器跑进化窗口
4. 过关者在 holdout 窗口复测一次 → 全部通关入毕业生名单
5. 更新 journal.md（四节）
6. 向人汇报：本轮淘汰谁、谁接近过关（卡在哪关）、谁毕业

配合 Claude Code loop 机制实现无人值守连续迭代；skill 必须强调"结论只凭落盘记录""关卡判定以代码为准"。

## ⑤ 人的位置

- Phase 1（本 spec）：`journal.md` + 榜单 JSON/JSONL 人可读；毕业 profile 由人手动合入 `t0/strategy_profiles.py`
- Follow-up（不在本 spec）：UI 研究审计面板（榜单 + 关卡诊断 + 毕业批准按钮）；平台运行时工具化

## 文件清单

| 文件 | 动作 |
|---|---|
| `qlib_research/gates.py` | 新建 |
| `qlib_research/holdout.py` | 新建 |
| `qlib_research/mutations.py` | 新建 |
| `scripts/research/t0_qlib_leaderboard.py` | 新建 |
| `scripts/research/t0_qlib_replay.py` | 小改：`run_replay` 加 `record: bool = True` |
| `.claude/skills/t0-research/SKILL.md` | 新建 |
| `tests/test_qlib_gates.py` | 新建 |
| `tests/test_qlib_holdout.py` | 新建 |
| `tests/test_qlib_mutations.py` | 新建 |
| `tests/test_qlib_leaderboard.py` | 新建 |

## 验证

1. 四个新测试文件全绿 + 既有 t0/qlib 测试不回归
2. 真实 smoke：对 spike 记录中的 11 只候选跑一轮真实榜单（进化窗口），输出过关/出局诊断
3. 真实 smoke：一次完整 loop 迭代（人工扮演 agent 走一遍 skill 流程），journal.md 四节更新正确
4. 毕业路径 smoke：任一过关候选在 holdout 窗口复测，指标落毕业生名单
