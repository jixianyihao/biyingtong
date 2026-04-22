# Trading Agent + Backtest Engine Design Spec

## Overview

Build an LLM-driven trading agent system with 1-year backtesting. Each agent gets ¥100,000 initial capital. All market data (K-line, financials, snapshots) comes from TDX via tqcenter SDK. No fake data, no random numbers — everything is real.

## Architecture: Flask + SSE + SQLite + LLM

```
React (Vite) <-- SSE/polling --> Flask <---> TDX SDK (market data)
                                     <---> LLM APIs (Claude/GPT/DeepSeek)
                                     <---> SQLite (K-line cache + backtest results)
```

Single `python app.py` runs everything. No Redis/Celery. SSE streams backtest progress in real-time.

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

### 2.1 Data APIs Used

| Data Type | TDX SDK Call | Purpose | Cache |
|-----------|-------------|---------|-------|
| Daily K-line | `tq.get_market_data(field_list=['Open','High','Low','Close','Volume'], period='1d', count=250)` | 1-year price history for each stock | SQLite |
| Financial data | `tq.get_stock_info(stock_code)` | PE/PB/ROE/Revenue/Profit | SQLite (monthly refresh) |
| Index data | `tq.get_market_snapshot(stock_code)` for 000001.SH, 399001.SZ, etc. | Market overview context | In-memory |
| Stock list | `tq.get_stock_list(market='5')` | Universe definition | SQLite |
| Real-time snapshot | `tq.get_market_snapshot(stock_code)` | 5-level bid/ask (live only) | Not cached |

### 2.2 Interaction Timing (Backtest)

```
Before backtest starts:
  1. Fetch stock list → get CSI300 codes (~300 stocks)
  2. For each stock: fetch 1 year daily K-line (250 bars) → store in SQLite
     - API call: tq.get_market_data(stock_list=[...all codes...], period='1d', count=250)
     - Batch fetch: can pass stock_list with up to 50 stocks per call
     - Total: ~6 API calls for all 300 stocks
  3. For each stock: fetch financial info → store in SQLite
     - API call: tq.get_stock_info(stock_code=code)
     - Total: 300 calls, but cached permanently

During backtest (no TDX calls needed — all from SQLite cache):
  For each trading day:
    1. Read K-line from SQLite for this date range
    2. Read financial data from SQLite
    3. Calculate technical indicators (MA/MACD/RSI) in Python
    4. Build prompt context
    5. Call LLM (this is the only external call during backtest)
    6. Simulate execution in portfolio

TDX is NOT called during the backtest loop itself. All data is pre-cached.
```

### 2.3 Interaction Timing (Live Trading — future)

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

### 3.1 Agent Style — Guidance, Not Hard Restrictions

Each agent has an investment philosophy described in its system prompt. The LLM is *guided* by this philosophy but NOT forced into specific stocks. For example, the "林园" agent prefers 白酒/医药/消费 but CAN buy tech stocks if it believes it's a good opportunity.

The guidance comes from the system prompt only. No code-level restrictions on stock selection.

### 3.2 Five Pre-defined Agents

#### Agent 1: 林园风格 (Lin Yuan Style)
- **Model**: Claude
- **Philosophy**: 价值投资 — 寻找"印钞机"式企业，重仓龙头，长期持有
- **Preferences**: 白酒、医药、消费行业；高ROE(>15%)、高毛利率(>30%)、低PE(低于行业均值20%)
- **Trading pattern**: Low frequency, large positions, long holding periods
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
- **Preferences**: 热门题材、涨停板、成交量异动、板块轮动
- **Trading pattern**: High frequency, smaller positions, short holding (1-5 days), strict stop-loss
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
- **Preferences**: 银行、公用事业、消费龙头；高ROE(>15%)、低PB、稳定分红
- **Trading pattern**: Very low frequency, concentrated positions, monthly review
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
- **Preferences**: 宏观趋势、ETF、黄金、做空机会、情绪极端
- **Trading pattern**: Event-driven, concentrated bets, can hold large cash position
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
- **Preferences**: 因子模型(动量/反转/质量/价值)、沪深300成分股、每日调仓
- **Trading pattern**: Very high frequency, many small positions, systematic
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

## 4. Backtest Engine — Detailed

### 4.1 Matching Rules: 五档撮合 + T+1

**Price determination:**
- **Buy order**: executed at next trading day's **open price** (simulates buying at ask price at market open)
- **Sell order**: executed at next trading day's **open price** (simulates selling at bid price at market open)
- **Slippage**: add ±0.1% random slippage to simulate real bid-ask spread

**T+1 enforcement:**
- Stocks bought on day D cannot be sold until day D+1 at earliest
- Portfolio tracks `buy_date` per position for T+1 check
- A stock that was bought today and LLM says "sell" → trade rejected, logged as "T+1 violation"

**Board lot rules:**
- A-shares trade in 100-share lots (手)
- Minimum buy: 100 shares (1手)
- Sell: can sell any amount if holding (odd lots allowed for partial sells)

### 4.2 Commission (A股标准费率)

All amounts in ¥, calculated to 2 decimal places:

| Fee | Rate | Charged When |
|-----|------|-------------|
| Broker commission | 0.025% of trade value | Buy + Sell |
| Stamp tax (印花税) | 0.1% of trade value | **Sell only** |
| Transfer fee (过户费) | 0.001% of trade value | Buy + Sell |
| Minimum commission | ¥5 per order | If calculated < ¥5 |

Example: Buy ¥100,000 of stock:
- Commission: 100000 × 0.025% = ¥25.00
- Transfer fee: 100000 × 0.001% = ¥1.00
- Total cost: ¥26.00

Example: Sell ¥100,000 of stock:
- Commission: 100000 × 0.025% = ¥25.00
- Stamp tax: 100000 × 0.1% = ¥100.00
- Transfer fee: 100000 × 0.001% = ¥1.00
- Total cost: ¥126.00

**Precision: All monetary calculations use Python `Decimal` type to avoid floating-point errors. No `float` for money.**

### 4.3 Portfolio State Machine

```
Portfolio states per day:
  1. OPEN: new day begins, load market data
  2. AGENT_DECIDE: LLM returns decision
  3. RISK_CHECK: validate against RedLine rules
  4. EXECUTE: simulate trade at next-day open price
  5. SETTLE: calculate NAV, update positions
  6. RECORD: save daily snapshot

Portfolio data per day:
  {
    date: "2025-06-15",
    nav: 368000.00,           # 总资产 = cash + positions_value
    cash: 87532.00,           # 可用现金
    positions: {
      "600519.SH": { qty: 200, avg_cost: 1402.00, buy_date: "2025-06-10", current_price: 1432.00 },
      "000858.SZ": { qty: 300, avg_cost: 145.00, buy_date: "2025-06-12", current_price: 152.30 },
    },
    daily_pnl: 1234.00,       # 今日盈亏
    daily_pnl_pct: 0.34,      # 今日盈亏%
    trades: [...],             # 今日成交
    thinking: "...",           # Agent思考过程
    blocked: [...],            # 被拦截的操作
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

## 5. Safety — Four-Layer Protection

### Layer 1: RedLine Interception

Before any trade executes, check all RedLine rules:

| Rule | Check | Action if Violated |
|------|-------|-------------------|
| 日亏损上限 (dailyLoss) | If today's loss > X% of NAV | Block ALL trades for rest of day |
| 单票仓位上限 (positionMax) | If this trade makes single stock > X% | Reject trade |
| 单股集中度 (stockMax) | If total position in one stock > X% | Reject buy |
| 最低现金比例 (cashMin) | If cash < X% after trade | Reject buy |
| 单笔金额上限 (orderMax) | If trade value > ¥X | Reject trade |
| 禁止追涨停 (banLimitUp) | If stock is at limit-up price | Reject buy |
| 禁止ST (banST) | If stock name contains ST/\*ST | Reject trade |

All violations logged to `blocked_trades` and shown in thinking log.

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
├── config.py                  # Config (LLM keys, port, defaults)
├── requirements.txt
├── .env                       # API keys (gitignored)
│
├── engine/                    # Backtest engine
│   ├── __init__.py
│   ├── backtest.py            # Main backtest loop + thread management
│   ├── portfolio.py           # Virtual account (Decimal precision)
│   ├── data_fetcher.py        # Fetch from TDX + SQLite cache
│   ├── indicators.py          # MA/MACD/RSI/Bollinger calculations
│   ├── commission.py          # A-share fee calculation
│   └── metrics.py             # Sharpe/MDD/win rate/rating
│
├── agents/                    # Agent definitions
│   ├── __init__.py
│   ├── base.py                # AgentBase class + tool definitions
│   ├── linyuan.py             # System prompt + style config
│   ├── fuyou.py
│   ├── buffet.py
│   ├── soros.py
│   └── quant_neutral.py
│
├── llm/                       # Multi-model adapter
│   ├── __init__.py
│   ├── base.py                # LLMBase abstract class
│   ├── claude.py
│   ├── openai_adapter.py
│   └── deepseek.py
│
├── tdx_service.py             # Existing TDX wrapper
│
├── data/                      # Local cache (gitignored)
│   └── kline_cache.db         # SQLite: kline + financials + backtest results
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

## 10. Implementation Order

1. **Backend foundation**: Create `engine/`, `agents/`, `llm/` module structure + `config.py`
2. **Data layer**: `data_fetcher.py` + SQLite cache + `indicators.py`
3. **Portfolio**: `portfolio.py` with Decimal precision + T+1 + commission
4. **LLM adapters**: `claude.py` first, then openai + deepseek
5. **Agent personas**: 5 agent files with system prompts
6. **Backtest loop**: `backtest.py` with SSE streaming
7. **API routes**: New endpoints in `app.py`
8. **Frontend**: Vite setup + migrate all pages
9. **Wire up**: AgentLab + Backtest pages connected to real APIs
10. **Test**: Full end-to-end: create agent → backtest 1 year → view results
