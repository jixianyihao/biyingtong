# Trading Agent + Backtest Engine Design

## Overview

Build an LLM-driven trading agent system with 1-year backtesting capability. Each agent gets ¥100,000 initial capital and uses a large language model (Claude/GPT/DeepSeek) to make trading decisions based on historical market data.

## Architecture: Flask + SSE + SQLite + LLM

```
React (Vite) <-- SSE/polling --> Flask <---> TDX SDK (market data)
                                     <---> LLM APIs (Claude/GPT/DeepSeek)
                                     <---> SQLite (K-line cache + results)
```

No Redis/Celery. Single `python app.py` runs everything. SSE streams backtest progress in real-time.

## Project Structure

```
biyingtong/
├── app.py                     # Flask entry (routes + SSE)
├── config.py                  # Config (LLM keys, port)
├── requirements.txt
├── .env                       # API keys (gitignored)
│
├── engine/                    # Backtest engine
│   ├── __init__.py
│   ├── backtest.py            # Main backtest loop
│   ├── portfolio.py           # Virtual account (cash, positions, trades)
│   ├── data_fetcher.py        # Fetch + cache historical data from TDX
│   └── metrics.py             # Sharpe, MDD, win rate, etc.
│
├── agents/                    # Agent definitions
│   ├── __init__.py
│   ├── base.py                # Agent base class
│   ├── linyuan.py             # Value investing
│   ├── fuyou.py               # Momentum / short-term
│   ├── buffet.py              # Moat / ROE focus
│   ├── soros.py               # Reflexivity / macro hedge
│   └── quant_neutral.py       # Multi-factor market-neutral
│
├── llm/                       # Multi-model adapter
│   ├── __init__.py
│   ├── base.py                # Abstract LLM interface
│   ├── claude.py              # Anthropic SDK
│   ├── openai_adapter.py      # OpenAI SDK
│   └── deepseek.py            # DeepSeek (OpenAI-compatible)
│
├── tdx_service.py             # TDX SDK wrapper (existing)
│
├── data/                      # Local data cache
│   └── kline_cache.db         # SQLite K-line cache
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
│       │   └── EquityChart.jsx
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

## Backtest Engine

### Core Loop

```
1. Fetch/cached K-line data for all relevant stocks (entire year)
2. For each trading day (244 days in 1 year):
   a. Build context: portfolio state + market data + indicators
   b. Call LLM with agent's persona prompt + context
   c. Parse LLM response: <thinking>...</thinking><action>buy/sell/hold | code | qty | reason</action>
   d. Execute trade in virtual portfolio (check risk limits)
   e. Record: daily NAV, trade log, thinking log
   f. Emit SSE progress event
3. Calculate final metrics
4. Store results in SQLite
```

5 agents can run in parallel (each in a thread). Within each agent, days are sequential (today's decisions depend on yesterday's portfolio state).

### Portfolio (Virtual Account)

```python
class Portfolio:
    initial_capital: float = 100000
    cash: float
    positions: dict  # { code: { qty, avg_cost } }
    trades: list     # [{ date, action, code, qty, price, pnl }]
    nav_history: list  # [{ date, nav }]
    
    # Risk limits (from RedLine config)
    max_position_pct: float = 0.30
    daily_loss_limit: float = 0.03
    max_single_order: float = 200000
    
    def execute_trade(action, code, qty, price) -> TradeResult
    def get_nav(current_prices) -> float
    def check_risk_limits(action, code, qty, price) -> bool
```

### Data Fetcher + Cache

- First backtest: fetch 1 year of daily K-line from TDX for all CSI300 stocks + common A-shares (~500 stocks)
- Store in SQLite: `kline_cache` table (stock_code, date, open, high, low, close, volume)
- Subsequent backtests: read from SQLite (milliseconds vs seconds)
- Cache key: `stock_code + period + start_date + end_date`

### Metrics Calculation

```python
def calculate_metrics(nav_history, trades, benchmark_nav) -> dict:
    return {
        'total_return': float,       # 累计收益率
        'annual_return': float,      # 年化收益率
        'sharpe_ratio': float,       # 夏普比率
        'sortino_ratio': float,      # 索提诺比率
        'max_drawdown': float,       # 最大回撤
        'max_dd_duration': int,      # 最大回撤持续天数
        'win_rate': float,           # 胜率
        'profit_loss_ratio': float,  # 盈亏比
        'trade_count': int,          # 交易次数
        'turnover_rate': float,      # 换手率
        'monthly_returns': list,     # 月度收益 (for heatmap)
        'strategy_rating': str,      # A+/A/B/C/D
    }
```

## LLM Multi-Model Adapter

### Interface

```python
class LLMBase(ABC):
    @abstractmethod
    def chat(self, messages: list[dict]) -> dict:
        """Send messages, return response with content."""
        pass

class ClaudeLLM(LLMBase):     # anthropic SDK
class OpenAILLM(LLMBase):     # openai SDK
class DeepSeekLLM(LLMBase):   # openai SDK (API-compatible)
```

Model selection per agent from config:
- 林园 → Claude
- 浮游 → OpenAI GPT
- 巴菲特 → Claude
- 索罗斯 → DeepSeek
- 量化中性 → DeepSeek

### Prompt Structure (per trading day)

```
[System Prompt]
你是 {agent.name}，一位 {agent.style} 的基金经理。
{agent.system_prompt}

[Current State]
日期: {date}
账户资金: ¥{cash} | 持仓: {positions_summary} | 总资产: ¥{total_nav}

[Position Details]
{for each position}: {code} {name} {qty}股 成本¥{avg_cost} 现价¥{current_price} 盈亏{pct}

[Market Overview]
沪深300: {index_value} ({pct}) | 上证: {index_value} ({pct})

[Available Stocks - K-line summary (30-day)]
{for each stock in universe}: {code} {name} 现价{price} PE {pe} ROE {roe} 30日涨幅{pct}

请做出今日决策，严格按以下格式回复：
<thinking>你的详细分析过程</thinking>
<action>buy/sell/hold | 股票代码 | 数量 | 理由</action>
```

### Decision Parsing

- `<thinking>` → saved to thinking log, displayed in frontend
- `<action>` → parsed as structured trade instruction
- Parse failure → default to `hold` (no trade)
- Risk limit violation → trade rejected, logged

## 5 Agent Personas

| Agent | Model | Style | Decision Freq | Universe Focus |
|-------|-------|-------|---------------|----------------|
| 林园风格 | Claude | 价值投资·白酒医药消费·长期持有 | Weekly | 茅台/五粮液/片仔癀/恒瑞 |
| 浮游风格 | GPT | 短线游资·题材热点·快进快出 | Daily | 全市场热点 |
| 巴菲特风格 | Claude | 护城河·安全边际·ROE>15% | Monthly | 招行/长电/美的/伊利 |
| 索罗斯反身性 | DeepSeek | 宏观对冲·反身性·追逐趋势 | Weekly+event | ETF/黄金/大盘股 |
| 量化中性 | DeepSeek | 多因子·市值中性·低回撤 | Daily | 沪深300成分股 |

Each agent's system prompt follows the persona definition in the prototype (agent.jsx).

### Stock Universe

Each agent has a curated watchlist (matching prototype positions) plus access to the full CSI300 pool (300 stocks). The LLM can only trade stocks it has data for. The universe is pre-fetched and cached before backtest starts.

## API Endpoints

### Existing (unchanged)
- GET /api/status, /api/connect
- GET /api/market/indices, /api/market/kline, /api/market/snapshot, /api/market/snapshots
- GET /api/stocks/list, /api/stocks/info
- GET /api/account/status, /api/account/asset, /api/account/positions, /api/account/orders
- POST /api/trade/order, /api/trade/cancel
- WebSocket: quotes push

### New (Agent + Backtest)
- `GET /api/agents` — list all agent definitions (id, name, style, model, system_prompt)
- `POST /api/agents/create` — create custom agent with user-defined prompt
- `POST /api/backtest/start` — start backtest `{ agent_id, capital: 100000, start_date, end_date }` → returns `{ task_id }`
- `GET /api/backtest/{task_id}/stream` — SSE endpoint, emits:
  - `{ day, total_days, status: "thinking", context_snippet }`
  - `{ day, decision: { action, code, qty, reason } }`
  - `{ day, status: "completed", nav }`
  - `{ status: "done", metrics: {...} }`
- `GET /api/backtest/{task_id}/result` — final result with all metrics
- `GET /api/backtest/{task_id}/trades` — trade history
- `GET /api/backtest/{task_id}/thinking` — thinking log
- `POST /api/backtest/{task_id}/cancel` — cancel running backtest
- `GET /api/backtest/results` — list all completed backtests (for comparison)

## Frontend Migration (Vite + React)

### Tech Stack
- **Vite** — build tool with HMR
- **React 18** — UI framework
- **React Router** — page routing
- **@tanstack/react-query** — data fetching + SSE
- **tokens.css** — retained as-is

### Dev/Prod Setup

Dev mode:
```
Vite dev server (localhost:5173) → proxy /api/* → Flask (localhost:5000)
```

Production:
```
vite build → outputs to static/
Flask serves static/index.html + assets
```

### Page → Component Mapping

| Current file | New location | Changes |
|-------------|-------------|---------|
| common.jsx | components/Icon.jsx, Sparkline.jsx | Split into focused components |
| shell.jsx | components/Sidebar.jsx, TopBar.jsx, StatusBar.jsx | Split, real account data |
| dashboard.jsx | pages/Dashboard.jsx | + React Query |
| agent.jsx | pages/AgentLab.jsx | Real backtest data, SSE progress |
| backtest.jsx | pages/Backtest.jsx | Real backtest engine connection |
| others.jsx | pages/LiveTrading.jsx, RiskMonitor.jsx | Split into separate pages |
| screener.jsx | pages/Screener.jsx | Migrate as-is |
| editor.jsx | pages/Editor.jsx | Migrate as-is |

### AgentLab Page Changes
- Agent cards: metrics from `/api/backtest/results`
- Thinking log: real-time from SSE stream
- Position display: from portfolio state
- Compare chart: real NAV curves from backtest results
- Cost stats: from LLM token usage tracking
- Create modal: calls `/api/agents/create`

### Backtest Page Changes
- Strategy selector → Agent selector
- Parameters → backtest config (dates, capital, commission)
- Run button → starts SSE stream, shows real-time progress
- 6 metrics → from real metrics calculation
- Equity chart → real NAV history + benchmark
- Monthly heatmap → from real monthly returns
- Trade log → from real trade history
- Strategy rating → calculated from real metrics

## RedLine Integration

The existing RedLine config (12 risk parameters in localStorage) will be enforced during backtest:
- Daily loss limit → stop all trading if breached
- Max position per stock → reject oversized trades
- Min cash ratio → force hold if cash too low
- Ban ST/*ST → exclude from universe
- Cooldown period → skip trading same stock within N minutes

RedLine violations are logged and displayed in the thinking log.

## Implementation Order

1. Create backend modules: `engine/`, `agents/`, `llm/`
2. Set up Vite + React in `client/`
3. Implement data fetcher + SQLite cache
4. Implement portfolio + backtest loop
5. Implement LLM adapters (Claude first)
6. Implement agent personas
7. Build SSE streaming API
8. Migrate frontend pages to Vite components
9. Wire up AgentLab + Backtest pages to real APIs
10. Test full flow: create agent → run 1-year backtest → view results
