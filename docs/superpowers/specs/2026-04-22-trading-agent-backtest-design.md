# Trading Agent + Backtest Engine Design Spec

## Overview

Build an LLM-driven trading agent system with 1-year backtesting. Each agent gets ¥100,000 initial capital. **Backtest infrastructure uses vnpy (VeighNa) framework** — no reinventing the wheel. We only build the LLM integration layer on top of vnpy's proven engine.

## Architecture: Flask + vnpy + LLM

```
React (Vite) <-- SSE/polling --> Flask
                                    |
                                    +--> vnpy BacktestingEngine (portfolio simulation, matching, commission)
                                    |       +--> LLM Strategy (calls Claude/GPT/DeepSeek per bar)
                                    |       +--> vnpy_sqlite (K-line cache)
                                    |       +--> vnpy-tdx (data loading)
                                    |       +--> vnpy_riskmanager (pre-trade checks)
                                    |
                                    +--> tdx_service.py (existing: live trading via tqcenter SDK)
```

### What vnpy provides (reuse directly):

| Component | vnpy Module | What it gives us |
|-----------|------------|-----------------|
| Backtesting engine | `vnpy_portfoliostrategy.BacktestingEngine` | Multi-stock portfolio replay, order matching, NAV tracking, daily statistics |
| Data storage | `vnpy_sqlite` | SQLite persistence for K-line data via vnpy's BaseDatabase API |
| Data loading | `vnpy-tdx` | Fetch historical K-line from TDX servers into vnpy's database |
| Strategy template | `vnpy_portfoliostrategy.StrategyTemplate` | `on_bars()` callback, `buy()`/`sell()` API, position tracking |
| Technical indicators | `vnpy.trader.tech.ArrayManager` | MA/MACD/RSI/Bollinger built-in (wraps numpy) |
| Risk management | `vnpy_riskmanager` | Pre-trade order flow control, quantity limits, position limits |
| Event system | `vnpy.event.EventEngine` | Thread-safe event queue for real-time data dispatch |
| Data objects | `vnpy.trader.object` | BarData, TickData, OrderData, TradeData, PositionData — clean dataclasses |
| Performance metrics | `BacktestingEngine.calculate_result()` | Sharpe, max drawdown, return/drawdown ratio, daily PnL, trade count |

### What we build ourselves:

| Component | Purpose |
|-----------|---------|
| `LLMStrategy` (inherits vnpy StrategyTemplate) | Strategy that calls LLM on each bar instead of using fixed rules |
| `llm/` adapter layer | Multi-model LLM calls (Claude/GPT/DeepSeek) |
| `agents/` persona definitions | System prompts + context builders per agent style |
| A-share T+1 enforcement | vnpy doesn't enforce T+1 natively — we add it in strategy code |
| A-share commission override | vnpy uses `rate * turnover` — we override with exact A-share fee schedule |
| SSE streaming wrapper | Wraps vnpy's backtest loop to emit real-time progress events |
| Flask API routes | REST + SSE endpoints for frontend |
| Prompt context builder | Assembles market data into LLM-ready text per bar |
| Agent deployment system | Live agent runner with semi-automatic confirmation |

---

## 1. Operation Flow

### 1.1 User Journey (Backtest)

```
Step 1: User opens "Agent Lab" page
        → sees 5 pre-defined agents + "create new" button
        → each agent card shows: name, style, model, backtest status

Step 2: User clicks "开始回测" on an agent card
        → confirm dialog: agent name, capital ¥100K, 1 year period
        → backend receives POST /api/backtest/start

Step 3: Backend pre-fetches all data
        → fetch 1 year daily K-line for ~300 stocks from TDX
        → cache to SQLite (first run ~2 min, subsequent <1 sec)
        → fetch financial data (PE/PB/ROE) for all stocks
        → SSE emits: { phase: "data_loading", progress: 0..1 }

Step 4: Backtest loop begins (244 trading days)
        → for each day:
            a. Build market context from cached data
            b. Call LLM with agent persona + context
            c. Parse decision (<thinking> + <action>)
            d. Check risk limits (RedLine rules)
            e. Execute trade in virtual portfolio
            f. SSE emits: { day, status, thinking_snippet, decision, nav }
        → 5 agents run in parallel (each in a Python thread)

Step 5: Backtest complete
        → calculate all metrics
        → store results in SQLite
        → SSE emits: { status: "done", metrics: {...} }
        → frontend updates agent card with real numbers
```

### 1.2 User Journey (Live Trading — future, not in this phase)

```
Step 1: Agent runs on schedule (daily close / per-event)
Step 2: Agent calls tools to get market data from TDX
Step 3: Agent calls LLM to make decision
Step 4: If trade decision:
        → check RedLine rules
        → show confirmation dialog to user (semi-automatic)
        → user approves → execute via TDX order API
        → user rejects → log rejection
```

---

## 2. TDX Interaction

### 2.1 Two TDX Data Paths

This project uses TDX data in two different ways:

| Purpose | Module | API | When Used |
|---------|--------|-----|-----------|
| **Backtest data** (historical K-line) | `vnpy-tdx` (datafeed) | vnpy's `BaseDatafeed` → TDX servers | Pre-backtest: load 1 year of data into vnpy_sqlite |
| **Live data** (real-time quotes, trading) | `tqcenter` SDK (existing) | `tq.get_market_snapshot()`, `tq.order_stock()` | During live trading |
| **Financial data** (PE/PB/ROE) | `tqcenter` SDK | `tq.get_stock_info()` | Both backtest and live |

Why two paths:
- `vnpy-tdx` integrates directly with vnpy's BacktestingEngine — it loads data into vnpy's BarData format
- `tqcenter` SDK provides live trading, account management, and real-time snapshots — vnpy-tdx does not support these
- Financial data (PE/PB/ROE) is not available via vnpy-tdx, only via tqcenter

### 2.2 Backtest Data Flow (via vnpy-tdx)

```
Step 1: Data Loading (before backtest, one-time)
  vnpy-tdx datafeed → fetch K-line from TDX servers → store in vnpy_sqlite database
  
  Python code:
    from vnpy_tdx import TdxDatafeed
    datafeed = TdxDatafeed()
    datafeed.query_bar_history(
        symbol="600519", exchange=Exchange.SSE,
        interval=Interval.DAILY, 
        start="2025-04-22", end="2026-04-22"
    )
  → Data stored in vnpy_sqlite, reused for all subsequent backtests

Step 2: Backtest Engine (reads from vnpy_sqlite, no TDX calls)
  vnpy BacktestingEngine.load_data() → reads from vnpy_sqlite
  → Replays bars to strategy via on_bars() callback
  → Strategy calls LLM on each bar
  → vnpy handles order matching, commission, NAV tracking internally

Step 3: Financial Data (separate, via tqcenter)
  Before backtest: fetch PE/PB/ROE for universe via tqcenter
  → Store in separate SQLite table (not vnpy's, since it's not K-line data)
  → Strategy reads from this cache during context building
```

### 2.3 Live Data Flow (via tqcenter SDK — existing)

```
Agent trigger → tdx_service.get_snapshot() → real-time 5-level quotes
Agent decision → tdx_service.place_order() → execute via tqcenter
Position check → tdx_service.get_positions() → current holdings
```

### 2.4 Financial Data Cache

vnpy does not store PE/PB/ROE data. We build a separate cache:

```python
# data/financial_cache.db (separate from vnpy's database)
CREATE TABLE financial_data (
    stock_code TEXT,
    date DATE,
    pe REAL,
    pb REAL,
    roe REAL,
    gross_margin REAL,         # 毛利率
    revenue_growth REAL,       # 营收增长率
    net_profit_growth REAL,    # 净利润增长率
    PRIMARY KEY (stock_code, date)
);
```

Refreshed monthly via `tqcenter` SDK. Used by prompt context builder during backtest. Since user has already downloaded financial data locally via TDX, we read directly from the local cache — no remote API calls needed.

TDX is NOT called during the backtest loop itself. All data is pre-cached.
```

### 2.5 Interaction Timing (Live Trading — future)

```
Agent trigger (scheduled or event):
  1. Call tq.get_market_snapshot() for watched stocks → real-time 5-level quotes
  2. Call tq.get_market_data() for recent K-line → may use cache
  3. Agent makes decision via LLM
  4. If trade:
     → tq.stock_account() → get account ID
     → tq.order_stock() → place order
     → tq.query_stock_positions() → verify
```

---

## 3. Agent Design

### 3.1 Agent Architecture — Persona + Stock Pool + Schedule + Rules

Each agent is defined by 4 dimensions:

| Dimension | Description | Example |
|-----------|------------|---------|
| **Persona** | System prompt describing investment philosophy (guidance, not hard restriction) | 林园: 价值投资，找印钞机企业 |
| **Stock Pool** | 30-50 stocks the agent monitors, selected by sector/index/filter | 林园: 白酒+医药+消费龙头 |
| **Rebalance Schedule** | How often the agent makes decisions | 林园: 每周一；浮游: 每天；量化中性: 每天 |
| **Risk Rules** | Configurable validation rules (position limits, stop-loss, etc.) | 仓位上限30%, 止损线-4%, 最大回撤-15% |

**Stock Pool Management:**
- Each agent has its own stock pool of 30-50 stocks
- Pool is defined at agent creation time, stored in SQLite
- Pool can be refreshed periodically (e.g., monthly re-screen based on criteria)
- During backtest: pool is fixed to the period's actual constituents
- During live: pool can be dynamically updated

**Rebalance Schedule:**
- `daily`: agent decides every trading day (after close for daily, during session for intraday)
- `weekly`: agent decides every Monday (or configured weekday)
- `monthly`: agent decides on first trading day of each month
- `intraday_5m`: agent decides every 5-minute bar during trading hours
- Only the rebalance days trigger LLM calls — non-rebalance days are automatic holds

### 3.2 Agent ↔ vnpy Interaction Model

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent (LLM-Driven)                         │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Persona +    │    │ Prompt       │    │ Decision     │      │
│  │ Stock Pool   │───>│ Context      │───>│ Parser       │      │
│  │ + Schedule   │    │ Builder      │    │ (XML→struct) │      │
│  └──────────────┘    └──────────────┘    └──────┬───────┘      │
│                                                   │              │
│                                    ┌──────────────┴──────┐      │
│                                    │  Validation Engine   │      │
│                                    │  (configurable rules)│      │
│                                    └──────────┬──────────┘      │
│                                               │                  │
└───────────────────────────────────────────────┼──────────────────┘
                                                │
                    ┌───────────────────────────┼───────────────────┐
                    │                           │                    │
              Backtest Mode               Live Mode                 │
                    │                           │                    │
                    ▼                           ▼                    │
          ┌─────────────────┐        ┌─────────────────┐           │
          │ vnpy Engine     │        │ tdx_service.py  │           │
          │                 │        │ (tqcenter SDK)  │           │
          │ • K-line replay │        │ • Real-time     │           │
          │ • Order match   │        │   quotes        │           │
          │ • NAV tracking  │        │ • Order exec    │           │
          │ • Statistics    │        │ • Positions     │           │
          └─────────────────┘        └─────────────────┘           │
                                                                   │
                    Data Layer (shared)                             │
          ┌─────────────────┐        ┌─────────────────┐           │
          │ vnpy_sqlite     │        │ financial_cache │           │
          │ (K-line cache)  │        │ (PE/PB/ROE)     │           │
          └─────────────────┘        └─────────────────┘           │
```

**Key principle**: The agent code is the same for both backtest and live. Only the execution layer differs:
- Backtest: `on_bars()` called by vnpy engine replaying historical data
- Live: `on_tick()` / `on_timer()` called by scheduler in agent subprocess

### 3.3 Agent Decision Cycle (Detailed)

For each rebalance event, the agent executes this cycle:

```
Step 1: FETCH DATA
  ├── Read stock pool from agent config
  ├── For each stock in pool: fetch K-line + financials + technicals
  ├── Read current portfolio state (positions + cash)
  └── Read market index data

Step 2: BUILD CONTEXT
  ├── Assemble prompt: [system prompt] + [knowledge boundary] + [market data]
  ├── Format positions table
  ├── Format stock pool summary (price, PE, PB, ROE, technicals)
  └── Include recent thinking history (last 5 decisions for continuity)

Step 3: CALL LLM
  ├── Send prompt to configured model (Claude/GPT/DeepSeek)
  ├── Receive XML response: <thinking>...</thinking><action>...</action>
  └── Track token usage and cost

Step 4: PARSE DECISION
  ├── Extract action (buy/sell/hold), stock code, quantity, reason
  └── On parse failure: default to hold, log warning

Step 5: VALIDATE
  ├── Run all configured validation rules
  ├── RedLine checks: position limit, stop-loss, concentration, cash ratio
  ├── Quality checks: ST filter, limit-up filter, T+1 check
  ├── If any rule fails: block trade, log reason, notify (live mode)
  └── Output: { action, validated: true/false, reason, blocked_by? }

Step 6: EXECUTE
  ├── Backtest: call vnpy engine's buy()/sell() API
  ├── Live: send to tdx_service.place_order() (with user confirmation)
  └── Record trade in audit log

Step 7: RECORD
  ├── Save thinking + decision + validation result
  ├── Update portfolio snapshot
  └── Emit SSE event (backtest) or WebSocket notification (live)
```

### 3.4 Five Pre-defined Agents

#### Agent 1: 林园风格 (Lin Yuan Style)
- **Model**: Claude
- **Philosophy**: 价值投资 — 寻找"印钞机"式企业，重仓龙头，长期持有
- **Stock Pool** (40 stocks): 白酒(5) + 医药(15) + 消费龙头(10) + 高ROE筛选(10)
  - 白酒: 茅台、五粮液、泸州老窖、汾酒、洋河
  - 医药: 片仔癀、恒瑞医药、云南白药、长春高新、爱尔眼科、迈瑞医疗、药明康德、智飞生物、泰格医药、通策医疗、华兰生物、东阿阿胶、同仁堂、白云山、以岭药业
  - 消费: 海天味业、伊利股份、双汇发展、格力电器、美的集团、青岛啤酒、重庆啤酒、安井食品、中炬高新、千禾味业
  - 高ROE补充: 海螺水泥、福耀玻璃、宇通客车、万华化学、长江电力、中国平安、招商银行、海康威视、大华股份、宁德时代
- **Rebalance Schedule**: `weekly` — 每周一收盘后决策
- **Decision Logic Priority**: ROE → 毛利率 → PE安全边际 → 行业景气度
- **Validation Rules**: 单票≤30%, 现金≥10%, 禁止ST, 禁止追涨停, 最大回撤-15%
- **System Prompt Core**:
  ```
  你是林园，一位坚守价值投资理念的基金经理。
  投资原则：
  1. 只买看得懂的行业，偏好白酒、医药、消费
  2. 寻找"印钞机"企业：ROE > 15%，毛利率 > 30%
  3. 安全边际至上：PE 低于行业均值 20%
  4. 长期持有：平均持仓周期 > 6个月
  5. 重仓龙头：单只股票 ≤ 30%，前5重仓 ≥ 70%
  避免：追涨杀跌、短线交易、科技股/周期股/新概念
  ```

#### Agent 2: 浮游风格 (Fu You Style)
- **Model**: OpenAI GPT
- **Philosophy**: 短线游资 — 捕捉题材热点，快进快出，止损果断
- **Stock Pool** (50 stocks): 全市场筛选，按以下标准动态更新：
  - 近5日换手率 > 5% 的活跃股(15)
  - 近10日出现过涨停的股票(15)
  - 当前热门板块龙头(10)
  - 自选补充池(10)
  - 池子每月重新筛选
- **Rebalance Schedule**: `daily` — 每个交易日收盘后决策
- **Decision Logic Priority**: 量价异动 → 板块轮动 → 资金流向 → 题材热度
- **Validation Rules**: 单票≤20%, 止损-4%, 同时≤5只, 现金≥20%, 最大回撤-10%
- **System Prompt Core**:
  ```
  你是一位短线游资操盘手。
  交易原则：
  1. 追热点：关注涨停板、板块轮动、资金流入
  2. 量价配合：放量突破优先，缩量回调观望
  3. 快进快出：持仓1-5天，不恋战
  4. 严格止损：单票亏损 > 4% 立即止损
  5. 分仓操作：单票 ≤ 20%，同时持有 ≤ 5 只
  避免：长期持有、逆势加仓、重仓单票
  ```

#### Agent 3: 巴菲特风格 (Buffett Style)
- **Model**: Claude
- **Philosophy**: 护城河 + 安全边际 + 优秀管理层
- **Stock Pool** (30 stocks): 银行(8) + 公用事业(7) + 消费龙头(10) + 高分红(5)
  - 银行: 招商银行、宁波银行、兴业银行、平安银行、工商银行、建设银行、农业银行、常熟银行
  - 公用事业: 长江电力、华能水电、中国核电、国投电力、川投能源、大秦铁路、宁沪高速
  - 消费龙头: 贵州茅台、五粮液、海天味业、伊利股份、双汇发展、格力电器、美的集团、青岛啤酒、中顺洁柔、安琪酵母
  - 高分红: 中国神华、宝钢股份、上汽集团、万科A、中国石化
- **Rebalance Schedule**: `monthly` — 每月首个交易日决策
- **Decision Logic Priority**: 护城河宽度 → ROE连续性 → 管理层质量 → 估值折价
- **Validation Rules**: 单票≤25%, 现金≥15%, 禁止ST, 最大回撤-12%
- **System Prompt Core**:
  ```
  你是沃伦·巴菲特风格的价值投资者。
  投资原则：
  1. 护城河：只买具有持久竞争优势的企业
  2. 安全边际：只在价格远低于内在价值时买入
  3. ROE > 15%：连续5年高ROE
  4. 简单易懂：只投自己能理解的生意
  5. 长期持有： ideally forever，月度评估
  避免：频繁交易、热门概念、高负债企业
  ```

#### Agent 4: 索罗斯反身性 (Soros Reflexivity)
- **Model**: DeepSeek
- **Philosophy**: 宏观对冲 — 识别市场偏见，利用反身性获利
- **Stock Pool** (35 stocks): ETF(10) + 周期股(10) + 金融(8) + 黄金/资源(7)
  - ETF: 沪深300ETF、上证50ETF、中证500ETF、创业板ETF、恒生ETF、纳指ETF、黄金ETF、白银ETF、军工ETF、芯片ETF
  - 周期股: 紫金矿业、中国铝业、江西铜业、洛阳钼业、北方稀土、宝钢股份、海螺水泥、万华化学、荣盛石化、中国神华
  - 金融: 中国平安、招商银行、中信证券、海通证券、中国太保、新华保险、广发证券、东方财富
  - 黄金/资源: 山东黄金、中金黄金、赤峰黄金、银泰黄金、盛达资源、天齐锂业、赣锋锂业
- **Rebalance Schedule**: `weekly` — 每周一收盘后决策（可根据宏观事件触发额外调仓）
- **Decision Logic Priority**: 宏观趋势 → 市场情绪极端度 → 趋势确认 → 仓位管理
- **Validation Rules**: 单票≤25%, 现金≥30%(不确定时≥50%), 最大回撤-18%
- **System Prompt Core**:
  ```
  你是乔治·索罗斯风格的宏观对冲基金经理。
  投资原则：
  1. 反身性：市场偏见创造机会，识别并利用
  2. 宏观视野：关注利率、汇率、政策、地缘政治
  3. 趋势跟随：认准方向后重仓出击
  4. 承认错误：方向错了立即砍仓，不固执
  5. 大量现金：不确定时保持高现金比例 (>50%)
  避免：分散投资、均值回归假设、忽视宏观
  ```

#### Agent 5: 量化中性 (Quant Neutral)
- **Model**: DeepSeek
- **Philosophy**: 多因子选股 — 市值中性、行业中性、追求绝对收益
- **Stock Pool** (50 stocks): 沪深300成分股，按因子动态筛选：
  - 动量因子 Top 15（近20日涨幅排名）
  - 反转因子 Top 10（近5日跌幅排名）
  - 质量因子 Top 10（ROE × 毛利率排名）
  - 价值因子 Top 10（PE倒数排名）
  - 成长因子 Top 5（营收增长率排名）
  - 池子每周重新筛选
- **Rebalance Schedule**: `daily` — 每个交易日收盘后决策
- **Decision Logic Priority**: 因子信号综合得分 → 行业中性调整 → 仓位控制
- **Validation Rules**: 单票≤8%, 同时≤15只, 行业≤25%, 最大回撤-5%, 单日亏损-0.5%
- **System Prompt Core**:
  ```
  你是一位量化中性策略基金经理。
  投资原则：
  1. 多因子模型：动量、反转、质量、价值、成长因子
  2. 市值中性：多头+空头组合，暴露≈0
  3. 行业中性：不押注单一行业
  4. 系统化：按信号交易，不受情绪影响
  5. 风险控制：最大回撤 < 3%，单日亏损 < 0.5%
  注意：模拟回测中无法真正做空，可用高现金比例替代
  避免：主观判断、集中持仓、追涨杀跌
  ```

### 3.3 Agent Tools (What Each Agent Can Call)

Each agent has access to these tools. The tools are implemented as Python functions that read from cached data during backtest:

| Tool | Input | Output | Data Source |
|------|-------|--------|-------------|
| `get_kline(code, period, count)` | 股票代码, 周期(1d/1w/1M), 数量 | OHLCV数组 | SQLite cache |
| `get_snapshot(code)` | 股票代码 | 当前价/涨跌/成交量/五档 | SQLite (backtest) / TDX (live) |
| `get_financials(code)` | 股票代码 | PE/PB/ROE/营收/净利/毛利率 | SQLite cache |
| `get_technical(code, indicator)` | 股票代码, 指标名 | MA(5/10/20/60)/MACD/RSI/布林带 | Python计算 from K-line |
| `get_index()` | 无 | 沪深300/上证/深证当日数据 | SQLite cache |
| `get_portfolio()` | 无 | 当前持仓/资金/总资产 | Portfolio state |
| `place_order(action, code, qty, reason)` | 方向/代码/数量/理由 | 成功/失败 | Portfolio模拟执行 |

**Technical indicators are calculated in Python**, not fetched from TDX:
- MA(5/10/20/60): simple moving average from cached K-line
- MACD: standard 12/26/9 calculation
- RSI: 14-period standard calculation
- Bollinger Bands: 20-period, 2 std dev

### 3.4 Tool Integration in LLM Prompt

The agent does NOT directly call tools via function calling. Instead:

```
1. Before calling LLM, the backtest engine pre-fetches all tool outputs
2. The results are embedded directly into the prompt context
3. The LLM sees the data and makes a decision
4. This simplifies the architecture — no tool-use round trips needed
```

Context construction (what the LLM sees for each day):

```
[System Prompt — agent persona]

## 当前状态
日期: 2025-06-15（周一）
账户: 可用资金 ¥87,532.00 | 持仓市值 ¥280,468.00 | 总资产 ¥368,000.00
今日盈亏: +¥1,234.00 (+0.34%)

## 当前持仓
| 代码 | 名称 | 持仓 | 成本 | 现价 | 盈亏% | 持仓占比 |
| 600519.SH | 贵州茅台 | 200股 | ¥1,402.00 | ¥1,432.00 | +2.14% | 77.8% |
| 000858.SZ | 五粮液 | 300股 | ¥145.00 | ¥152.30 | +5.03% | 12.4% |

## 大盘概况
沪深300: 3,842.56 (+0.42%) | 上证指数: 3,215.78 (+0.31%) | 创业板指: 2,102.34 (+0.88%)

## 可操作股票 — 近30日数据摘要
| 代码 | 名称 | 现价 | 涨跌幅 | PE | PB | ROE | 30日涨幅 | MA20 | RSI14 |
| 600519.SH | 贵州茅台 | 1432.00 | +1.2% | 23.1 | 9.8 | 31.2% | +5.2% | 1420.5 | 62.4 |
| 000858.SZ | 五粮液 | 152.30 | +2.1% | 18.4 | 6.2 | 28.4% | +8.7% | 148.6 | 68.1 |
| 600436.SH | 片仔癀 | 262.40 | -0.8% | 48.2 | 15.6 | 22.1% | +12.3% | 256.2 | 71.5 |
| 601899.SH | 紫金矿业 | 17.89 | +3.4% | 12.5 | 3.2 | 18.6% | +15.1% | 16.95 | 74.2 |
| ... (all stocks in universe) ...

请分析当前市场状态和持仓，做出今日决策。

严格按以下XML格式回复：
<thinking>
你的详细分析过程（2-5句），包括：
- 对持仓的分析
- 对市场环境的判断
- 对操作机会的评估
</thinking>
<action>
buy|sell|hold | 股票代码 | 数量(股) | 决策理由(一句话)
</action>

示例：
<thinking>茅台PE 23x处于合理区间，继续持有。五粮液30日涨幅8.7%较强，但RSI 68接近超买，暂不加仓。紫金矿业近期有色板块强势，考虑新建仓。</thinking>
<action>buy | 601899.SH | 500 | 有色板块龙头，估值PE 12.5x较低，突破前高</action>
```

---

## 4. Backtest Engine — vnpy Integration

### 4.1 What vnpy's BacktestingEngine Handles

vnpy's `vnpy_portfoliostrategy.BacktestingEngine` provides out of the box:

| Feature | How vnpy handles it | Our code |
|---------|-------------------|----------|
| K-line replay | `load_data()` reads from vnpy_sqlite, calls `on_bars()` per bar | None — vnpy does this |
| Order matching | `buy()`/`sell()`/`short()`/`cover()` API, matches against bar OHLCV | We call vnpy's API |
| Position tracking | Automatic position dict per symbol | Read from vnpy state |
| NAV calculation | Daily NAV = cash + sum(positions × price) | Read from vnpy result |
| Statistics | `calculate_result()` → Sharpe, max drawdown, return/dd ratio, trade count | We use vnpy's output |
| Slippage model | Configurable: fixed, percentage, or random | Set in engine config |

### 4.2 What We Add on Top of vnpy

vnpy is generic — it doesn't know A-share specifics. We add:

**A-share T+1 enforcement (in LLMStrategy.on_bars()):**
- Track `buy_date` per position in a dict
- Before executing `sell()`: check if position was bought today
- If T+1 violated → reject trade, log to `blocked_trades`
- vnpy doesn't enforce T+1 natively, so this is our responsibility

**A-share commission override (runner/commission.py):**
- vnpy uses `rate * turnover` — we override with exact A-share fee schedule
- Set engine's `commission_rate`, `slippage` parameters
- Add custom commission calculator that applies: 佣金0.025% + 印花税0.1%(sell only) + 过户费0.001%
- Minimum commission ¥5 per order

**Board lot rules:**
- A-shares trade in 100-share lots (手)
- Minimum buy: 100 shares (1手)
- Sell: can sell any amount if holding (odd lots allowed for partial sells)

### 4.3 Commission (A股标准费率) — Decimal Precision

All amounts in ¥, calculated with `decimal.Decimal`:

| Fee | Rate | Charged When |
|-----|------|-------------|
| Broker commission | 0.025% of trade value | Buy + Sell |
| Stamp tax (印花税) | 0.1% of trade value | **Sell only** |
| Transfer fee (过户费) | 0.001% of trade value | Buy + Sell |
| Minimum commission | ¥5 per order | If calculated < ¥5 |

**All monetary calculations use `decimal.Decimal`. No `float` for money.**

### 4.4 Backtest Runner Flow (runner/backtest_runner.py)

The runner wraps vnpy's BacktestingEngine and adds SSE streaming:

```python
from vnpy_portfoliostrategy import BacktestingEngine
from vnpy.trader.object import Interval

class BacktestRunner:
    def run(self, agent_id, capital, start, end, sse_callback):
        engine = BacktestingEngine()
        engine.set_parameters(
            vt_symbol="",           # multi-stock, not single
            interval=Interval.DAILY,
            start=start,
            end=end,
            rate=0.00025,           # commission 0.025%
            slippage=0.001,         # 0.1% slippage
            size=100,               # 1 lot = 100 shares
            pricetick=0.01,
            capital=capital,
        )
        # Load data from vnpy_sqlite
        engine.load_data()

        # Add our LLM strategy
        engine.add_strategy(LLMStrategy, {
            'agent_id': agent_id,
            'sse_callback': sse_callback,
        })

        # Run backtest
        engine.run_backtesting()

        # Get results
        result = engine.calculate_result()
        stats = engine.calculate_statistics(result)
        return result, stats
```

### 4.5 Daily State Snapshot

Each day during backtest, we record a snapshot from vnpy's state + our additions:

```
Portfolio data per day:
  {
    date: "2025-06-15",
    nav: 368000.00,           # from vnpy engine
    cash: 87532.00,           # from vnpy engine
    positions: {
      "600519.SH": { qty: 200, avg_cost: 1402.00, buy_date: "2025-06-10", current_price: 1432.00 },
      "000858.SZ": { qty: 300, avg_cost: 145.00, buy_date: "2025-06-12", current_price: 152.30 },
    },
    daily_pnl: 1234.00,       # from vnpy engine
    daily_pnl_pct: 0.34,      # from vnpy engine
    trades: [...],             # vnpy trade records
    thinking: "...",           # LLM thinking (our addition)
    blocked: [...],            # RedLine-rejected trades (our addition)
  }
```

### 4.4 Data Precision Requirements

- **Money**: Use `decimal.Decimal` for all monetary calculations. Display to 2 decimal places.
- **Shares**: Integer only (100-share lots for buy, any integer for sell)
- **Percentages**: 2 decimal places for display (e.g., +2.14%)
- **Prices**: 2 decimal places (A-share convention)
- **Volume**: Integer
- **NAV**: 2 decimal places
- **Indicators** (MA/MACD/RSI): 2 decimal places

### 4.5 Backtest Output

For each completed backtest, the following is stored in SQLite:

```python
{
    "task_id": "bt_20260422_linyuan",
    "agent_id": "linyuan",
    "start_date": "2025-04-22",
    "end_date": "2026-04-22",
    "initial_capital": 100000,
    "final_nav": 132400.00,
    "metrics": {
        "total_return": 32.40,       # %
        "annual_return": 32.40,      # % (1 year = annual)
        "sharpe_ratio": 1.84,
        "sortino_ratio": 2.31,
        "max_drawdown": -6.20,       # %
        "max_dd_duration": 24,       # days
        "win_rate": 71.0,            # %
        "profit_loss_ratio": 2.14,
        "trade_count": 14,
        "turnover_rate": 8.42,       # %
        "monthly_returns": [2.1, -1.3, 4.5, ...],  # 12 months
        "strategy_rating": "A",
    },
    "nav_history": [
        {"date": "2025-04-22", "nav": 100000.00},
        {"date": "2025-04-23", "nav": 100234.00},
        ...
    ],
    "trades": [
        {"date": "2025-05-10", "action": "buy", "code": "600519.SH", "qty": 100, "price": 1402.00, "commission": 38.02, "reason": "PE 23x 低于行业均值，安全边际充足"},
        ...
    ],
    "thinking_log": [
        {"date": "2025-05-10", "thinking": "茅台回调至1402，PE 23x处于近5年35%分位...", "decision": "buy 600519.SH 100", "blocked": []},
        ...
    ],
    "blocked_trades": [
        {"date": "2025-06-15", "action": "buy", "code": "600519.SH", "reason": "RedLine: 单票仓位已达30%上限"},
        ...
    ],
}
```

---

## 5. Validation — Configurable Rule Engine

### 5.1 Two-Phase Validation

**Phase 1: Pre-trade Validation (before execution)**
Every trade decision passes through a configurable rule engine before execution:

**Phase 2: Post-backtest Quality Gate (before deploy)**
After backtest completes, the agent must pass quality metrics before it can be deployed to live trading.

### 5.2 Pre-trade Rules (Configurable per Agent)

Each rule has a `enabled` flag and configurable threshold. Rules are stored in the agent config:

```python
validation_rules = {
    # Position limits
    "position_max_pct": {"enabled": True, "value": 30.0},    # 单票仓位上限 %
    "max_holdings": {"enabled": True, "value": 5},            # 最大持仓数
    "cash_min_pct": {"enabled": True, "value": 10.0},         # 最低现金比例 %

    # Loss limits
    "daily_loss_limit_pct": {"enabled": True, "value": 3.0},  # 日亏损上限 %
    "stop_loss_pct": {"enabled": True, "value": -4.0},        # 单票止损线 %
    "max_drawdown_pct": {"enabled": True, "value": -15.0},    # 最大回撤 %

    # Trade limits
    "order_max_value": {"enabled": True, "value": 50000},     # 单笔金额上限 ¥
    "industry_max_pct": {"enabled": False, "value": 25.0},    # 行业集中度上限 %

    # Filters
    "ban_st": {"enabled": True},                              # 禁止ST
    "ban_limit_up": {"enabled": True},                        # 禁止追涨停
    "ban_limit_down": {"enabled": True},                      # 禁止抄跌停
    "ban_ipo_30d": {"enabled": True},                         # 禁止次新股(上市<30天)

    # A-share specific
    "t_plus_1": {"enabled": True},                            # T+1检查
    "board_lot": {"enabled": True, "value": 100},             # 整手交易(100股)
}
```

Each agent has its own ruleset. Default rulesets are pre-configured for the 5 built-in agents. Custom agents inherit defaults with user overrides.

### 5.3 Rule Evaluation Flow

```python
def validate_trade(decision, portfolio, market_data, rules) -> ValidationResult:
    result = ValidationResult(valid=True, blocked_by=[])

    for rule_name, rule_config in rules.items():
        if not rule_config.get("enabled", False):
            continue

        check = RULE_CHECKS[rule_name]
        passed, reason = check(decision, portfolio, market_data, rule_config)

        if not passed:
            result.valid = False
            result.blocked_by.append({
                "rule": rule_name,
                "reason": reason,
                "config": rule_config,
            })

    return result
```

### 5.4 Post-backtest Quality Gate

Before an agent can be deployed to live trading, it must pass quality metrics:

```python
quality_gate = {
    "min_sharpe": 0.3,           # 最低夏普比率
    "max_drawdown_pct": -25.0,   # 最大回撤不超过25%
    "min_trade_count": 5,        # 至少5笔交易（排除只持有不动的策略）
    "min_win_rate": 30.0,        # 最低胜率30%
    "max_daily_loss_pct": -5.0,  # 单日最大亏损不超过5%
}
```

These are default thresholds. Users can customize them. Quality gate results are shown on the backtest result page with pass/fail indicators.

### 5.5 Audit Log

Every event is logged with timestamp and details:

```python
{
    "timestamp": "2026-04-22T14:32:18",
    "type": "trade_executed",       # or: trade_blocked, llm_called, validation, error
    "agent_id": "linyuan",
    "day": 87,
    "details": {
        "action": "buy",
        "code": "600519.SH",
        "qty": 100,
        "price": 1432.00,
        "reason": "PE 23x处于合理区间",
    }
}
```

Audit logs are stored in SQLite and viewable in the RiskMonitor page.

### Layer 2: Single Trade Limit

- Maximum single trade value: configurable, default ¥200,000 (from RedLine)
- Maximum single position size: 30% of NAV
- Board lot enforcement: must trade in 100-share multiples (buy side)

### Layer 3: Exception Tolerance

- **LLM response parse failure** → default to `hold`, log warning, continue backtest
- **Invalid stock code** → reject, log, continue
- **Invalid quantity** (negative, non-integer, > available cash) → reject, log
- **T+1 violation** → reject sell, log, continue
- **LLM API error** (timeout, rate limit) → retry up to 3 times with backoff, then hold for that day
- **No crash**: backtest NEVER stops due to a single trade error. All errors are caught and logged.

### Layer 4: Audit Log

Every event is logged with timestamp and details:

```python
{
    "timestamp": "2026-04-22T14:32:18",
    "type": "trade_executed",       # or: trade_blocked, llm_called, risk_check, error
    "agent_id": "linyuan",
    "day": 87,
    "details": {
        "action": "buy",
        "code": "600519.SH",
        "qty": 100,
        "price": 1432.00,
        "reason": "PE 23x处于合理区间",
    }
}
```

Audit logs are stored in SQLite and viewable in the RiskMonitor page.

---

## 6. LLM Integration

### 6.1 Multi-Model Adapter

```python
class LLMBase(ABC):
    model_name: str
    
    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """Send messages, return raw text response."""
        pass

class ClaudeLLM(LLMBase):
    """Uses anthropic SDK. model_name: 'claude-sonnet-4-5-20250514'"""
    def chat(self, messages):
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_KEY)
        response = client.messages.create(
            model=self.model_name,
            max_tokens=1000,
            system=messages[0]['content'] if messages[0]['role'] == 'system' else '',
            messages=[m for m in messages if m['role'] != 'system'],
        )
        return response.content[0].text

class OpenAILLM(LLMBase):
    """Uses openai SDK. model_name: 'gpt-4o'"""
    def chat(self, messages):
        client = openai.OpenAI(api_key=settings.OPENAI_KEY)
        response = client.chat.completions.create(
            model=self.model_name,
            max_tokens=1000,
            messages=messages,
        )
        return response.choices[0].message.content

class DeepSeekLLM(LLMBase):
    """Uses openai SDK (API-compatible). model_name: 'deepseek-chat'"""
    def chat(self, messages):
        client = openai.OpenAI(
            api_key=settings.DEEPSEEK_KEY,
            base_url="https://api.deepseek.com/v1",
        )
        response = client.chat.completions.create(
            model=self.model_name,
            max_tokens=1000,
            messages=messages,
        )
        return response.choices[0].message.content
```

### 6.2 Decision Parsing

```python
import re

def parse_decision(llm_response: str) -> dict:
    """
    Parse LLM response into structured decision.
    Returns: { thinking: str, action: str, code: str, qty: int, reason: str }
    On parse failure: returns { thinking: raw_response, action: 'hold', code: '', qty: 0, reason: 'parse_failed' }
    """
    result = {
        'thinking': '',
        'action': 'hold',
        'code': '',
        'qty': 0,
        'reason': '',
    }
    
    # Extract <thinking>
    think_match = re.search(r'<thinking>(.*?)</thinking>', llm_response, re.DOTALL)
    if think_match:
        result['thinking'] = think_match.group(1).strip()
    
    # Extract <action>
    action_match = re.search(r'<action>(.*?)</action>', llm_response, re.DOTALL)
    if not action_match:
        result['thinking'] = llm_response  # no tags found, treat entire response as thinking
        return result
    
    action_text = action_match.group(1).strip()
    # Parse: "buy|600519.SH|100|reason" or "sell|600519.SH|200|reason" or "hold"
    
    parts = [p.strip() for p in action_text.split('|')]
    if len(parts) < 1:
        return result
    
    action = parts[0].lower()
    if action not in ('buy', 'sell', 'hold'):
        return result
    
    result['action'] = action
    
    if action == 'hold':
        result['reason'] = parts[1] if len(parts) > 1 else ''
        return result
    
    # buy/sell: need code and qty
    if len(parts) < 3:
        return result  # incomplete, default to hold
    
    result['code'] = parts[1].strip()
    try:
        result['qty'] = int(parts[2].strip())
    except ValueError:
        return result  # invalid qty, default to hold
    
    result['reason'] = parts[3].strip() if len(parts) > 3 else ''
    
    return result
```

### 6.3 Token Cost Tracking

```python
class LLMCallTracker:
    """Tracks token usage and cost per agent per backtest."""
    
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_calls: int = 0
    
    # Pricing (per 1M tokens)
    PRICING = {
        'claude-sonnet-4-5-20250514': { 'input': 3.0, 'output': 15.0 },
        'gpt-4o': { 'input': 2.5, 'output': 10.0 },
        'deepseek-chat': { 'input': 0.14, 'output': 0.28 },
    }
    
    def get_cost_usd(self) -> float:
        price = self.PRICING.get(self.model_name, {'input': 1, 'output': 5})
        input_cost = self.total_input_tokens / 1_000_000 * price['input']
        output_cost = self.total_output_tokens / 1_000_000 * price['output']
        return input_cost + output_cost
    
    def get_cost_cny(self) -> float:
        return self.get_cost_usd() * 7.25  # approximate exchange rate
```

---

## 7. Project Structure

```
biyingtong/
├── app.py                     # Flask entry (routes + SSE)
├── config.py                  # Config (LLM keys, vnpy settings, port)
├── requirements.txt
├── .env                       # API keys (gitignored)
│
├── strategy/                  # LLM-driven vnpy strategies
│   ├── __init__.py
│   ├── base.py                # LLMStrategy base (inherits vnpy_portfoliostrategy.StrategyTemplate)
│   ├── linyuan.py             # 林园风格 — overrides context_builder + system_prompt
│   ├── fuyou.py               # 浮游风格
│   ├── buffet.py              # 巴菲特风格
│   ├── soros.py               # 索罗斯风格
│   └── quant_neutral.py       # 量化中性
│
├── llm/                       # Multi-model adapter
│   ├── __init__.py
│   ├── base.py                # LLMBase abstract class
│   ├── claude.py              # Anthropic SDK
│   ├── openai_adapter.py      # OpenAI SDK
│   └── deepseek.py            # DeepSeek (OpenAI-compatible)
│
├── context/                   # Prompt context builders
│   ├── __init__.py
│   ├── market_context.py      # Build market overview section
│   ├── position_context.py    # Build current positions section
│   ├── technical_context.py   # Build technical indicators section
│   └── financial_context.py   # Build PE/PB/ROE section
│
├── runner/                    # Backtest runner + live agent deployment
│   ├── __init__.py
│   ├── backtest_runner.py     # Wraps vnpy BacktestingEngine + SSE streaming
│   ├── live_runner.py         # Continuous agent operation (background thread)
│   └── commission.py          # A-share exact fee calculation (Decimal)
│
├── tdx_service.py             # Existing TDX wrapper (live trading via tqcenter)
│
├── data/                      # vnpy SQLite database (gitignored)
│   └── vnpy_data.db           # vnpy_sqlite stores K-line + financial data here
│
├── client/                    # Frontend (Vite + React)
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api.js
│       ├── components/
│       │   ├── Sidebar.jsx
│       │   ├── TopBar.jsx
│       │   ├── CandleChart.jsx
│       │   ├── Sparkline.jsx
│       │   ├── Icon.jsx
│       │   ├── EquityChart.jsx
│       │   └── MonthlyHeatmap.jsx
│       ├── pages/
│       │   ├── Dashboard.jsx
│       │   ├── AgentLab.jsx
│       │   ├── Backtest.jsx
│       │   ├── LiveTrading.jsx
│       │   ├── Screener.jsx
│       │   ├── Editor.jsx
│       │   └── RiskMonitor.jsx
│       ├── styles/
│       │   └── tokens.css
│       └── hooks/
│           ├── useAccount.js
│           └── useBacktest.js
│
└── static/                    # Vite build output (Flask serves this)
```

Key difference from previous design:
- **Removed** `engine/` (backtest/portfolio/metrics/indicators) — all handled by vnpy
- **Added** `strategy/` — thin layer inheriting vnpy's StrategyTemplate
- **Added** `context/` — prompt context builders
- **Added** `runner/` — wraps vnpy engine with SSE + live deployment
- **Kept** `llm/` — multi-model adapter (vnpy has no LLM support)
- **Kept** `tdx_service.py` — for live trading via tqcenter (vnpy-tdx is data-only)

---

## 8. API Endpoints

### Existing (unchanged)
All current endpoints remain: /api/status, /api/market/*, /api/stocks/*, /api/account/*, /api/trade/*, WebSocket quotes

### New: Agent Management
- `GET /api/agents` — list all agent definitions with their configs
- `POST /api/agents/create` — create custom agent `{ name, model, system_prompt, capital, stop_loss, max_position_pct }`

### New: Backtest
- `POST /api/backtest/start` — start backtest
  ```json
  { "agent_id": "linyuan", "capital": 100000, "start_date": "2025-04-22", "end_date": "2026-04-22" }
  ```
  Returns: `{ "task_id": "bt_20260422_linyuan" }`

- `GET /api/backtest/{task_id}/stream` — SSE endpoint
  ```
  event: progress
  data: {"day": 87, "total_days": 244, "status": "thinking", "snippet": "茅台PE 23x..."}
  
  event: decision
  data: {"day": 87, "action": "buy", "code": "600519.SH", "qty": 100, "reason": "...", "nav": 368000}
  
  event: blocked
  data: {"day": 87, "action": "sell", "code": "600519.SH", "reason": "T+1: 买入当日不可卖出"}
  
  event: done
  data: {"metrics": {"total_return": 32.4, "sharpe_ratio": 1.84, ...}}
  ```

- `GET /api/backtest/{task_id}/result` — final result
- `GET /api/backtest/{task_id}/trades` — trade history
- `GET /api/backtest/{task_id}/thinking` — thinking log
- `GET /api/backtest/{task_id}/nav` — daily NAV series
- `POST /api/backtest/{task_id}/cancel` — cancel running backtest
- `GET /api/backtest/results` — list all completed backtests (for comparison chart)

---

## 9. Frontend Migration (Vite + React)

### Tech Stack
- **Vite** — build + HMR
- **React 18** — UI
- **React Router** — routing
- **@tanstack/react-query** — data fetching + caching
- **tokens.css** — unchanged

### Dev/Prod
- Dev: Vite (localhost:5173) → proxy /api → Flask (localhost:5000)
- Prod: `vite build` → static/ → Flask serves directly

### Prototype → Implementation Mapping

Every element from the prototype maps to real data:

| Prototype Element | Data Source | Status |
|------------------|------------|--------|
| Agent cards (收益/夏普/回撤/胜率) | `/api/backtest/results` metrics | Real |
| Agent thinking log | SSE `decision` events → `thinking` field | Real |
| Agent positions | `/api/backtest/{id}/result` → final positions | Real |
| Compare chart (5 curves) | `/api/backtest/{id}/nav` for each agent | Real |
| Cost stats (Token/¥/决策数) | LLM call tracker in backtest result | Real |
| Create Agent modal | `POST /api/agents/create` | Real |
| Backtest equity chart | `/api/backtest/{id}/nav` | Real |
| Monthly heatmap | `monthly_returns` in metrics | Real |
| Trade log | `/api/backtest/{id}/trades` | Real |
| Strategy rating | `strategy_rating` in metrics | Real |
| Backtest progress bar | SSE `progress` events | Real |
| AutonomousScheduler | Shows currently running backtest tasks | Real |
| Dashboard signals | From latest backtest thinking logs | Real (deferred) |

---

## 10. Intraday Strategy Support

### 10.1 Data Requirement

Intraday agents need 1-minute and 5-minute K-line data. TDX supports these periods: `1m`, `5m`, `10m`, `15m`, `30m`, `1h`.

**Verified**: Daily K-line (`1d`) → SQLite roundtrip works perfectly.  
**Limitation**: Intraday K-line (`1m`/`5m`) returned empty in initial testing. This may require:
- TDX client to be running and connected to a market data server
- Pre-download of intraday data via `refresh_kline()` (requires TDX GUI interaction)
- Or: manual data import from user's existing cache

**Resolution**: During development, start with daily K-line backtesting first (proven to work). Intraday support is added as a second phase:
1. Phase 1: Daily backtest with `1d` K-line → works immediately
2. Phase 2: Investigate and fix intraday data fetch → add `1m`/`5m` support
3. The backtest engine is designed to support any period — just change the `period` parameter

### 10.2 Intraday Backtest Differences

When using 1m/5m data, the backtest loop changes:

| Aspect | Daily Backtest | Intraday Backtest |
|--------|---------------|-------------------|
| Data bars | 244 days × 1 bar = 244 bars | 1 day × 48 bars (5m) or 240 bars (1m) |
| Decision frequency | Once per day | Every 5min or every 1min bar |
| LLM calls | 244 per agent per year | 48-240 per agent per day |
| Cost | ~244 calls | ~10,000-60,000 calls per year |
| Context window | 30-day summary | Intraday price action + daily context |

Intraday backtest is much more expensive (LLM call volume 10-100x higher). Use sparingly and only for agents configured for intraday trading.

### 10.3 Intraday Agent Example

```python
# Agent configured for intraday
agent = {
    'id': 'fuyou_5m',
    'name': '浮游 · 5分钟级别',
    'period': '5m',
    'decision_interval': '5m',  # make decision every 5-minute bar
    'system_prompt': '''
        你是短线游资操盘手，基于5分钟K线做日内交易。
        你每天有48个决策点（9:30-11:30, 13:00-15:00，每5分钟一次）。
        规则：
        1. 日内建仓，收盘前平仓（不隔夜）
        2. 突破分时均线时进场
        3. 严格止损：-1% 立即平仓
        4. 日内最多交易3次
    ''',
}
```

---

## 11. LLM Knowledge Leakage Prevention

### 11.1 The Problem

LLMs are trained on data up to their training cutoff date. When backtesting 2025-04-22 to 2026-04-22, the LLM already "knows" which stocks went up or down during this period. This inflates backtest results and makes them unreliable.

### 11.2 Mitigation: Prompt Declaration (Phase 1)

Add explicit knowledge boundary to every LLM call:

```
[IMPORTANT - KNOWLEDGE BOUNDARY]
当前日期是 {date}。你只能基于截至此日期的信息做决策。
你不知道{date}之后发生的事情——包括但不限于：
- 任何股票在{date}之后的涨跌
- 任何宏观经济事件、政策变化
- 任何公司业绩公告
如果推理中出现了{date}之后的信息，你的决策将被视为无效。
请严格基于当前日期已知信息进行分析。
```

This is not foolproof but is the simplest approach. We will test effectiveness and consider stronger measures later.

### 11.3 Risk Disclosure

Every backtest result page displays:

> ⚠️ 回测结果声明：本回测使用 LLM 大模型进行决策模拟。LLM 的训练数据可能包含回测期间之后的真实市场信息，导致回测结果可能优于实际表现。回测收益仅供参考，不构成投资建议。实盘表现可能与回测存在显著差异。

### 11.4 Future Measures (Phase 2, if needed)

- Use older model snapshots with training cutoff before backtest period
- Evaluate backtest results against a random baseline to detect suspicious alpha
- Cross-validation: run backtest on random time windows and compare consistency

---

## 12. Agent Lifecycle: Backtest → Validate → Save → Deploy → Continuous Operation

### 12.1 Full Agent Lifecycle

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│  1. CREATE  │────>│  2. BACKTEST  │────>│  3. VALIDATE │────>│ 4. DEPLOY LIVE   │
│  Define     │     │  Run 1 year  │     │  Quality Gate│     │  Subprocess +    │
│  persona +  │     │  via vnpy    │     │  metrics ≥   │     │  Message Queue   │
│  pool +     │     │  SSE stream  │     │  thresholds  │     │  Semi-automatic  │
│  schedule   │     │              │     │              │     │  via tdx_service │
└─────────────┘     └──────────────┘     └──────────────┘     └──────────────────┘
                           │                     │                      │
                           ▼                     ▼                      ▼
                    SSE stream             Pass → Save            Agent subprocess
                    real-time progress     Fail → Re-tune         sends decisions
                                           or discard             to Flask via MQ
                                                                  Flask notifies user
                                                                  User confirms → TDX
```

### 12.2 Agent Config Schema

Each agent is fully defined by its config, stored in SQLite:

```sql
CREATE TABLE agents (
    id TEXT PRIMARY KEY,           -- 'linyuan', 'custom_1713763200'
    name TEXT NOT NULL,
    model TEXT NOT NULL,           -- 'claude-sonnet-4-5-20250514'
    system_prompt TEXT NOT NULL,
    style_desc TEXT,
    stock_pool JSON,               -- list of stock codes (30-50)
    stock_pool_filter JSON,        -- filter criteria for dynamic pool updates
    rebalance_schedule TEXT,       -- 'daily', 'weekly', 'monthly', 'intraday_5m'
    validation_rules JSON,         -- configurable rule set (see Section 5)
    quality_gate JSON,             -- post-backtest quality thresholds
    initial_capital DECIMAL(15,2) DEFAULT 100000,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'created', -- 'created', 'backtesting', 'backtested', 'deployed', 'stopped'
    subprocess_pid INTEGER,        -- PID of running agent process (null if not deployed)
);
```

### 12.3 Save Agent + Backtest Results

After backtest + validation, user can:
- **Save**: Agent definition + backtest results stored permanently
- **Re-run**: Re-run backtest with different parameters or time period
- **Discard**: Delete agent and results

Multiple backtest runs per agent are kept for comparison.

```sql
CREATE TABLE backtest_results (
    id TEXT PRIMARY KEY,           -- 'bt_20260422_linyuan'
    agent_id TEXT REFERENCES agents(id),
    start_date DATE,
    end_date DATE,
    initial_capital DECIMAL(15,2),
    final_nav DECIMAL(15,2),
    metrics JSON,                  -- Sharpe, drawdown, win rate, etc.
    quality_gate_result JSON,      -- pass/fail per rule
    nav_history JSON,              -- daily NAV series
    trades JSON,                   -- all trades
    thinking_log JSON,             -- all thinking entries
    blocked_trades JSON,           -- rejected trades + reasons
    token_usage JSON,              -- LLM call stats + cost
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 12.4 Deploy Architecture: Independent Subprocess + Message Queue

Each deployed agent runs as an **independent Python subprocess**. The Flask server communicates with agent processes via a message queue (using Python's `multiprocessing.Queue` or Redis).

```
┌─────────────────────────────────────────────────────┐
│                  Flask Server                        │
│                                                      │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐ │
│  │ REST API │  │ WebSocket │  │ Message Router   │ │
│  │ Routes   │  │ Handler   │  │ (central hub)    │ │
│  └────┬─────┘  └─────┬─────┘  └────────┬─────────┘ │
│       │              │                  │            │
│       └──────────────┴──────────────────┘            │
│                        │                             │
│              ┌─────────┴──────────┐                  │
│              │  Message Queue     │                  │
│              │  (multiprocessing) │                  │
│              └─────┬──────┬───────┘                  │
└────────────────────┼──────┼──────────────────────────┘
                     │      │
          ┌──────────┘      └──────────┐
          ▼                            ▼
  ┌───────────────┐          ┌───────────────┐
  │ Agent Process │          │ Agent Process │
  │   (linyuan)   │          │   (fuyou)     │
  │               │          │               │
  │  Scheduler    │          │  Scheduler    │
  │  → weekly     │          │  → daily      │
  │               │          │               │
  │  LLM Caller   │          │  LLM Caller   │
  │  Validator    │          │  Validator    │
  │               │          │               │
  │  Sends:       │          │  Sends:       │
  │  - heartbeat  │          │  - heartbeat  │
  │  - decision   │          │  - decision   │
  │  - error      │          │  - error      │
  └───────────────┘          └───────────────┘
```

**Why subprocess + MQ instead of Flask threads:**

| Concern | Flask threads | Subprocess + MQ |
|---------|--------------|-----------------|
| Isolation | Agent crash kills Flask | Agent crash isolated, Flask unaffected |
| Restart | Flask restart kills all agents | Agent can restart independently |
| CPU/memory | Shares Flask's GIL | Separate process, no GIL contention |
| Debugging | Mixed logs | Separate logs per agent |
| Scaling | Limited by Flask process | Can move to separate machines |

### 12.5 Agent Subprocess Implementation

```python
# runner/agent_process.py — runs as independent process

import multiprocessing as mp
import schedule
import time
from datetime import datetime

class AgentProcess:
    """Runs in its own Python process, managed by Flask."""

    def __init__(self, agent_id: str, config: dict, msg_queue: mp.Queue):
        self.agent_id = agent_id
        self.config = config
        self.msg_queue = msg_queue
        self.running = True

    def run(self):
        """Main loop — runs forever until stopped."""
        self._send("started", {"schedule": self.config["rebalance_schedule"]})

        while self.running:
            try:
                # Wait for next rebalance time
                if self._should_rebalance():
                    self._run_decision_cycle()
                time.sleep(30)  # check every 30 seconds
            except KeyboardInterrupt:
                break
            except Exception as e:
                self._send("error", {"error": str(e)})
                time.sleep(60)  # back off on error

        self._send("stopped", {})

    def _should_rebalance(self) -> bool:
        """Check if current time matches agent's rebalance schedule."""
        now = datetime.now()
        sched = self.config["rebalance_schedule"]

        if sched == "daily":
            # Trigger at 15:05 on trading days
            return now.hour == 15 and now.minute == 5
        elif sched == "weekly":
            # Trigger at 15:05 on Mondays
            return now.weekday() == 0 and now.hour == 15 and now.minute == 5
        elif sched == "monthly":
            # Trigger at 15:05 on 1st trading day
            return now.day <= 3 and now.hour == 15 and now.minute == 5
        elif sched == "intraday_5m":
            # Trigger every 5 minutes during trading hours
            return (9 <= now.hour <= 11 or 13 <= now.hour <= 15) and now.minute % 5 == 0
        return False

    def _run_decision_cycle(self):
        """Execute one full decision cycle."""
        # 1. Fetch live data from TDX (via tdx_service)
        market_data = self._fetch_market_data()
        positions = self._fetch_positions()

        # 2. Build prompt context
        context = self._build_context(market_data, positions)

        # 3. Call LLM
        response, tokens = self._call_llm(context)

        # 4. Parse decision
        decision = self._parse_decision(response)

        # 5. Validate against rules
        validation = self._validate(decision)

        if not validation.valid:
            self._send("trade_blocked", {
                "decision": decision,
                "blocked_by": validation.blocked_by,
            })
            return

        # 6. Send to Flask for user confirmation
        self._send("trade_proposal", {
            "decision": decision,
            "thinking": decision.get("thinking", ""),
            "tokens": tokens,
        })

        # 7. Wait for user response (with timeout)
        # Flask puts response into a response queue specific to this agent
        user_response = self._wait_user_response(timeout=60)
        if user_response == "approved":
            self._execute_trade(decision)
            self._send("trade_executed", {"decision": decision})
        else:
            self._send("trade_rejected", {
                "decision": decision,
                "reason": user_response or "timeout",
            })

    def _send(self, msg_type: str, data: dict):
        """Send message to Flask via queue."""
        self.msg_queue.put({
            "agent_id": self.agent_id,
            "type": msg_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        })

    def stop(self):
        self.running = False

# Entry point for subprocess
def start_agent_process(agent_id, config, msg_queue):
    agent = AgentProcess(agent_id, config, msg_queue)
    agent.run()
```

### 12.6 Flask Message Router

```python
# runner/message_router.py — runs in Flask process

import multiprocessing as mp
import threading

class MessageRouter:
    """Routes messages between agent subprocesses and Flask endpoints."""

    def __init__(self):
        self.msg_queue = mp.Queue()
        self.agent_processes: dict[str, mp.Process] = {}
        self.response_queues: dict[str, mp.Queue] = {}  # per-agent response queues
        self._listener_thread = None

    def deploy_agent(self, agent_id: str, config: dict):
        """Start an agent subprocess."""
        response_q = mp.Queue()
        self.response_queues[agent_id] = response_q

        proc = mp.Process(
            target=start_agent_process,
            args=(agent_id, config, self.msg_queue),
            daemon=True,
        )
        proc.start()
        self.agent_processes[agent_id] = proc

    def stop_agent(self, agent_id: str):
        """Stop an agent subprocess."""
        if agent_id in self.agent_processes:
            self.response_queues[agent_id].put({"type": "stop"})
            self.agent_processes[agent_id].join(timeout=10)
            if self.agent_processes[agent_id].is_alive():
                self.agent_processes[agent_id].terminate()
            del self.agent_processes[agent_id]

    def approve_trade(self, agent_id: str):
        """User approved a trade proposal."""
        if agent_id in self.response_queues:
            self.response_queues[agent_id].put({"type": "approved"})

    def reject_trade(self, agent_id: str, reason: str = ""):
        """User rejected a trade proposal."""
        if agent_id in self.response_queues:
            self.response_queues[agent_id].put({"type": "rejected", "reason": reason})

    def start_listener(self):
        """Background thread that reads from message queue and dispatches."""
        def _listen():
            while True:
                msg = self.msg_queue.get()
                # Dispatch based on message type
                if msg["type"] == "trade_proposal":
                    # Push to frontend via WebSocket
                    socketio.emit("trade_proposal", msg)
                elif msg["type"] == "trade_executed":
                    socketio.emit("trade_result", msg)
                elif msg["type"] == "trade_blocked":
                    socketio.emit("trade_blocked", msg)
                elif msg["type"] == "error":
                    log_error(msg["agent_id"], msg["data"])
                # Store all messages in audit log
                save_audit_log(msg)

        self._listener_thread = threading.Thread(target=_listen, daemon=True)
        self._listener_thread.start()

    def get_status(self) -> dict:
        """Status of all running agents."""
        return {
            agent_id: {
                "pid": proc.pid,
                "alive": proc.is_alive(),
            }
            for agent_id, proc in self.agent_processes.items()
        }
```

### 12.7 User Confirmation Flow

When a deployed agent makes a trade decision:

1. Agent subprocess sends `trade_proposal` via message queue
2. MessageRouter dispatches to Flask WebSocket → frontend
3. Frontend shows notification:
   ```json
   {
     "type": "trade_proposal",
     "agent_id": "linyuan",
     "data": {
       "decision": {
         "action": "buy",
         "code": "600519.SH",
         "name": "贵州茅台",
         "qty": 100,
         "price": 1432.00,
         "reason": "PE 23x处于合理区间，回调至支撑位"
       },
       "thinking": "茅台PE 23x处于合理区间...",
       "tokens": 1247
     }
   }
   ```
4. User clicks "确认执行" → `POST /api/agents/{id}/approve` → router puts response → agent executes via tdx_service
5. User clicks "拒绝" or 60s timeout → `POST /api/agents/{id}/reject` → agent logs rejection
6. Agent sends `trade_executed` or `trade_rejected` back via queue → frontend updates

### 12.8 Persistence + Crash Recovery

**Requirement**: Agents MUST resume after any interruption — planned restart, Flask crash, agent subprocess crash, or OS restart.

**Three-layer recovery:**

**Layer 1: State Persistence (SQLite)**
Every agent action is immediately persisted:

```sql
-- Agent state table — always in sync with reality
CREATE TABLE agent_state (
    agent_id TEXT PRIMARY KEY REFERENCES agents(id),
    status TEXT NOT NULL,            -- 'running', 'stopped', 'crashed'
    last_heartbeat DATETIME,         -- updated every 60s by agent subprocess
    last_decision_time DATETIME,     -- last successful decision cycle
    last_trade_time DATETIME,        -- last executed trade
    pending_trade JSON,              -- trade awaiting user confirmation (null if none)
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Every trade and decision is recorded before execution
-- Even if process dies mid-trade, the audit trail is intact
```

**Layer 2: Flask Restart Recovery**
On Flask startup, `restore_deployed_agents()` runs automatically:

```python
def restore_deployed_agents():
    """Restart all deployed agents after Flask restart."""
    deployed = db.query("SELECT * FROM agents WHERE status = 'deployed'")
    for agent in deployed:
        state = db.query("SELECT * FROM agent_state WHERE agent_id = ?", agent.id)
        config = load_agent_config(agent.id)

        # Check if agent had a pending trade (user hadn't confirmed yet)
        if state and state.pending_trade:
            # Re-emit the pending trade to user via WebSocket
            socketio.emit("trade_proposal", {
                "agent_id": agent.id,
                "data": state.pending_trade,
                "note": "此交易在服务重启前等待确认，请重新确认"
            })

        # Restart agent subprocess
        message_router.deploy_agent(agent.id, config)
```

**Layer 3: Agent Subprocess Auto-Restart**
MessageRouter monitors agent subprocess health and auto-restarts crashed agents:

```python
class MessageRouter:
    def _health_monitor(self):
        """Runs every 60 seconds. Checks all agent subprocesses."""
        while True:
            for agent_id, proc in list(self.agent_processes.items()):
                if not proc.is_alive():
                    # Agent crashed — auto-restart
                    log_error(agent_id, f"Process died (exit code {proc.exitcode}), restarting")
                    state = db.query("SELECT * FROM agent_state WHERE agent_id = ?", agent_id)
                    config = load_agent_config(agent_id)
                    self.deploy_agent(agent_id, config)

                    # Update state
                    db.execute("UPDATE agent_state SET status = 'restarted' WHERE agent_id = ?", agent_id)
                    socketio.emit("agent_recovered", {
                        "agent_id": agent_id,
                        "message": "Agent进程意外中断，已自动恢复"
                    })

            time.sleep(60)
```

**Layer 4: Graceful Shutdown**
On Flask shutdown (SIGTERM/SIGINT):

```python
def graceful_shutdown():
    """Stop all agents cleanly, preserving state."""
    for agent_id in list(message_router.agent_processes.keys()):
        # Agent subprocess saves its state before exiting
        message_router.stop_agent(agent_id)
        db.execute("UPDATE agent_state SET status = 'stopped' WHERE agent_id = ?", agent_id)
```

**Recovery scenarios:**

| Scenario | What happens | Recovery |
|----------|-------------|----------|
| Flask restart (planned) | Graceful shutdown saves state, startup restores all agents | Auto |
| Flask crash (unplanned) | Agent subprocesses die (daemon), SQLite state intact | Startup restores |
| Agent subprocess crash | Health monitor detects, auto-restarts agent | Auto within 60s |
| User rejects during crash | Pending trade persisted in SQLite, re-emitted on restart | Auto |
| Mid-trade crash | Audit log shows last state, no double-execution (trade idempotency) | Manual check |
| Full OS restart | All processes gone, SQLite on disk, Flask service auto-starts agents | Auto on boot |

### 12.9 Agent Process Monitoring

```python
# Health check: each agent sends heartbeat every 60 seconds
# If no heartbeat for 3 minutes → mark as "unresponsive"
# Frontend shows agent status: running / unresponsive / stopped / error

@app.route('/api/agents/running')
def running_agents():
    return jsonify(message_router.get_status())

@app.route('/api/agents/<agent_id>/logs')
def agent_logs(agent_id):
    """Return recent audit log entries for this agent."""
    return jsonify(get_agent_audit_log(agent_id, limit=100))
```

---

## 13. TDX Data Verification Summary

| Data Type | TDX API | SQLite Cache | Status |
|-----------|---------|-------------|--------|
| Daily K-line (`1d`) | `get_market_data(period='1d')` | Verified ✓ works | **Ready** |
| Weekly/Monthly | `get_market_data(period='1w'/'1mon')` | Should work (same API) | To verify |
| Intraday K-line (`1m`/`5m`) | `get_market_data(period='1m'/'5m')` | Returns empty in test | **Needs investigation** |
| Stock info (PE/PB/ROE) | `get_stock_info()` | Works ✓ | **Ready** |
| Real-time snapshot | `get_market_snapshot()` | Works ✓ (live only) | **Ready** |
| Index data | `get_market_snapshot('000001.SH')` | Works ✓ | **Ready** |
| Trading calendar | `get_trading_calendar()` | Not tested | To verify |

**Phase 1**: Start with daily backtesting (proven data pipeline).
**Phase 2**: Add intraday support after resolving data access issue.

---

## 14. Implementation Order

1. **Project setup**: Create `strategy/`, `llm/`, `context/`, `runner/` module structure + `config.py` + `requirements.txt`
2. **vnpy data layer**: Install vnpy + vnpy_sqlite + vnpy-tdx, load daily K-line into SQLite, verify roundtrip
3. **Financial data cache**: Build `data/financial_cache.db` from local TDX data via tqcenter SDK
4. **LLM adapters**: `llm/base.py` + `claude.py` first, then `openai_adapter.py` + `deepseek.py`
5. **Prompt context builders**: `context/market_context.py`, `position_context.py`, `technical_context.py`, `financial_context.py`
6. **LLMStrategy base**: `strategy/base.py` inheriting vnpy StrategyTemplate, with T+1 enforcement + RedLine checks
7. **Agent personas**: 5 strategy files in `strategy/` with system prompts + knowledge boundary prompt
8. **Backtest runner**: `runner/backtest_runner.py` wrapping vnpy engine + SSE streaming + `runner/commission.py` for A-share fees
9. **API routes**: New endpoints in `app.py` (backtest + agent CRUD + SSE)
10. **Frontend migration**: Vite setup + migrate all pages from CDN to Vite + React
11. **Wire up**: AgentLab + Backtest pages connected to real APIs
12. **Agent save/evaluate**: Save backtest results to SQLite, agent comparison chart
13. **Live deploy**: Agent deployment + background threads + user confirmation
14. **Intraday support**: Fix 1m/5m data access, add intraday backtest mode
