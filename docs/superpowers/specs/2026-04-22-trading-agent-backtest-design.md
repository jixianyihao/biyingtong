# Trading Agent + Backtest Engine Design Spec

> **v2 — rewritten 2026-04-22** after requirements review against prototype. 13 decisions locked in § 0. Section numbering and architecture choices differ materially from v1; treat this as the canonical document.

---

## 0. Decision Log (2026-04-22 Review)

Review compared v1 spec against the prototype UI in `static/src/*.jsx` (identical to `基于通达信的量化交易软件-handoff/untitled/project/src/*.jsx`). Fifteen inconsistencies + six LLM-expert concerns were surfaced. The following 13 decisions finalize the design:

| # | Topic | Decision |
|---|-------|----------|
| D1 | **Knowledge leakage** | Force every backtest to span the LLM's `training_cutoff`. Results page shows pollution-zone metrics and clean-zone metrics separately. If divergence is large, user knows the LLM is leaking. |
| D2 | **Tool architecture** | LLM uses strict-JSON tool_use (Anthropic `tools` / OpenAI `function_calling` / Gemini `functionDeclarations`). Each agent has an `allowed_tools` whitelist. No XML pipe-parsing. |
| D3 | **AutonomousScheduler** | MVP implements only `daily/weekly/monthly/intraday_5m`. Prototype's 24h timeline panel is kept visually but rendered with mock data + "Phase 2" labels. Event triggers (news/price/tech/collab) are deferred. |
| D4 | **Dual-mode backtest** | Backtest page has two tabs: **Agent Backtest** (LLM-driven, § 6.2) and **Rule Backtest** (均线突破 / 网格套利 / 多因子 via `vnpy_ctastrategy`, § 6.3). They share the same infrastructure (commission, statistics, rating, heatmap). |
| D5 | **Initial capital** | Default ¥1,000,000. User selects from `{100k, 500k, 1M, 5M}`. Matches prototype (v1's ¥100,000 was wrong). |
| D6 | **Model list** | Real-world callable models as of today: Claude Opus 4.7 (1M), Claude Sonnet 4.6, Claude Haiku 4.5, GPT-5, GPT-4o, DeepSeek V3, Gemini 2.0 Pro. No fictional names. Registry in DB (§ 5.5). |
| D7 | **Agent health formula** | `health = max(0, 100 − violations_7d×3 − backtest_deviation_pts×2 − parse_failures_7d×1)`. Trust rating: A+ ≥ 90, A 80–89, B 60–79, C < 60. Defined in § 8. |
| D8 | **RedLine vs per-agent rules** | Two layers. **Global RedLine** is an immutable hard ceiling; all agents must comply. **Per-agent rules** can be stricter but never looser. UI warns when per-agent threshold exceeds RedLine and clamps it. |
| D9 | **Multi-instance mode** | An `agent` = `persona_id` + `model_id` + `validation_rules_override`. Same persona ("林园价值投资") can be instantiated with Claude / GPT / DeepSeek for head-to-head comparison. |
| D10 | **Vendor neutrality** | LLM layer is vendor-neutral. A canonical internal `ToolSpec` + message format is translated per vendor. Prompt caching is abstracted (`cacheable_prefix_len` parameter). |
| D11 | **Baseline strategies** | Every agent backtest automatically runs three baselines for comparison: **HS300 buy-and-hold**, **random-trade agent**, **fixed-rule agent** (PE<15 buy / PE>30 sell). Result page overlays 4 curves. |
| D12 | **Prompt versioning** | Every edit to `system_prompt` creates a new version in `agent_prompt_versions`. Each backtest is linked to the exact version used. Rollback button. No diff UI (defer to Phase 2). |
| D13 | **Next action** | Rewrite this Spec in-place. Afterwards run `superpowers:writing-plans` for an implementation plan. |

### 0.1 What's Deferred to Phase 2+

- Event-driven scheduler triggers (news, price events, technical signals, anomaly alerts, agent-to-agent collaboration)
- News/announcement data pipelines (Wind, 雪球, 东财 crawler)
- Strategy marketplace + subscription
- Prompt diff UI
- Multi-agent signal sharing
- Intraday 1m/5m backtest (pending TDX data-access fix)
- "AI 风控提示" on manual order placement (LiveTrading page)

---

## 1. Overview

Build an LLM-driven trading agent system with 1-year backtesting on A-shares. Three architectural pillars differ from v1:

1. **Dual-mode backtest** — Both LLM agents and traditional rule strategies are first-class. Rule strategies use vnpy's built-in CTA templates; LLM agents use our `LLMStrategy` extension. Everything above the strategy layer is shared.
2. **Vendor-neutral LLM layer** — A single `LLMBase` abstract with adapters for Anthropic, OpenAI (and OpenAI-compatible providers like DeepSeek), and Gemini. Agents specify a model ID; switching providers requires zero agent code changes.
3. **Persona/Model separation** — A "persona" is the philosophy + prompt. An "agent" is `persona × model × rules_override`. One persona can spawn multiple agent instances on different models.

Everything else — backtest matching, NAV tracking, commission, positions — reuses vnpy (VeighNa) directly.

### 1.1 What vnpy provides (reuse directly)

| Component | vnpy Module | What it gives us |
|-----------|------------|-----------------|
| Backtest engine (portfolio) | `vnpy_portfoliostrategy.BacktestingEngine` | Multi-stock replay, order matching, NAV, daily stats |
| Backtest engine (single-asset CTA) | `vnpy_ctastrategy.BacktestingEngine` | For rule-mode backtests (均线突破 / 网格 / factor) |
| Data storage | `vnpy_sqlite` | SQLite for K-line via BaseDatabase API |
| Data loading | `vnpy-tdx` | Historical K-line from TDX |
| Strategy templates | `StrategyTemplate` (both portfolio + CTA variants) | `on_bars()` / `on_bar()` callbacks, `buy()`/`sell()` API |
| Technical indicators | `vnpy.trader.tech.ArrayManager` | MA/MACD/RSI/Bollinger |
| Risk management | `vnpy_riskmanager` | Pre-trade flow control |
| Performance metrics | `calculate_statistics()` | Sharpe, max drawdown, return/dd ratio |
| Data objects | `vnpy.trader.object` | `BarData`, `OrderData`, `TradeData`, `PositionData` |

### 1.2 What we build

| Component | Purpose |
|-----------|---------|
| `LLMStrategy` (inherits vnpy `StrategyTemplate`) | Calls LLM on each rebalance bar via tool_use loop |
| `llm/` adapter layer | Vendor-neutral chat + tool_use + caching abstraction |
| `personas/` definitions | 5 built-in personas + user-created |
| `tools/` callables | Backed by SQLite cache during backtest, by `tdx_service` live |
| A-share specifics | T+1, exact commission, board lots |
| SSE streaming | Real-time backtest progress |
| Flask API | REST + SSE endpoints |
| Subprocess runner | Live agent deployment with MQ + crash recovery |
| `config_validator/` | Configurable rule engine (two layers) |
| `rating/` | Agent health + strategy rating formulas |

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        React SPA (Vite build)                         │
│   Dashboard · AgentLab · Backtest · RiskMonitor · LiveTrading · ...   │
└──────────┬──────────────────────────────┬────────────────────────────┘
           │ REST + SSE                   │ WebSocket (quotes + agent)
           ▼                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Flask Server (app.py)                         │
│                                                                       │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│   │ REST / SSE API  │  │ WebSocket Hub   │  │ Message Router      │  │
│   └─────────────────┘  └─────────────────┘  └──────┬──────────────┘  │
│                                                     │                 │
│   ┌─────────────────┐  ┌─────────────────┐  ┌──────▼──────────────┐  │
│   │ Backtest Runner │  │ RedLine Engine  │  │ Agent Process Pool  │  │
│   │ (Agent + Rule)  │  │ (global)        │  │ (multiprocessing.Q) │  │
│   └────────┬────────┘  └─────────────────┘  └──────┬──────────────┘  │
│            │                                        │                 │
│   ┌────────▼─────────────────────────────┐  ┌──────▼──────────────┐  │
│   │    vnpy BacktestingEngine(s)          │  │ tdx_service (live)  │  │
│   │  Portfolio ←→ CTA (two flavors)       │  │  tqcenter SDK        │  │
│   └────────┬──────────────────────────────┘  └──────────────────────┘  │
└────────────┼──────────────────────────────────────────────────────────┘
             │
    ┌────────┴────────┐ ┌──────────────────┐ ┌────────────────────────┐
    │  vnpy_sqlite    │ │ financial_cache  │ │ agent_state.db        │
    │  K-line bars    │ │ PE / PB / ROE    │ │ configs / audit / MQ  │
    └─────────────────┘ └──────────────────┘ └────────────────────────┘

                  ┌──────────────────────────────────────┐
                  │       LLM Layer (vendor-neutral)     │
                  │  ┌─────────┬─────────┬────────────┐  │
                  │  │ Claude  │ OpenAI  │ Gemini     │  │
                  │  │ adapter │ compat  │ adapter    │  │
                  │  └─────────┴─────────┴────────────┘  │
                  │       Canonical ToolSpec + Cache     │
                  └──────────────────────────────────────┘
```

Key points:

- **Three SQLite databases** separated by concern and locking characteristics:
  - `vnpy_data.db` — K-line (vnpy-managed, heavy reads)
  - `financial_cache.db` — PE/PB/ROE (monthly refresh)
  - `agent_state.db` — agents, prompt versions, backtest results, audit log (WAL mode, concurrent writes)
- **RedLine Engine** is a server-side singleton, not per-agent. Every order from every agent passes through it.
- **Agent Process Pool** is the live execution path. One subprocess per deployed agent. Backtest does not use subprocesses (runs in Flask's thread pool since it's short-lived).

---

## 3. TDX Integration

### 3.1 Two TDX Data Paths

Unchanged from v1. Summary:

| Purpose | Module | API | When |
|---------|--------|-----|------|
| Backtest K-line | `vnpy-tdx` datafeed | `query_bar_history` → `vnpy_sqlite` | Pre-backtest |
| Live data / trading | `tqcenter` SDK | `get_market_snapshot`, `order_stock` | Live only |
| Financial data (PE/PB/ROE) | `tqcenter` SDK | `get_stock_info` | Both (monthly cache) |

### 3.2 Financial Data Cache

```sql
CREATE TABLE financial_data (
    stock_code  TEXT,
    date        DATE,
    pe          REAL,
    pb          REAL,
    roe         REAL,
    gross_margin REAL,
    revenue_growth REAL,
    net_profit_growth REAL,
    PRIMARY KEY (stock_code, date)
);
```

Refreshed monthly from local TDX data. Never called during backtest loop.

### 3.3 Trading Calendar

`tq.get_trading_calendar()` is verified in spike before implementation (§ 17). If unavailable, fall back to: `vnpy_sqlite` K-line dates as proxy for trading days (any date with at least one HS300 constituent bar = trading day).

---

## 4. Agent Design — Persona + Model + Rules

### 4.1 Four-Dimensional Agent Model (updated)

An **Agent Instance** is defined by four separable dimensions:

| Dimension | Description | Change from v1 |
|-----------|-------------|----------------|
| **Persona** | Investment philosophy + system prompt + default stock pool + default schedule. Reusable across instances. | **New: extracted as a shareable entity** |
| **Model** | Specific LLM to call (e.g. `claude-opus-4-7` or `deepseek-v3`) | **New: separated from persona** |
| **Rules Override** | Per-agent validation_rules that are stricter than global RedLine | Same concept, clarified RedLine relationship |
| **Capital + Status** | ¥ allocated + lifecycle state | Same |

Schema:

```sql
CREATE TABLE personas (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    style_desc       TEXT,
    system_prompt    TEXT NOT NULL,
    default_pool     JSON,            -- list of stock codes
    pool_filter      JSON,            -- for dynamic refresh
    default_schedule TEXT,            -- 'daily' | 'weekly' | 'monthly' | 'intraday_5m'
    default_rules    JSON,            -- starting-point rules (still ≥ RedLine)
    allowed_tools    JSON,            -- whitelist of tool names
    is_builtin       BOOLEAN DEFAULT 0,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agents (
    id                  TEXT PRIMARY KEY,
    persona_id          TEXT NOT NULL REFERENCES personas(id),
    model_id            TEXT NOT NULL REFERENCES llm_models(id),
    display_name        TEXT,         -- e.g. "林园 · Claude Opus 4.7"
    rules_override      JSON,         -- per-instance overrides (still ≥ RedLine)
    initial_capital     DECIMAL(15,2) DEFAULT 1000000,
    status              TEXT DEFAULT 'created',
                                     -- 'created' | 'backtesting' | 'backtested' |
                                     -- 'deployed' | 'stopped' | 'crashed'
    subprocess_pid      INTEGER,
    health_score        INTEGER DEFAULT 100,
    trust_rating        TEXT DEFAULT 'A',
    current_prompt_version INTEGER,   -- FK to agent_prompt_versions
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 Multi-Instance Mode

```
Persona: 林园风格 (linyuan)
         ├── Agent instance #1: linyuan + claude-opus-4-7
         ├── Agent instance #2: linyuan + gpt-5
         └── Agent instance #3: linyuan + deepseek-v3

User compares head-to-head: does the same prompt produce different
behaviors across models? Different decision quality? Different cost?
```

Persona edits propagate to all instances on next decision. Each instance's `rules_override` is independent. Backtest results track both `persona_id` and `model_id`.

### 4.3 Five Built-in Personas

| ID | Name | Default Model | Philosophy | Pool Size | Schedule |
|----|------|---------------|------------|-----------|----------|
| `linyuan` | 林园风格 | claude-opus-4-7 | 价值投资 · 白酒医药消费 · 长期持有 | 40 | weekly |
| `fuyou` | 浮游风格 | gpt-5 | 短线游资 · 题材热点 · 快进快出 | 50 (monthly refresh) | daily |
| `buffet` | 巴菲特风格 | claude-sonnet-4-6 | 护城河 · 安全边际 · ROE > 15% | 30 | monthly |
| `soros` | 索罗斯反身性 | deepseek-v3 | 宏观对冲 · 反身性 · 趋势跟随 | 35 | weekly |
| `quant_neutral` | 量化中性 | deepseek-v3 | 多因子 · 市值/行业中性 · 低回撤 | 50 (weekly refresh) | daily |

Concrete stock pools, system prompts, and `default_rules` are identical to v1 § 3.4 and are not reproduced here to save space — they live in `personas/` as Python modules seeded into the DB on first boot.

### 4.4 Agent Decision Cycle

The cycle is **tool_use driven**, not a single-shot chat. Tools are real Python functions exposed to the LLM.

```
On rebalance event for agent instance A:

Step 1: FETCH CONTEXT (cheap, deterministic, pre-LLM)
  ├── Load portfolio state (positions, cash, buy_dates for T+1)
  ├── Load index snapshot
  ├── Today's date
  └── Agent's persona_prompt + allowed_tools list

Step 2: BUILD INITIAL PROMPT
  ├── [cache] System prompt = persona.system_prompt + knowledge boundary (§ 11.2)
  ├── [cache] Tools spec (static)
  ├── [fresh] Brief portfolio snapshot + date
  └── "请基于工具调用获取你需要的数据，然后做出决策。"

Step 3: TOOL_USE LOOP (until agent outputs place_decision or max 10 turns)
  Loop:
    a. Send messages to LLM
    b. LLM returns either:
         (i) tool_call: { name, input }  →  execute → append result → continue
         (ii) place_decision tool_call   →  exit loop with decision
    c. Hard cap: 10 iterations (abort to 'hold' if exceeded)

Step 4: VALIDATE (§ 7)
  ├── Global RedLine checks
  ├── Per-agent rules checks
  └── If either fails: block trade, record reason, notify

Step 5: EXECUTE
  ├── Backtest: vnpy engine's buy()/sell()
  ├── Live: message → Flask → user confirm → tdx_service.place_order()
  └── Record trade + thinking + token usage + prompt version

Step 6: PERSIST
  ├── Save thinking, tool calls, decision
  ├── Update agent_state.db last_decision_time + heartbeat
  └── Emit SSE event
```

**Why tool_use over v1's pre-filled prompt:**

1. Context is dramatically smaller — agent fetches only what it needs
2. Per-agent tool whitelist becomes enforceable (v1 had no enforcement mechanism)
3. 100% JSON schema compliance on decision output (no XML regex fragility)
4. Natural integration with Anthropic/OpenAI/Gemini tool-use APIs
5. Prompt caching benefit is larger (static system + tools definition)

### 4.5 Tools

All tools are declared once in `tools/__init__.py` as a `ToolSpec` list. Each agent's `allowed_tools` is a subset.

| Tool | Input | Output | Data Source | Available in Whitelist? |
|------|-------|--------|-------------|-------------------------|
| `get_kline` | code, period, count | OHLCV array | `vnpy_sqlite` (backtest) / `tdx_service` (live) | Yes |
| `get_snapshot` | code | Current quote + 5-level | Last bar (backtest) / `tdx_service` (live) | Yes |
| `get_financials` | code | PE, PB, ROE, margins, growth | `financial_cache.db` | Yes |
| `get_technical` | code, indicator | MA/MACD/RSI/BOLL values | Computed on-demand from K-line | Yes |
| `get_index` | index_code | Today's index snapshot | Cache | Yes |
| `get_portfolio` | (none) | Current positions + cash | vnpy engine state (backtest) / `tdx_service` (live) | Yes |
| `get_news` | code | **Phase 2 only** — returns empty list in MVP | Stub | Yes (returns empty) |
| `place_decision` | action, code, qty, reason | Structured decision object (terminates tool loop) | N/A | **Always granted** |

`place_decision` is the **terminator tool**. Any other order-placing path is forbidden — the execution layer owns actual order dispatch to vnpy or tdx_service, not the LLM.

---

## 5. LLM Integration — Vendor-Neutral

### 5.1 Architecture Principles

1. **Canonical message format** — our internal `Message` dataclass is vendor-agnostic. Each adapter translates it.
2. **Canonical tool spec** — `ToolSpec(name, description, input_schema_json)` is translated per vendor.
3. **Explicit cacheable prefix** — caller specifies how many messages from the start can be cached. Each adapter applies its vendor's caching mechanism (or no-op if unsupported).
4. **Uniform return** — `LLMResponse(messages, tool_calls, stop_reason, usage)` regardless of vendor.
5. **Vendor-isolated failures** — any vendor's API error surfaces as a typed `LLMError` so upper layers can retry/fallback without vendor-specific code.

### 5.2 LLMBase Abstract

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict        # JSON Schema

@dataclass
class Message:
    role: Literal['system', 'user', 'assistant', 'tool']
    content: str | list       # list for multi-block (tool_use, tool_result)
    tool_call_id: str | None = None

@dataclass
class ToolCall:
    id: str
    name: str
    input: dict

@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    cached_read_tokens: int = 0     # for Anthropic + DeepSeek
    cached_write_tokens: int = 0    # for Anthropic prompt-caching write

@dataclass
class LLMResponse:
    messages: list[Message]
    tool_calls: list[ToolCall]
    stop_reason: str      # 'end_turn' | 'tool_use' | 'max_tokens' | 'error'
    usage: Usage

class LLMBase(ABC):
    provider: str
    model_id: str
    training_cutoff: str      # ISO date, e.g. "2026-01-31"

    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        cacheable_prefix_len: int = 0,  # cache first N messages
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> LLMResponse: ...

class LLMError(Exception):
    """Typed error from any adapter."""
    def __init__(self, provider: str, kind: str, message: str, retryable: bool):
        self.provider = provider; self.kind = kind
        self.retryable = retryable; super().__init__(message)
```

### 5.3 Four Adapters

Each adapter translates `Message`/`ToolSpec` to its vendor's native format and back.

| Adapter | Class | SDK | Tool-Use Format | Caching |
|---------|-------|-----|----------------|---------|
| Anthropic | `ClaudeLLM` | `anthropic` | `tools=[{name, description, input_schema}]`, response blocks `tool_use` / `text` | `cache_control: {type: "ephemeral"}` on system + tools + first N user msgs |
| OpenAI-compatible (OpenAI, DeepSeek, moonshot, 百川, etc.) | `OpenAILLM` (takes `base_url`) | `openai` | `tools=[{type:"function", function:{...}}]`, response `tool_calls` | Automatic for prefixes ≥1024 tokens (no explicit knob); DeepSeek automatic |
| Gemini | `GeminiLLM` | `google-generativeai` | `tools=[{function_declarations: [...]}]`, response `functionCall` | `CachedContent` objects (requires ≥32K tokens in cached segment, MVP skip) |
| Mock (testing) | `MockLLM` | — | Returns canned responses | No-op |

### 5.4 Vendor-Neutral ToolSpec Translation

```python
# Canonical:
ToolSpec(
    name="get_kline",
    description="获取 K 线数据",
    input_schema={
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "period": {"type": "string", "enum": ["1d", "1w", "1M"]},
            "count": {"type": "integer", "minimum": 1, "maximum": 500}
        },
        "required": ["code", "period", "count"]
    }
)

# Anthropic translation:
{
    "name": "get_kline",
    "description": "获取 K 线数据",
    "input_schema": {...}   # same JSON Schema
}

# OpenAI / DeepSeek translation:
{
    "type": "function",
    "function": {
        "name": "get_kline",
        "description": "获取 K 线数据",
        "parameters": {...}  # same JSON Schema, key renamed
    }
}

# Gemini translation:
{
    "function_declarations": [{
        "name": "get_kline",
        "description": "获取 K 线数据",
        "parameters": {...}  # Gemini accepts OpenAPI-ish JSON Schema
    }]
}
```

### 5.5 Model Registry

```sql
CREATE TABLE llm_models (
    id                  TEXT PRIMARY KEY,
    provider            TEXT NOT NULL,        -- 'anthropic' | 'openai' | 'deepseek' | 'gemini'
    display_name        TEXT NOT NULL,
    api_model_id        TEXT NOT NULL,        -- exact string to pass to SDK
    training_cutoff     DATE NOT NULL,        -- critical for § 11
    pricing_input_per_1m   DECIMAL(8,4),      -- USD per 1M input tokens
    pricing_output_per_1m  DECIMAL(8,4),      -- USD per 1M output tokens
    pricing_cache_read_per_1m DECIMAL(8,4),   -- USD; 0 if vendor doesn't surface separately
    pricing_cache_write_per_1m DECIMAL(8,4),  -- Anthropic only
    supports_tool_use   BOOLEAN DEFAULT 1,
    max_tokens_out      INTEGER DEFAULT 4096,
    enabled             BOOLEAN DEFAULT 1
);
```

**Seed data (2026-04-22 snapshot):**

| id | provider | display_name | api_model_id | cutoff | in/out $/1M | cache_read $/1M |
|----|----------|--------------|--------------|--------|-------------|----------------|
| `claude-opus-4-7` | anthropic | Claude Opus 4.7 (1M) | `claude-opus-4-7` | 2026-01-31 | 15 / 75 | 1.5 |
| `claude-sonnet-4-6` | anthropic | Claude Sonnet 4.6 | `claude-sonnet-4-6` | 2026-01-31 | 3 / 15 | 0.3 |
| `claude-haiku-4-5` | anthropic | Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | 2025-07-31 | 1 / 5 | 0.1 |
| `gpt-5` | openai | GPT-5 | (confirmed name at implementation time) | 2025-10-31 | (seed at impl) | auto |
| `gpt-4o` | openai | GPT-4o | `gpt-4o` | 2023-10-31 | 2.5 / 10 | auto |
| `deepseek-v3` | deepseek | DeepSeek V3 | `deepseek-chat` | 2025-07-31 | 0.14 / 0.28 | 0.014 |
| `gemini-2-pro` | gemini | Gemini 2.0 Pro | `gemini-2.0-pro` | 2025-08-31 | (seed at impl) | — |

Values marked "(seed at impl time)" will be looked up at implementation; actual CLI-accessible constants live in `llm/models.py`.

### 5.6 Decision Parsing via Tool_Use

Old v1 XML parser is **deleted**. Instead:

```python
# The place_decision tool's JSON schema:
place_decision_spec = ToolSpec(
    name="place_decision",
    description="Record your final trading decision. Calling this ends the decision loop.",
    input_schema={
        "type": "object",
        "properties": {
            "action":   {"type": "string", "enum": ["buy", "sell", "hold"]},
            "code":     {"type": "string",
                         "description": "股票代码 (如 600519.SH)。action=hold 时留空。"},
            "qty":      {"type": "integer", "minimum": 0,
                         "description": "股数。买入需 ≥100 且 % 100。卖出任意。"},
            "reason":   {"type": "string", "minLength": 20, "maxLength": 500},
            "thinking": {"type": "string",
                         "description": "完整分析推理。不限长度。"}
        },
        "required": ["action", "reason", "thinking"]
    }
)
```

Validation happens on the parsed JSON directly (not on prose). T+1 check, board-lot check, cash check all occur on this structured object.

### 5.7 Token Cost Tracking with Cache

```python
class LLMCallTracker:
    def record(self, usage: Usage, model_id: str):
        pricing = db.get_model_pricing(model_id)
        input_cost  = (usage.input_tokens - usage.cached_read_tokens) / 1_000_000 * pricing.input_per_1m
        cached_cost = usage.cached_read_tokens / 1_000_000 * pricing.cache_read_per_1m
        write_cost  = usage.cached_write_tokens / 1_000_000 * (pricing.cache_write_per_1m or pricing.input_per_1m * 1.25)
        output_cost = usage.output_tokens / 1_000_000 * pricing.output_per_1m
        total_usd   = input_cost + cached_cost + write_cost + output_cost
        # persist to audit + return USD / CNY
```

Display in backtest result page: "累计调用 1,220 次，缓存命中 78%，总 Token 987K（其中缓存 714K），成本 ¥ 128.40（未缓存情况下约 ¥ 518）"

### 5.8 Prompt Caching Strategy

Every agent backtest follows this caching pattern:

```python
messages = [
    Message(role='system', content=PERSONA_SYSTEM_PROMPT + KNOWLEDGE_BOUNDARY),
    # ^^^ cacheable_prefix_len will include this
    Message(role='user', content=f"当前日期: {date}\n账户快照: {snapshot}"),
]
tools = [place_decision_spec, get_kline_spec, ...]   # cacheable

# First bar: cache miss on system+tools. Subsequent bars: cache hit.
response = llm.chat(
    messages=messages,
    tools=tools,
    cacheable_prefix_len=1,  # system message is cached
    temperature=0.0,
)
```

- **System prompt + tool definitions** are large (~2-3K tokens) and static across all 244 bars → perfect cache candidates
- Per-bar user message is small (~200 tokens) and fresh → never cached
- Anthropic cache TTL is 5 minutes; backtest bars fire in rapid succession so cache stays warm
- Live agents with sparse rebalances (weekly/monthly) will usually miss cache — that's acceptable, the volume is low

---

## 6. Backtest Engine — Dual Mode

### 6.1 Shared Infrastructure

Both agent mode and rule mode share:

- `vnpy_sqlite` K-line database
- Commission calculator (§ 6.5)
- T+1 enforcement (§ 6.5)
- Board-lot enforcement (§ 6.5)
- RedLine validation (§ 7)
- Baseline overlay (§ 6.4)
- Metric computation + strategy rating (§ 9)
- SSE streaming wrapper
- Result persistence schema (§ 6.7)

### 6.2 Agent Mode (LLM-driven)

Uses `vnpy_portfoliostrategy.BacktestingEngine` (multi-asset portfolio) + our `LLMStrategy`:

```python
from vnpy_portfoliostrategy import BacktestingEngine
from vnpy_portfoliostrategy.template import StrategyTemplate

class LLMStrategy(StrategyTemplate):
    def on_bars(self, bars: dict[str, BarData]):
        if not self._should_rebalance(bars):
            return
        agent_runtime = self.get_agent_runtime()
        decision = agent_runtime.decide(bars, self.get_portfolio_state())
        if decision.blocked:
            self._log_blocked(decision)
            return
        self._execute_via_vnpy(decision)
```

Invoked by `BacktestRunner.run_agent(...)`.

### 6.3 Rule Mode (Traditional Strategies)

Uses `vnpy_ctastrategy.BacktestingEngine` + built-in templates that we wrap. Three seeded rule strategies match the prototype:

| ID | Name | vnpy Template | Params |
|----|------|---------------|--------|
| `ma_v3` | 均线突破 V3.2 | Custom (MA cross + volume filter) | fast=5, slow=20, vol_ratio=1.5 |
| `grid` | 网格套利 · 大盘股 | Custom grid strategy | upper=1.05, lower=0.95, step=0.01 |
| `factor` | 多因子选股 | Custom (composite rank) | factors=['momentum', 'value', 'quality'], top_n=20 |

Invoked by `BacktestRunner.run_rule(strategy_id, params)`.

**No LLM is involved in rule mode.** Cheaper and faster (seconds vs. minutes). Useful for:
- Benchmarking LLM agents (users want to see "is AI actually better?")
- Users who don't want to pay LLM costs
- Regression testing — if rule backtest still gets same Sharpe tomorrow, infra isn't broken

### 6.4 Baseline Strategies (auto-overlaid on every backtest)

Every backtest result includes three additional runs for comparison:

| Baseline | Description | Implementation |
|----------|-------------|----------------|
| **HS300 Buy-and-Hold** | Put 100% into 000300.SH equivalent on day 1, never trade | Single "buy on day 1" rule strategy |
| **Random Agent** | Each rebalance: 50% chance no-op, 25% random buy, 25% random sell within pool | Rule strategy with `random.Random(seed=agent_id_hash)` |
| **Fixed-Rule Agent** | Every rebalance: buy any stock where PE < 15 (until cash depleted); sell any stock where PE > 30 | Deterministic rule strategy using financial_cache |

Baselines run in the **same date range** with the **same commission** as the main backtest. Result page overlays **4 curves** (main + 3 baselines) on the equity chart. If the LLM agent loses to all three, the user knows there's no alpha.

### 6.5 A-Share Specifics

**Commission (Decimal):**
| Fee | Rate | Side |
|-----|------|------|
| Broker commission | 0.025% | Buy + Sell |
| Stamp tax | 0.1% | Sell only |
| Transfer fee | 0.001% | Buy + Sell |
| Min commission | ¥5 | If calculated < ¥5 |

`runner/commission.py` overrides vnpy's simple `rate * turnover`. All monetary math uses `decimal.Decimal`.

**T+1:**
- Enforced in a new `runner/t_plus_1.py` that plugs into both `LLMStrategy` and rule strategies via a shared mixin
- Tracks `buy_date` per position
- Sells requested on buy_date are blocked → logged to `blocked_trades` → returned as "T+1 violated"

**Board lots:**
- Buy: must be in multiples of 100 (1 手). Non-compliant buy → rejected by engine before vnpy sees it.
- Sell: can sell any integer qty if holding (odd-lot partial sells allowed).

### 6.6 Backtest Runner Flow

```python
class BacktestRunner:
    def run_agent(self, agent_id, start, end, sse_callback):
        agent = db.get_agent(agent_id)
        model = db.get_model(agent.model_id)

        # D1: enforce cross-cutoff requirement
        if not (start < model.training_cutoff < end):
            raise ValueError(
                f"Backtest must span model cutoff ({model.training_cutoff}). "
                f"Adjust dates or switch models."
            )

        # Run main agent backtest
        engine = BacktestingEngine()
        engine.set_parameters(...)
        engine.add_strategy(LLMStrategy, {'agent_id': agent_id, 'sse_cb': sse_callback})
        engine.run_backtesting()
        main_result = engine.calculate_result()

        # Run 3 baselines (fast, no LLM)
        baselines = {
            'hs300':      self._run_baseline_hs300(start, end, agent.initial_capital),
            'random':     self._run_baseline_random(start, end, agent),
            'fixed_rule': self._run_baseline_fixed(start, end, agent),
        }

        # Split metrics by knowledge boundary (§ 11)
        pollution, clean = split_by_cutoff(main_result.nav_history, model.training_cutoff)

        return BacktestResult(
            main=main_result,
            baselines=baselines,
            pollution_metrics=metrics(pollution),
            clean_metrics=metrics(clean),
            prompt_version=agent.current_prompt_version,
            model_cutoff=model.training_cutoff,
        )
```

### 6.7 Result Schema (Persisted)

```sql
CREATE TABLE backtest_results (
    id              TEXT PRIMARY KEY,            -- 'bt_20260422_linyuan_opus47'
    agent_id        TEXT REFERENCES agents(id),
    model_id        TEXT REFERENCES llm_models(id),
    persona_id      TEXT REFERENCES personas(id),
    prompt_version  INTEGER,
    mode            TEXT NOT NULL,               -- 'agent' | 'rule'
    rule_strategy_id TEXT,                       -- if mode='rule'
    start_date      DATE, end_date DATE,
    initial_capital DECIMAL(15,2),
    final_nav       DECIMAL(15,2),

    -- Full metrics on the whole period
    metrics         JSON,

    -- NEW: split metrics (agent mode only)
    pollution_metrics JSON,        -- metrics on [start, cutoff]
    clean_metrics     JSON,        -- metrics on (cutoff, end]
    divergence_flag   BOOLEAN,     -- true if Sharpe difference > 1.0 (suspicious)

    -- NEW: baseline comparisons
    baseline_hs300_metrics      JSON,
    baseline_random_metrics     JSON,
    baseline_fixed_rule_metrics JSON,

    -- Existing
    nav_history     JSON,
    trades          JSON,
    thinking_log    JSON,
    blocked_trades  JSON,
    token_usage     JSON,
    strategy_rating JSON,          -- See § 9

    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 7. Validation — Two-Layer Rules

### 7.1 Layer 1: Global RedLine (Immutable Hard Ceiling)

Persisted globally (one row per install), changes only via explicit user action in RedLine config modal. Every order from every agent goes through this layer first.

```python
DEFAULT_REDLINES = {
    # hard limits (must pass)
    'daily_loss_max_pct':    3.0,       # 日亏损上限
    'position_max_pct':      15.0,      # 单笔最大仓位
    'stock_concentration':   30.0,      # 单股集中度
    'cash_min_pct':          5.0,       # 最低现金
    'order_max_value':       200000,    # 单笔金额 ¥
    'turnover_max_daily':    300.0,     # 日内最大换手 %
    'same_stock_cooldown_min': 5,       # 同票冷却分钟

    # behavioral toggles (hard)
    'ban_limit_up':          True,      # 禁止追涨停
    'ban_st':                True,      # 禁止 ST
    'ban_limit_down':        True,      # 禁止抄跌停
    'ban_ipo_30d':           True,      # 禁止次新股
    'require_reason':        True,      # 决策必须含理由 (≥20 字)
    'prompt_injection_check': True,     # 可疑 prompt 注入检测 (stub in MVP)
    'auto_halt_var_2sigma':  True,      # VaR 超 2σ 自动熔断
}
```

Stored in `agent_state.db.redlines` (single-row table). Changes logged to audit.

### 7.2 Layer 2: Per-Agent Rules (Stricter-Only Overrides)

Agent's `rules_override` column can only **narrow** RedLine, not widen. UI enforces this at write time:

```python
def apply_override(redline: dict, override: dict) -> dict:
    result = dict(redline)
    for k, v in override.items():
        if k.endswith('_pct') or k.endswith('_value') or k in ('daily_loss_max_pct', 'order_max_value'):
            # These are upper-bounds — override must be ≤ redline
            result[k] = min(redline[k], v)
        elif k in ('cash_min_pct',):
            # Lower-bound — override must be ≥ redline
            result[k] = max(redline[k], v)
        elif k.startswith('ban_'):
            # Toggle — can only turn on, not off
            result[k] = redline[k] or v
    return result
```

Example: Agent 林园 wants 单股 ≤ 30% but RedLine says 30% → OK. Agent wants 40% → clamped to 30%, UI shows "被全局红线限定为 30%" pill.

### 7.3 Validation Flow

```python
def validate(decision: Decision, portfolio: Portfolio, ctx: dict) -> ValidationResult:
    effective_rules = apply_override(redline, agent.rules_override)
    blocked_by = []

    for rule_name, rule_value in effective_rules.items():
        if rule_value is False: continue
        check = RULE_CHECKS[rule_name]
        ok, reason = check(decision, portfolio, ctx, rule_value)
        if not ok:
            blocked_by.append({'rule': rule_name, 'reason': reason, 'layer': _which_layer(rule_name, redline, agent.rules_override)})

    return ValidationResult(valid=not blocked_by, blocked_by=blocked_by)
```

Every block records whether it came from RedLine or the agent's own override — useful for debugging.

### 7.4 Post-Backtest Quality Gate

Before deploying to live:

```python
DEFAULT_QUALITY_GATE = {
    'min_sharpe':        0.3,
    'max_drawdown_pct': -25.0,
    'min_trade_count':   5,
    'min_win_rate':      30.0,
    'max_daily_loss_pct':-5.0,
    'min_clean_zone_days': 60,    # NEW: at least 60 days post-cutoff required to trust results
    'max_divergence_flag': False, # NEW: clean/pollution divergence must not be flagged
}
```

Quality gate pass is shown on result page per-criterion. Agent cannot be deployed until it passes.

### 7.5 Audit Log

```sql
CREATE TABLE audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    DATETIME DEFAULT CURRENT_TIMESTAMP,
    kind         TEXT NOT NULL,    -- 'trade_executed' | 'trade_blocked' | 'llm_called'
                                   -- | 'validation' | 'error' | 'redline_changed' | 'agent_deployed'
    agent_id     TEXT,
    persona_id   TEXT,
    model_id     TEXT,
    prompt_version INTEGER,
    details      JSON
);

CREATE INDEX audit_by_agent ON audit_log(agent_id, timestamp DESC);
CREATE INDEX audit_by_kind  ON audit_log(kind, timestamp DESC);
```

WAL mode. Never truncated in MVP.

---

## 8. Agent Health & Trust Rating

### 8.1 Health Score Formula

Defined per D7:

```
health_score = max(0, 100 - violations_7d × 3
                         - backtest_deviation_pts × 2
                         - parse_failures_7d × 1)

where:
  violations_7d          = count of validation failures in last 7 trading days
  backtest_deviation_pts = abs(live_7d_return_pct - backtest_7d_return_pct)
                           (live performance vs comparable period in backtest)
                           0 if agent is backtest-only (not deployed)
  parse_failures_7d      = count of tool_use loops that hit max iterations
                           or returned malformed JSON in last 7 days
```

Recomputed:
- After every trade (increment or recompute)
- Nightly full recalc at 20:00 local

### 8.2 Trust Rating

| Rating | Range | Consequence |
|--------|-------|-------------|
| A+ | health ≥ 90 | Full auto trading allowed |
| A | 80–89 | Full auto allowed |
| B | 60–79 | Each trade requires user confirmation (forced to semi-auto) |
| C | 0–59 | Observe-only mode; place_decision calls are rejected at the server |

Stored as `agents.trust_rating`. RiskMonitor page shows this column.

### 8.3 Degradation Triggers

In addition to the formula above, these conditions **immediately** drop rating regardless of score:

- 3 consecutive validation blocks → B (review needed)
- Live performance deviates >5% from backtest over any 3 day window → C
- Any "prompt_injection_check" hit in last 24h → C (flagged for manual review)
- Agent subprocess crashed ≥3 times in 24h → C

Operator can manually reset a C agent to B after investigation via RiskMonitor → "调整权限" button.

---

## 9. Strategy Rating (Post-Backtest)

### 9.1 Overall Rating

| Letter | Threshold (weighted sub-scores) |
|--------|-------------------------------|
| A+ | ≥ 90 |
| A | 80–89 |
| B | 70–79 |
| C | 60–69 |
| D | < 60 |

### 9.2 Five Sub-Scores (formulas)

Each sub-score is 0–100. The overall score is a weighted average: `0.3·收益 + 0.3·风险 + 0.15·稳定 + 0.15·效率 + 0.10·过拟合`.

**① 收益能力 (Return Power)**
```
base = clamp((clean_zone_sharpe - 0) / 2.5 * 100, 0, 100)
# 0 ≈ no alpha; 2.5 ≈ exceptional
# Uses clean_zone_sharpe, not full-period, to discount knowledge leakage
```

**② 风险控制 (Risk Control)**
```
mdd_score   = 100 * max(0, 1 - abs(max_drawdown) / 30)    # 30% drawdown → 0; 0% → 100
daily_score = 100 * max(0, 1 - abs(worst_daily_loss) / 10)
base = 0.6 * mdd_score + 0.4 * daily_score
```

**③ 稳定性 (Stability)**
```
monthly_returns = 12-month array from backtest
volatility = std(monthly_returns)
base = clamp(100 - volatility * 10, 0, 100)  # low vol → high score
```

**④ 交易效率 (Trading Efficiency)**
```
if trade_count < 5: base = 0  # not enough data
else:
    avg_profit_per_trade = total_return / trade_count
    cost_ratio = total_commission / total_return
    base = clamp(50 + avg_profit_per_trade * 5 - cost_ratio * 100, 0, 100)
```

**⑤ 过拟合风险 (Overfitting Risk)** — HIGHER is BETTER
```
# Compares clean zone to pollution zone. Inverts divergence.
cutoff_divergence = abs(pollution_sharpe - clean_sharpe)
base = 100 * max(0, 1 - cutoff_divergence / 2.0)
# Sharpe differs by 2.0 → 0 (heavy leakage); identical → 100 (clean)
```

These formulas live in `rating/strategy_rating.py` and are deterministic given a backtest result.

---

## 10. Prompt Versioning

### 10.1 Schema

```sql
CREATE TABLE agent_prompt_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    version_number  INTEGER NOT NULL,      -- monotonic per agent
    system_prompt   TEXT NOT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    note            TEXT,                  -- optional edit comment
    UNIQUE(agent_id, version_number)
);
CREATE INDEX prompt_by_agent ON agent_prompt_versions(agent_id, version_number DESC);
```

### 10.2 Auto-Versioning

On any update to `agents.system_prompt` OR `personas.system_prompt` (where persona propagates to instances):
1. Write new row into `agent_prompt_versions` with `version_number = max(existing) + 1`
2. Update `agents.current_prompt_version` to new number
3. Old versions remain forever
4. Each subsequent backtest result stores the `prompt_version` it used

### 10.3 Rollback

UI button "回滚到 vN" in the Prompt panel:
```
POST /api/agents/{id}/prompt/rollback
body: {"target_version": 5}
```
Creates a new version N+1 whose content is identical to version 5 (never mutate existing versions). Updates `current_prompt_version`.

### 10.4 Re-Backtest Comparison

User can re-run backtest against an older version; result page shows "Prompt v5 vs v7" side-by-side metrics. No diff rendering in MVP.

---

## 11. Knowledge Leakage Mitigation — Cross-Cutoff

### 11.1 The Core Problem

LLMs trained up to some date `T` already know which stocks rose/fell during any pre-`T` period. Prompting them with "你不知道 T 之后的事" does not reliably suppress this knowledge — the model will leak via plausible-sounding reasoning.

### 11.2 Cross-Cutoff Requirement (D1)

Every agent backtest MUST span its model's `training_cutoff` date:

```
start_date  <  training_cutoff  <  end_date
```

Enforced in `BacktestRunner.run_agent()` and in the backtest config form UI.

### 11.3 Bifurcated Metrics Display

Backtest result page shows **two sets of metrics side-by-side**:

| Metric | 污染区间 (≤ cutoff) | 干净区间 (> cutoff) |
|--------|-------------------|--------------------|
| 总收益 | +32.4% | +3.1% |
| 夏普 | 2.41 | 0.42 |
| 最大回撤 | -3.1% | -8.9% |
| 交易笔数 | 82 | 22 |

With a prominent banner:

> ⚠️ **干净区间 (模型 cutoff 之后) 才反映真实 alpha**。污染区间的指标可能被模型先验知识污染。
> 如果两区间指标差异大 → 模型在泄漏历史记忆，策略在真实场景表现可能大幅不如污染区指标。

### 11.4 Divergence Detection

Automatic flag on result:
```python
divergence_flag = abs(pollution_sharpe - clean_sharpe) > 1.0
                  OR abs(pollution_return - clean_return) > 0.2
```

If flagged, quality gate fails (§ 7.4). Deploy blocked until user confirms via override.

### 11.5 In-Prompt Disclaimer (secondary defense)

We still include the v1 knowledge-boundary declaration in every call — it doesn't eliminate leakage but it slightly reduces explicit memory citation:

```
[知识边界声明]
今日是 {date}。你只能基于截至此日期的公开信息决策。
不使用 {date} 之后的任何事件、公告、新闻或股价走势。
```

### 11.6 UI Disclaimer

Every backtest result page displays:

> ⚠️ 本回测使用大语言模型做决策。LLM 训练数据可能包含回测期间之后的真实市场信息，导致回测结果偏离实盘。
> 我们已将结果按模型截止日期切分为"污染区"和"干净区"。请以干净区指标为准。

---

## 12. Intraday (Phase 2)

Unchanged from v1. Phase 1 uses only daily (`1d`) K-line. Intraday `1m`/`5m` requires investigating and fixing TDX data access first.

---

## 13. Agent Lifecycle

### 13.1 States

```
created → backtesting → backtested → deployed → (stopped | crashed → deployed)
```

`stopped` is user-initiated; `crashed` is detected by health monitor; `deployed` can recur after either.

### 13.2 Subprocess Architecture (unchanged from v1)

- One `multiprocessing.Process` per deployed agent
- Flask's `MessageRouter` holds a `multiprocessing.Queue` for messages from agents, + per-agent response queues
- Agent subprocess runs scheduled (re)balance, calls LLM, validates, requests confirmation via MQ, executes via `tdx_service`
- Health monitor thread in Flask restarts crashed agents (exit detection via `proc.is_alive()`)

### 13.3 Crash Recovery (unchanged from v1)

Three layers: SQLite state persistence → Flask startup replays deployed agents → Per-agent auto-restart on crash. See v1 § 12.4–12.8 — formulas and schema are unchanged.

Detail addition: `pending_trade` column in `agent_state` table persists any unconfirmed proposal so it can be re-surfaced after Flask restart.

---

## 14. Project Structure

```
biyingtong/
├── app.py                      # Flask entry — REST + SSE + WebSocket
├── config.py                   # Env/API key loading, feature flags
├── requirements.txt
├── .env                        # (gitignored)
│
├── llm/                        # ── Vendor-neutral LLM layer ──
│   ├── __init__.py
│   ├── base.py                 # LLMBase, Message, ToolSpec, LLMResponse
│   ├── claude.py               # Anthropic adapter
│   ├── openai_adapter.py       # OpenAI + DeepSeek (base_url override)
│   ├── gemini.py               # Gemini adapter
│   ├── mock.py                 # For tests
│   ├── models.py               # Seed data for llm_models table
│   └── tracker.py              # LLMCallTracker
│
├── tools/                      # ── Tools the LLM can call ──
│   ├── __init__.py             # ToolSpec registry + name→callable map
│   ├── get_kline.py
│   ├── get_snapshot.py
│   ├── get_financials.py
│   ├── get_technical.py
│   ├── get_index.py
│   ├── get_portfolio.py
│   ├── get_news.py             # Stub (Phase 2)
│   └── place_decision.py       # Terminator
│
├── personas/                   # ── Built-in persona definitions ──
│   ├── __init__.py             # Registry; seeds personas table on boot
│   ├── linyuan.py
│   ├── fuyou.py
│   ├── buffet.py
│   ├── soros.py
│   └── quant_neutral.py
│
├── strategy/                   # ── vnpy strategies (both modes) ──
│   ├── __init__.py
│   ├── llm_strategy.py         # LLMStrategy (inherits StrategyTemplate)
│   ├── ma_v3.py                # Rule: 均线突破
│   ├── grid.py                 # Rule: 网格
│   ├── factor.py               # Rule: 多因子
│   └── baselines.py            # HS300 buy-hold, Random, FixedRule
│
├── runner/                     # ── Execution ──
│   ├── __init__.py
│   ├── backtest_runner.py      # run_agent, run_rule, SSE streaming
│   ├── agent_process.py        # Subprocess entry for live agents
│   ├── message_router.py       # Flask-side MQ hub
│   ├── commission.py           # A-share commission (Decimal)
│   ├── t_plus_1.py             # T+1 mixin
│   └── board_lot.py            # 100-share enforcement
│
├── validation/                 # ── Two-layer rules ──
│   ├── __init__.py
│   ├── redline.py              # Global engine + persistence
│   ├── rules.py                # All RULE_CHECKS implementations
│   └── quality_gate.py         # Post-backtest gate
│
├── rating/                     # ── Health + strategy rating ──
│   ├── __init__.py
│   ├── agent_health.py         # Health score formula (§ 8)
│   └── strategy_rating.py      # 5 sub-scores + overall (§ 9)
│
├── tdx_service.py              # Existing — live trading via tqcenter
│
├── data/                       # (gitignored)
│   ├── vnpy_data.db            # vnpy K-line database
│   ├── financial_cache.db
│   └── agent_state.db          # WAL mode: agents, personas, versions, audit, backtest_results, redlines
│
├── client/                     # ── Vite + React frontend ──
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api.js
│       ├── components/
│       ├── pages/
│       │   ├── Dashboard.jsx
│       │   ├── AgentLab.jsx        # (tweaked from prototype)
│       │   ├── Backtest.jsx        # (dual-tab: Agent / Rule)
│       │   ├── LiveTrading.jsx
│       │   ├── Screener.jsx
│       │   ├── Editor.jsx
│       │   └── RiskMonitor.jsx
│       ├── styles/tokens.css       # unchanged
│       └── hooks/
│
└── static/                     # Vite build output — Flask serves directly
```

---

## 15. API Endpoints

### 15.1 Existing (unchanged)

`GET /api/status`, `/api/market/*`, `/api/stocks/*`, `/api/account/*`, `/api/trade/*`, WebSocket quotes.

### 15.2 Personas + Agents

- `GET    /api/personas` — list personas (built-in + user)
- `POST   /api/personas` — create user persona
- `PUT    /api/personas/{id}` — update persona (creates new prompt version)
- `DELETE /api/personas/{id}` — delete (blocked if any active agent references it)

- `GET    /api/agents` — list agent instances with health + trust
- `POST   /api/agents` — create agent instance `{persona_id, model_id, rules_override, initial_capital}`
- `PUT    /api/agents/{id}` — update (rules_override, display_name)
- `DELETE /api/agents/{id}` — delete (stops subprocess if deployed)
- `POST   /api/agents/{id}/deploy` — switch to deployed state
- `POST   /api/agents/{id}/stop` — stop deployed agent
- `POST   /api/agents/{id}/approve` — approve pending trade
- `POST   /api/agents/{id}/reject` — reject pending trade

### 15.3 Prompt Versions

- `GET  /api/agents/{id}/prompts` — list versions
- `POST /api/agents/{id}/prompts/rollback` — `{target_version}`

### 15.4 Backtest

- `POST /api/backtest/agent` — `{agent_id, start_date, end_date}` (cutoff validation here)
- `POST /api/backtest/rule` — `{strategy_id, params, start_date, end_date, stock_pool}`
- `GET  /api/backtest/{task_id}/stream` — SSE events (see 15.6)
- `GET  /api/backtest/{task_id}/result` — full result with pollution/clean split + baselines
- `GET  /api/backtest/{task_id}/trades`
- `GET  /api/backtest/{task_id}/thinking`
- `GET  /api/backtest/{task_id}/nav`
- `POST /api/backtest/{task_id}/cancel`
- `GET  /api/backtest/results` — list all for comparison chart

### 15.5 Models + RedLine

- `GET  /api/models` — list enabled models with cutoff + pricing
- `GET  /api/redline` — current values
- `PUT  /api/redline` — update (audit logged)

### 15.6 SSE Event Types (Backtest Stream)

```
event: phase         data: {"phase":"data_loading" | "running" | "done", "progress":0..1}
event: progress      data: {"day":87, "total":244, "status":"thinking"|"executing", "snippet":"..."}
event: tool_call     data: {"day":87, "tool":"get_kline", "code":"600519.SH"}
event: decision      data: {"day":87, "action":"buy", "code":"...", "qty":100, "reason":"...", "nav":1368000}
event: blocked       data: {"day":87, "rule":"stock_concentration", "layer":"redline", "reason":"..."}
event: baseline_done data: {"baseline":"hs300", "final_nav":1087000}
event: done          data: {"pollution_metrics":{...}, "clean_metrics":{...}, "divergence_flag":false, ...}
```

---

## 16. Frontend Migration (Vite + React) — mapping

Stack: Vite + React 18 + React Router + @tanstack/react-query. Dev: Vite @ 5173 with proxy to Flask @ 5000. Prod: `vite build` → Flask serves `static/`.

Prototype → Real-data mapping (updated from v1 § 9):

| Prototype Element | Data Source | Notes |
|------------------|------------|-------|
| Agent cards (ret/sharpe/mdd/win/trades/cost) | `/api/backtest/results` latest per agent | "为你赚" field = metrics.total_return × initial_capital |
| AutonomousScheduler 24h timeline | Mock data with Phase 2 disclaimer | Only the master-switch + phase label are real |
| Thinking log | SSE stream `decision` events + persisted `thinking_log` | Each entry includes tool_call traces |
| Positions panel | vnpy state (backtest) / `tdx_service` (live) | — |
| Compare chart (5 curves) | `/api/backtest/{id}/nav` per agent | — |
| **Cost stats (Token/¥/决策数/ROI)** | `LLMCallTracker` result + cache ratio | NEW: show "cache saved ¥X" |
| **Prompt panel "v7"** | `/api/agents/{id}/prompts` | Versions real; no diff UI |
| **Tools list** | `/api/agents/{id}` → `allowed_tools` | Real whitelist checkboxes |
| Create Agent modal → persona chips | `/api/personas` | — |
| Create Agent modal → model select | `/api/models` | Real model list |
| Create Agent modal → tool checkboxes | Same `allowed_tools` | — |
| Backtest equity chart (4 curves now) | `/api/backtest/{id}/nav` + 3 baselines | NEW: 4 lines overlay |
| **Pollution / Clean split** | `pollution_metrics` + `clean_metrics` | NEW: toggle or side-by-side view |
| Monthly heatmap | `monthly_returns` in metrics | — |
| Trade log | `/api/backtest/{id}/trades` | — |
| **Strategy rating A+/A/B/C** | `strategy_rating` in result with 5 sub-scores | NEW: show sub-scores per § 9 |
| **Quality gate panel** | `quality_gate_result` | NEW: pass/fail per criterion |
| RedLineBar (top) | `/api/redline` + realtime usage from running agents | — |
| RedLineConfigModal | PUT `/api/redline` | — |
| RiskMonitor → Agent 健康度 | `agents.health_score` + `trust_rating` | Real formula per § 8 |
| RiskMonitor → 三层防护 | Flattened view of RedLine + per-agent rules | — |
| RiskMonitor → 审计日志 | `audit_log` table | — |
| RiskMonitor → 待审批 | Pending trades from message queue | — |
| LiveTrading → AI 风控提示 | Phase 2 stub | Not in MVP |
| Dashboard → AI 今日贡献 | Phase 2 stub | Not in MVP |
| Marketplace | Phase 2+ | Not in MVP |

Migration order deferred — see § 18.

---

## 17. TDX Data Verification Summary (unchanged)

| Data Type | API | Status |
|-----------|-----|--------|
| Daily K-line (`1d`) | `get_market_data(period='1d')` | ✓ Ready |
| Weekly/Monthly | `get_market_data(period='1w'/'1mon')` | To verify in Phase 0 |
| Intraday (`1m`/`5m`) | `get_market_data(period='1m'/'5m')` | ✗ Phase 2 |
| Stock info (PE/PB/ROE) | `get_stock_info` | ✓ Ready |
| Real-time snapshot | `get_market_snapshot` | ✓ Ready |
| Index | `get_market_snapshot('000001.SH')` | ✓ Ready |
| Trading calendar | `get_trading_calendar` | To verify; fallback in § 3.3 |

---

## 18. Implementation Order

Revised. Organized into 5 milestones.

### Milestone 0 — Infrastructure spikes (1-2 days, low risk)
1. Verify TDX daily K-line → `vnpy_sqlite` roundtrip on 50 stocks × 1 year (proven in v1 but re-verify)
2. Verify `get_trading_calendar()`; if missing, implement K-line-dates fallback
3. Verify `financial_cache.db` build from local TDX cache (PE/PB/ROE for HS300)

### Milestone 1 — LLM layer + tools (3-5 days)
4. `llm/base.py` — canonical types + `LLMBase`
5. `llm/claude.py` + `llm/openai_adapter.py` — two adapters first, cover Anthropic and OpenAI-compatible (= DeepSeek)
6. `llm/models.py` + seed `llm_models` table
7. `tools/` — all 8 tools; backed by cache-read functions
8. End-to-end mock backtest with `MockLLM` that always calls `get_kline` then `place_decision("hold")` — verifies whole loop without cost
9. `llm/gemini.py` adapter (can defer if Anthropic+OpenAI cover personas 1-4)
10. `LLMCallTracker` with cached tokens separation

### Milestone 2 — Agent backtest MVP (5-7 days)
11. `personas/` — 5 built-ins seeded into DB
12. `strategy/llm_strategy.py` — vnpy `StrategyTemplate` with tool_use loop
13. `runner/backtest_runner.py` — Agent mode with SSE
14. `runner/commission.py`, `t_plus_1.py`, `board_lot.py`
15. `validation/redline.py` + `validation/rules.py` — two-layer enforcement
16. `rating/strategy_rating.py` + `agent_health.py`
17. Cross-cutoff bifurcated metrics in result
18. Flask API routes for agents + backtest + SSE + personas
19. End-to-end: real backtest of 林园 × Claude Sonnet for 1 year

### Milestone 3 — Rule mode + baselines (3 days)
20. `strategy/ma_v3.py`, `grid.py`, `factor.py` — rule strategies
21. `strategy/baselines.py` — HS300 buy-hold, Random, FixedRule
22. `runner.run_rule()` endpoint
23. Baselines auto-run on every agent backtest
24. Backtest result page 4-curve overlay

### Milestone 4 — Frontend integration (4-6 days)
25. Vite scaffolding under `client/`
26. Migrate pages one-at-a-time: Dashboard → AgentLab → Backtest → RiskMonitor → LiveTrading
27. Wire AgentLab cards + thinking log to SSE
28. Wire Backtest dual-tab (Agent / Rule) with pollution/clean split
29. Wire RiskMonitor to real audit + health data
30. Wire RedLineBar + RedLineConfigModal to `/api/redline`
31. Keep AutonomousScheduler panel with mock + Phase-2 labels

### Milestone 5 — Live deployment (4-6 days)
32. `runner/agent_process.py` subprocess entry
33. `runner/message_router.py` Flask MQ hub + health monitor
34. Trade proposal → WebSocket → user confirm → `tdx_service.place_order`
35. Crash recovery on Flask restart
36. Audit log UI in RiskMonitor

### Phase 2+ (no commitment date)
- Intraday 1m/5m
- News sources + prompt injection detection
- Event triggers for scheduler
- Multi-agent collaboration
- Marketplace
- LiveTrading AI 风控提示
- Prompt diff UI

Total Phase 1 estimate: **4–6 weeks** for a single full-time developer.

---

## 19. Open Items (Phase 2+ refs)

- **News data source** — cheapest path is likely 东财 (东方财富) RSS crawler; Wind/雪球too expensive for MVP
- **AutonomousScheduler event triggers** — the six trigger types in prototype are all individually substantial (price events = realtime quote pipeline; news = §1 above; technical signals = real-time indicator engine; anomaly = VaR monitor; collab = agent message bus)
- **Multi-agent collaboration** — one route: agents publish signals to a shared Redis channel, others consume. Semantics TBD.
- **Marketplace** — hosted "model-as-a-service" is a business decision, not just tech
- **LiveTrading AI 风控提示** — requires a lightweight LLM call on every manual order (can use Haiku for cost)
- **Prompt diff UI** — character-level diff with syntax highlighting; straightforward to add when demanded

---

## Appendix A — Glossary

| Term | Meaning |
|------|---------|
| Persona | Reusable definition of an investment philosophy (system_prompt + default pool + schedule) |
| Agent | A runnable instance = `persona × model × rules_override` |
| RedLine | Global immutable hard-limit rules (§ 7.1) |
| Clean zone | Backtest period strictly after the model's training cutoff |
| Pollution zone | Backtest period at or before the model's training cutoff |
| Cutoff | `training_cutoff` date of an LLM model |
| Quality gate | Post-backtest thresholds that must pass before live deploy |
| Health score | Per-agent 0–100 operational health metric (§ 8) |
| Trust rating | Derived from health: A+/A/B/C; controls auto-trade permission |
| Tool_use | Strict JSON function-calling mechanism (Anthropic/OpenAI/Gemini) |
