# P3-A 回测可观察性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户在 BacktestLab 跑完回测后，能完整复盘「那天发生了什么 / 为什么决策 / 曲线怎么走」。今天只有汇总 stats — 交付后可看每日权益、每笔成交、每次 LLM thinking、5 子分 strategy rating、quality gate。

**Architecture:**
- 后端 3 张 JSON 列 + 3 个 GET 端点。BacktestRunner 已经在内存里攒 `daily_records` 和 `book._tranches.fills`，本项只是把它们序列化 + 新增 per-day thinking 采集。
- 前端 `recharts` 4-curve NAV 图 + Trades 表 + Thinking 抽屉 + QualityGate 面板 + StrategyRating 面板。所有新组件都是 BacktestLab 的子视图，通过已有 session 数据拉新端点。
- 不动 SSE（P3-D 再做）。Thinking 是跑完读，不是流式看。

**Tech Stack:** Python 3.10 / Flask / SQLite (JSON columns) / React 19 / TypeScript / TanStack Query / lightweight-charts 4.x (TradingView)

---

## File Structure

**Backend:**
- `data_schema/backtest_state.py` — 新增 3 列到 `backtest_results`
- `backtest/base.py` — `BacktestResult` 加 3 字段 (`daily_records` / `trades` / `thinking`)
- `backtest/runner.py` — 采集 trades + thinking，填入 result
- `backtest/book.py` — 新增 `fills` 列表记录所有成交
- `agents/runner.py` — `run_day` 返回 `RunDayResult` 含 thinking，或暴露 per-call hook
- `storage/sqlite_backtests.py` — insert + select 覆盖 3 列；`_row_to_result` 回填
- `storage/base.py` — (无变更 — Protocol 不约束这些字段)
- `api/backtests.py` — 3 个新 route：`/:id/nav` `/:id/trades` `/:id/thinking`
- `tests/test_backtest_observability.py` — 新测试文件

**Frontend:**
- `frontend/package.json` — 加 `lightweight-charts ^4.2`
- `frontend/src/api/types.ts` — 加 `NavPoint` / `TradeRow` / `ThinkingEntry` 类型
- `frontend/src/api/hooks.ts` — 加 `useBacktestNav` / `useBacktestTrades` / `useBacktestThinking` / `useBacktestRating`
- `frontend/src/components/NavChart.tsx` — 新组件
- `frontend/src/components/TradesTable.tsx` — 新组件
- `frontend/src/components/ThinkingDrawer.tsx` — 新组件
- `frontend/src/components/QualityGatePanel.tsx` — 新组件
- `frontend/src/components/StrategyRatingPanel.tsx` — 新组件
- `frontend/src/pages/BacktestLab.tsx` — 挂载新组件

---

### Task 1: Schema + dataclass 扩展 3 个 JSON 字段

**Files:**
- Modify: `data_schema/backtest_state.py`
- Modify: `backtest/base.py`
- Test: `tests/test_backtest_observability.py` (new)

**Design notes:**
- `daily_records` 原本是 runner 的中间态，现在要持久化。每项形如 `{date: 'YYYY-MM-DD', equity, cash, pnl_pct, trade_count, won}`。
- `trades` 扁平 list：`{date, code, action: 'buy'|'sell', shares, price, fee}`。直接从 Book.fills 采。
- `thinking` 每天一条：`{date: 'YYYY-MM-DD', reasoning, tool_calls: [{name, input}], decisions: [{action, code, shares, price}]}`。reasoning 来自 LLM 最后一次 text turn；tool_calls 只记非 place_decision 的查询调用。

**DDL 扩展 — backward compatible，新列 nullable + 默认空 JSON：**

- [ ] **Step 1: 写 DDL 迁移的失败测试**

Create `tests/test_backtest_observability.py`:

```python
"""P3-A: observability endpoints — NAV, trades, thinking."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest


def test_backtest_results_schema_has_observability_columns(tmp_path):
    """新 schema 必须有 daily_records_json / trades_json / thinking_json。"""
    from data_schema.backtest_state import SCHEMA_BACKTEST_RESULTS
    con = sqlite3.connect(':memory:')
    con.executescript(SCHEMA_BACKTEST_RESULTS)
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    con.close()
    assert 'daily_records_json' in cols
    assert 'trades_json' in cols
    assert 'thinking_json' in cols
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_backtest_observability.py::test_backtest_results_schema_has_observability_columns -v`
Expected: FAIL — 3 列不存在。

- [ ] **Step 3: 修改 DDL**

Edit `data_schema/backtest_state.py`:

```python
SCHEMA_BACKTEST_RESULTS = '''
CREATE TABLE IF NOT EXISTS backtest_results (
    id                   TEXT PRIMARY KEY,
    session_id           TEXT NOT NULL,
    agent_id             TEXT NOT NULL,
    persona_id           TEXT,
    model_id             TEXT,
    start_date           TEXT NOT NULL,
    end_date             TEXT NOT NULL,
    initial_capital      REAL NOT NULL,
    final_equity         REAL,
    stats_json           TEXT NOT NULL,
    zone_stats_json      TEXT NOT NULL,
    quality_gate_label   TEXT NOT NULL,
    quality_gate_json    TEXT NOT NULL,
    daily_records_json   TEXT NOT NULL DEFAULT '[]',
    trades_json          TEXT NOT NULL DEFAULT '[]',
    thinking_json        TEXT NOT NULL DEFAULT '[]',
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS results_by_session ON backtest_results(session_id);
CREATE INDEX IF NOT EXISTS results_by_agent   ON backtest_results(agent_id, created_at DESC);
'''
```

- [ ] **Step 4: 迁移旧 DB — 写 migration helper**

Edit `data_schema/backtest_state.py`, append:

```python
SCHEMA_BACKTEST_RESULTS_MIGRATE = '''
-- Idempotent add-column. SQLite ignores duplicates when column exists,
-- but ALTER TABLE ADD COLUMN raises — so we branch via PRAGMA check.
'''

def ensure_observability_columns(con):
    """Add the 3 P3-A columns to an existing backtest_results table.
    Idempotent: safe to call on a fresh schema."""
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    if 'daily_records_json' not in cols:
        con.execute("ALTER TABLE backtest_results ADD COLUMN "
                    "daily_records_json TEXT NOT NULL DEFAULT '[]'")
    if 'trades_json' not in cols:
        con.execute("ALTER TABLE backtest_results ADD COLUMN "
                    "trades_json TEXT NOT NULL DEFAULT '[]'")
    if 'thinking_json' not in cols:
        con.execute("ALTER TABLE backtest_results ADD COLUMN "
                    "thinking_json TEXT NOT NULL DEFAULT '[]'")
```

- [ ] **Step 5: 写迁移测试**

Append to `tests/test_backtest_observability.py`:

```python
def test_ensure_observability_columns_migrates_old_schema(tmp_path):
    """旧 schema（只有 13 列）升级后必须有 16 列且旧数据保留。"""
    import sqlite3
    from data_schema.backtest_state import ensure_observability_columns

    db = tmp_path / 'test.db'
    con = sqlite3.connect(db)
    # 模拟旧表
    con.execute('''CREATE TABLE backtest_results (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL, agent_id TEXT NOT NULL,
        persona_id TEXT, model_id TEXT,
        start_date TEXT NOT NULL, end_date TEXT NOT NULL,
        initial_capital REAL NOT NULL, final_equity REAL,
        stats_json TEXT NOT NULL, zone_stats_json TEXT NOT NULL,
        quality_gate_label TEXT NOT NULL, quality_gate_json TEXT NOT NULL
    )''')
    con.execute(
        "INSERT INTO backtest_results VALUES "
        "('r1','s1','a1',null,null,'2025-01-01','2025-01-10',"
        "100000.0,null,'{}','[]','pass','{}')",
    )
    con.commit()

    ensure_observability_columns(con)
    ensure_observability_columns(con)  # idempotent

    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    assert 'daily_records_json' in cols
    assert 'trades_json' in cols
    assert 'thinking_json' in cols

    # 旧数据默认值检查
    row = con.execute(
        'SELECT daily_records_json, trades_json, thinking_json '
        'FROM backtest_results WHERE id=?', ('r1',),
    ).fetchone()
    assert row == ('[]', '[]', '[]')
    con.close()
```

- [ ] **Step 6: 跑两个测试确认通过**

Run: `python -m pytest tests/test_backtest_observability.py -v`
Expected: 2 passed.

- [ ] **Step 7: 扩展 BacktestResult dataclass**

Edit `backtest/base.py`:

```python
@dataclass
class BacktestResult:
    """One agent's outcome over a backtest window."""
    id: str
    session_id: str
    agent_id: str
    persona_id: str | None
    model_id: str | None
    start_date: str
    end_date: str
    initial_capital: float
    stats: BacktestStats
    zone_stats: list             # list[ZoneStats]
    quality_gate_label: str      # 'pass' | 'warn' | 'fail'
    quality_gate_criteria: dict
    final_equity: float | None = None
    daily_records: list = None   # list[dict] — per-day equity/cash/pnl_pct
    trades: list = None          # list[dict] — per-fill {date,code,action,shares,price,fee}
    thinking: list = None        # list[dict] — per-day LLM reasoning + tool_calls + decisions

    def __post_init__(self):
        # Ensure mutable-default safety without frozen=True constraints.
        if self.daily_records is None:
            self.daily_records = []
        if self.trades is None:
            self.trades = []
        if self.thinking is None:
            self.thinking = []
```

- [ ] **Step 8: 测 dataclass 默认值**

Append to `tests/test_backtest_observability.py`:

```python
def test_backtest_result_observability_defaults_empty():
    from backtest.base import BacktestResult, BacktestStats
    r = BacktestResult(
        id='r', session_id='s', agent_id='a',
        persona_id=None, model_id=None,
        start_date='2025-01-01', end_date='2025-01-10',
        initial_capital=100_000.0,
        stats=BacktestStats(
            sharpe=0.0, max_drawdown_pct=0.0, trade_count=0,
            win_rate=0.0, max_daily_loss_pct=0.0,
            total_return_pct=0.0, final_equity=100_000.0,
        ),
        zone_stats=[],
        quality_gate_label='warn', quality_gate_criteria={},
    )
    assert r.daily_records == []
    assert r.trades == []
    assert r.thinking == []
```

- [ ] **Step 9: 跑测试 + commit**

Run: `python -m pytest tests/test_backtest_observability.py -v`
Expected: 3 passed.

```bash
git add data_schema/backtest_state.py backtest/base.py tests/test_backtest_observability.py
git commit -m "feat(p3a): schema + dataclass for daily_records/trades/thinking"
```

---

### Task 2: Book 记录 fills；BacktestRunner 采集 trades

**Files:**
- Modify: `backtest/book.py:32-86`
- Modify: `backtest/runner.py:67-138`
- Test: `tests/test_backtest_observability.py`

- [ ] **Step 1: 写 Book.fills 测试**

Append to `tests/test_backtest_observability.py`:

```python
def test_book_records_fills_on_buy_and_sell():
    from datetime import date
    from backtest.book import Book
    from backtest.commission import FeeModel

    book = Book(cash=100_000.0, fee_model=FeeModel())
    d1 = date(2025, 1, 2)
    d2 = date(2025, 1, 3)
    fill1 = book.execute_buy('600519.SH', shares=100, price=1000.0, d=d1)
    fill2 = book.execute_sell('600519.SH', shares=50, price=1100.0, d=d2)

    assert fill1 is not None
    assert fill2 is not None
    assert len(book.fills) == 2
    f1, f2 = book.fills
    assert f1.side == 'buy'
    assert f1.shares == 100
    assert f1.date == d1
    assert f2.side == 'sell'
    assert f2.shares == 50
    assert f2.date == d2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_backtest_observability.py::test_book_records_fills_on_buy_and_sell -v`
Expected: FAIL — `Book` 无 `fills` 属性。

- [ ] **Step 3: 改 Book 加 fills 列表**

Edit `backtest/book.py`:

```python
@dataclass
class Book:
    cash: float
    fee_model: FeeModel
    _tranches: dict = field(default_factory=dict)  # code -> list[Tranche]
    total_fees: float = 0.0
    fills: list = field(default_factory=list)  # list[Fill] — all executed trades in order
```

Then inside `execute_buy`, 在 `return Fill(...)` 之前：

```python
        fill = Fill(code=code, side='buy', shares=shares, price=price,
                    fee=fee, date=d)
        self.fills.append(fill)
        return fill
```

Same for `execute_sell`, 在 `return Fill(...)` 之前：

```python
        fill = Fill(code=code, side='sell', shares=to_sell, price=price,
                    fee=fee, date=d)
        self.fills.append(fill)
        return fill
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_backtest_observability.py::test_book_records_fills_on_buy_and_sell -v`
Expected: PASS.

- [ ] **Step 5: 写 BacktestRunner 采集 trades 测试**

Append to `tests/test_backtest_observability.py`:

```python
def test_backtest_runner_populates_trades_and_daily_records(tmp_path, monkeypatch):
    """端到端：MockLLM 买1天卖1天，result.trades 和 daily_records 不为空。"""
    from datetime import date, datetime
    import storage
    from llm.mock import MockLLM
    from personas import seed_builtin_personas
    from storage.sqlite_kline import SQLiteKlineStore
    from storage.sqlite_agents import SQLiteAgentStore
    from storage.sqlite_personas import SQLitePersonaStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    from storage.sqlite_redline import SQLiteRedLineStore
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.sqlite_audit import SQLiteAuditStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_models import SQLiteModelStore

    # Point storage factory at tmp
    storage.reset()
    storage.set_kline(SQLiteKlineStore(tmp_path))
    storage.set_agents(SQLiteAgentStore(tmp_path))
    storage.set_personas(SQLitePersonaStore(tmp_path))
    storage.set_prompt_versions(SQLitePromptVersionStore(tmp_path))
    storage.set_redline(SQLiteRedLineStore(tmp_path))
    storage.set_stock_status(SQLiteStockStatusStore(tmp_path))
    storage.set_audit(SQLiteAuditStore(tmp_path))
    storage.set_backtests(SQLiteBacktestResultStore(tmp_path))
    storage.set_llm_cache(SQLiteLLMDecisionCache(tmp_path))
    storage.set_calendar(SQLiteCalendarStore(tmp_path))
    storage.set_models(SQLiteModelStore(tmp_path))
    for s in (storage.kline(), storage.agents(), storage.personas(),
              storage.prompt_versions(), storage.redline(),
              storage.stock_status(), storage.audit(),
              storage.backtests(), storage.llm_cache(),
              storage.calendar(), storage.models()):
        s.init_schema()
    storage.personas().upsert  # sanity
    seed_builtin_personas()
    storage.models().seed()

    # Seed 5 trading days of price data
    from vnpy.trader.object import BarData
    from vnpy.trader.constant import Exchange, Interval
    code = '600519.SH'
    for i, price in enumerate([1000, 1010, 1020, 1015, 1025]):
        d = datetime(2025, 1, 2 + i)
        bar = BarData(symbol='600519', exchange=Exchange.SSE,
                      datetime=d, interval=Interval.DAILY,
                      open_price=price, high_price=price+5,
                      low_price=price-5, close_price=price,
                      volume=1000, gateway_name='test')
        storage.kline().save_bars([bar])

    agent = storage.agents().create_from_persona(
        persona_id='linyuan_consumer', model_id='claude-sonnet-4-5',
        display_name='t-p3a', initial_capital=1_000_000.0,
    )

    # Build a MockLLM that alternates buy/sell days
    script = [
        {'action': 'buy', 'code': '600519.SH', 'shares': 100, 'reasoning': 'buy day'},
        {'action': 'sell', 'code': '600519.SH', 'shares': 100, 'reasoning': 'sell day'},
        {'action': 'hold', 'reasoning': 'hold day'},
    ]
    llm = MockLLM(scripted_decisions=script)

    from backtest.runner import BacktestRunner
    r = BacktestRunner(llm=llm).run(
        session_id='s-p3a', agent_id=agent.id,
        start_date='2025-01-02', end_date='2025-01-08',
        universe=[code],
    )
    assert len(r.daily_records) >= 3
    assert all('equity' in rec and 'date' in rec for rec in r.daily_records)
    assert len(r.trades) >= 2  # 1 buy + 1 sell at minimum
    # trade entries have the required fields
    t = r.trades[0]
    assert set(t) >= {'date', 'code', 'action', 'shares', 'price', 'fee'}
```

If MockLLM's `scripted_decisions` kwarg doesn't exist — check `llm/mock.py` — this test shows the right signature. Adjust accordingly.

- [ ] **Step 6: 跑测试确认失败**

Run: `python -m pytest tests/test_backtest_observability.py::test_backtest_runner_populates_trades_and_daily_records -v`
Expected: FAIL — `r.trades` is `[]` (runner isn't populating).

- [ ] **Step 7: Runner 采集 trades + daily_records 填入 result**

Edit `backtest/runner.py`. Find the block starting with `result = BacktestResult(...)` at the end of `run()` and expand it:

```python
        # --- P3-A: collect observability data ---
        trades_serial = [
            {
                'date': f.date.isoformat(),
                'code': f.code,
                'action': f.side,
                'shares': f.shares,
                'price': f.price,
                'fee': f.fee,
            }
            for f in book.fills
        ]
        daily_records_serial = [
            {
                'date': rec['date'].isoformat(),
                'equity': rec['equity'],
                'cash': None,  # backfilled below
                'pnl_pct': rec['pnl_pct'],
                'trade_count': rec['trade_count'],
                'won': rec['won'],
            }
            for rec in daily_records
        ]
        # Note: we didn't track cash per day in the runner previously.
        # For MVP we leave cash=None; Task 3 can either wire it through or
        # the UI computes it as equity - (positions_value). Keeping it
        # conservative here — minimal runner change.

        result = BacktestResult(
            id=str(uuid.uuid4()),
            session_id=session_id, agent_id=agent_id,
            persona_id=persona_id, model_id=model_id,
            start_date=start_date, end_date=end_date,
            initial_capital=cap, stats=overall, zone_stats=zones,
            quality_gate_label=gate.label,
            quality_gate_criteria=gate.criteria,
            final_equity=prev_equity,
            daily_records=daily_records_serial,
            trades=trades_serial,
            thinking=[],  # populated in Task 3
        )
```

Also inside the per-day loop, track cash. Find:

```python
            daily_records.append({
                'date': d, 'pnl_pct': pnl_pct, 'equity': equity,
                'trade_count': trade_count_today, 'won': wins_today,
            })
```

and change to include cash:

```python
            daily_records.append({
                'date': d, 'pnl_pct': pnl_pct, 'equity': equity,
                'cash': book.cash,
                'trade_count': trade_count_today, 'won': wins_today,
            })
```

Then update `daily_records_serial` to read `rec['cash']` instead of `None`.

- [ ] **Step 8: 跑测试确认通过**

Run: `python -m pytest tests/test_backtest_observability.py::test_backtest_runner_populates_trades_and_daily_records -v`
Expected: PASS.

- [ ] **Step 9: commit**

```bash
git add backtest/book.py backtest/runner.py tests/test_backtest_observability.py
git commit -m "feat(p3a): Book.fills + Runner collects trades/daily_records"
```

---

### Task 3: AgentRunner 采集 thinking，BacktestRunner 汇总

**Files:**
- Modify: `agents/runner.py:39-177`
- Modify: `backtest/runner.py`
- Test: `tests/test_backtest_observability.py`

**Design note:** 当前 `run_day` 只返回 `list[dict]` of decisions。最小侵入：在 `AgentRunner` 上加可选属性 `_last_thinking`，由调用方在每次 `run_day` 后读取。这样签名不破坏现有测试。

- [ ] **Step 1: 写 thinking 采集测试**

Append to `tests/test_backtest_observability.py`:

```python
def test_agent_runner_captures_thinking_per_day(tmp_path):
    """run_day 之后 last_thinking 包含 reasoning / tool_calls / decisions。"""
    from agents.runner import AgentRunner
    from llm.base import Message, ToolCall, LLMResponse
    from llm.mock import MockLLM

    class InstrumentedLLM(MockLLM):
        def chat(self, *, messages, tools):
            # First turn: call place_decision
            return LLMResponse(
                messages=[Message(role='assistant',
                                  content='Buy MT bc consumer strong')],
                tool_calls=[ToolCall(
                    id='call1', name='place_decision',
                    input={'action': 'buy', 'code': '600519.SH',
                           'shares': 100, 'reasoning': 'strong brand'},
                )],
                raw={},
            )

    import storage
    # ... (same setup fixture as Task 2 test)
    # key assertions:
    runner = AgentRunner(llm=InstrumentedLLM(scripted_decisions=[]))
    # Need a seeded agent + kline; reuse same fixture setup as previous test
    # ... (refactor to share setup via pytest fixture — see next step)
```

Refactor: create a `conftest.py`-level fixture `observability_storage` so both tests share setup. Put it at top of `tests/test_backtest_observability.py`:

```python
@pytest.fixture
def observability_storage(tmp_path):
    """Wires storage factory to tmp_path and seeds personas + models + kline."""
    import storage
    from datetime import datetime
    from personas import seed_builtin_personas
    from storage.sqlite_kline import SQLiteKlineStore
    from storage.sqlite_agents import SQLiteAgentStore
    from storage.sqlite_personas import SQLitePersonaStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    from storage.sqlite_redline import SQLiteRedLineStore
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.sqlite_audit import SQLiteAuditStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_models import SQLiteModelStore
    from vnpy.trader.object import BarData
    from vnpy.trader.constant import Exchange, Interval

    storage.reset()
    storage.set_kline(SQLiteKlineStore(tmp_path))
    storage.set_agents(SQLiteAgentStore(tmp_path))
    storage.set_personas(SQLitePersonaStore(tmp_path))
    storage.set_prompt_versions(SQLitePromptVersionStore(tmp_path))
    storage.set_redline(SQLiteRedLineStore(tmp_path))
    storage.set_stock_status(SQLiteStockStatusStore(tmp_path))
    storage.set_audit(SQLiteAuditStore(tmp_path))
    storage.set_backtests(SQLiteBacktestResultStore(tmp_path))
    storage.set_llm_cache(SQLiteLLMDecisionCache(tmp_path))
    storage.set_calendar(SQLiteCalendarStore(tmp_path))
    storage.set_models(SQLiteModelStore(tmp_path))
    for s in (storage.kline(), storage.agents(), storage.personas(),
              storage.prompt_versions(), storage.redline(),
              storage.stock_status(), storage.audit(),
              storage.backtests(), storage.llm_cache(),
              storage.calendar(), storage.models()):
        s.init_schema()
    seed_builtin_personas()
    storage.models().seed()

    # Seed 7 trading days of one stock
    code = '600519.SH'
    for i, price in enumerate([1000, 1010, 1020, 1015, 1025, 1030, 1040]):
        d = datetime(2025, 1, 2 + i)
        bar = BarData(symbol='600519', exchange=Exchange.SSE,
                      datetime=d, interval=Interval.DAILY,
                      open_price=price, high_price=price+5,
                      low_price=price-5, close_price=price,
                      volume=1000, gateway_name='test')
        storage.kline().save_bars([bar])

    yield tmp_path
    storage.reset()
```

Now the Task 2 test can use `observability_storage(tmp_path)` and drop the big setup block.

Re-write the thinking test:

```python
def test_agent_runner_captures_thinking_per_day(observability_storage):
    from agents.runner import AgentRunner
    from llm.base import Message, ToolCall, LLMResponse
    import storage

    class InstrumentedLLM:
        def chat(self, *, messages, tools):
            return LLMResponse(
                messages=[Message(role='assistant',
                                  content='strong consumer brand')],
                tool_calls=[ToolCall(
                    id='c1', name='place_decision',
                    input={'action': 'buy', 'code': '600519.SH',
                           'shares': 100, 'reasoning': 'buy now'},
                )],
                raw={},
            )

    agent = storage.agents().create_from_persona(
        persona_id='linyuan_consumer', model_id='claude-sonnet-4-5',
        display_name='t-thk', initial_capital=1_000_000.0,
    )
    runner = AgentRunner(llm=InstrumentedLLM())
    runner.run_day(
        agent_id=agent.id, date='2025-01-03',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 1000.0},
    )
    # AgentRunner exposes last-call thinking
    thk = runner.last_thinking
    assert thk is not None
    assert thk['reasoning'].startswith('strong consumer')
    assert len(thk['decisions']) == 1
    assert thk['decisions'][0]['action'] == 'buy'
    assert isinstance(thk['tool_calls'], list)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_backtest_observability.py::test_agent_runner_captures_thinking_per_day -v`
Expected: FAIL — no `last_thinking` attribute.

- [ ] **Step 3: AgentRunner 捕获每次 run_day 的 thinking**

Edit `agents/runner.py`:

```python
class AgentRunner:
    def __init__(self, llm, engine: ValidationEngine | None = None,
                 max_iterations: int = _MAX_TOOL_ITERATIONS):
        self._llm = llm
        self._engine = engine or ValidationEngine()
        self._max_iterations = max_iterations
        self.last_thinking: dict | None = None

    def run_day(self, *, agent_id, date, portfolio, market_context,
                mark_prices, market_snapshot=None) -> list[dict]:
        # ... existing setup ...

        # P3-A: accumulate per-day thinking
        thinking_reasoning: list[str] = []
        thinking_tool_calls: list[dict] = []
        thinking_decisions: list[dict] = []

        for _ in range(self._max_iterations):
            resp = self._llm.chat(messages=convo, tools=tool_specs)

            # Capture assistant text for thinking
            for m in resp.messages:
                if m.content:
                    thinking_reasoning.append(m.content)

            if not resp.tool_calls:
                break
            # ... existing assistant_content / convo append ...

            for call in resp.tool_calls:
                if call.name == 'place_decision':
                    decision = dict(call.input)
                    decision.setdefault('shares', decision.get('qty', 0))
                    decision.setdefault('price',
                                        mark_prices.get(decision.get('code'),
                                                        0.0))
                    result = self._engine.validate(...)
                    # Record decision regardless of validation outcome so
                    # users can see rejected attempts in the Thinking panel.
                    thinking_decisions.append({
                        'action': decision.get('action'),
                        'code': decision.get('code'),
                        'shares': decision.get('shares'),
                        'price': decision.get('price'),
                        'outcome': result.outcome,
                        'reasoning': decision.get('reasoning'),
                    })
                    if result.outcome != 'rejected' and result.decision_out:
                        decisions_executed.append(result.decision_out)
                    terminated = True
                    break

                # non-place_decision → record as research tool call
                thinking_tool_calls.append({
                    'name': call.name,
                    'input': call.input or {},
                })

                entry = allowed.get(call.name)
                # ... existing tool-result handling ...

            # ... existing terminated/convo append ...

        cache.put(...)

        self.last_thinking = {
            'reasoning': '\n'.join(thinking_reasoning).strip(),
            'tool_calls': thinking_tool_calls,
            'decisions': thinking_decisions,
        }
        return decisions_executed
```

Important: if the cached-decision early-return path is taken (`cached is not None`), set `self.last_thinking` to a synthetic entry so the backtest runner gets consistent shape:

```python
        cached = cache.get(cache_key)
        if cached is not None:
            self.last_thinking = {
                'reasoning': '(cached — no LLM call)',
                'tool_calls': [],
                'decisions': [
                    {'action': d.get('action'), 'code': d.get('code'),
                     'shares': d.get('shares'), 'price': d.get('price'),
                     'outcome': 'cached',
                     'reasoning': d.get('reasoning')}
                    for d in cached.decisions
                ],
            }
            return list(cached.decisions)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_backtest_observability.py::test_agent_runner_captures_thinking_per_day -v`
Expected: PASS.

- [ ] **Step 5: BacktestRunner 把每日 thinking 串成列表**

Edit `backtest/runner.py`. Inside per-day loop, after `runner.run_day(...)`:

```python
            decisions = runner.run_day(
                agent_id=agent_id, date=d.strftime('%Y-%m-%d'),
                portfolio=portfolio, market_context={},
                mark_prices=mark_prices,
                market_snapshot=snapshot,
            )
            # P3-A: capture per-day thinking
            per_day_thinking.append({
                'date': d.strftime('%Y-%m-%d'),
                **(runner.last_thinking or {'reasoning': '', 'tool_calls': [],
                                            'decisions': []}),
            })
```

Above the loop, initialize:

```python
        per_day_thinking: list[dict] = []
```

Then when building `result`, pass `thinking=per_day_thinking` instead of `[]`.

- [ ] **Step 6: 更新端到端测试验证 thinking**

Extend the Task 2 test (`test_backtest_runner_populates_trades_and_daily_records`) — add at the end:

```python
    assert len(r.thinking) >= 3
    t0 = r.thinking[0]
    assert 'date' in t0
    assert 'reasoning' in t0
    assert 'tool_calls' in t0
    assert 'decisions' in t0
```

- [ ] **Step 7: 跑完整测试 + commit**

Run: `python -m pytest tests/test_backtest_observability.py -v`
Expected: 4 passed.

```bash
git add agents/runner.py backtest/runner.py tests/test_backtest_observability.py
git commit -m "feat(p3a): AgentRunner.last_thinking + Runner collects per-day thinking"
```

---

### Task 4: Storage 持久化 3 个 JSON 列

**Files:**
- Modify: `storage/sqlite_backtests.py:19-184`
- Test: `tests/test_backtest_observability.py`

- [ ] **Step 1: 写持久化 roundtrip 测试**

Append to `tests/test_backtest_observability.py`:

```python
def test_sqlite_backtests_roundtrips_observability_fields(tmp_path):
    from backtest.base import BacktestResult, BacktestStats, ZoneStats
    from storage.sqlite_backtests import SQLiteBacktestResultStore

    store = SQLiteBacktestResultStore(tmp_path)
    store.init_schema()
    store.create_session('s1', '2025-01-01', '2025-01-10', ['a1'])

    result = BacktestResult(
        id='r1', session_id='s1', agent_id='a1',
        persona_id=None, model_id=None,
        start_date='2025-01-01', end_date='2025-01-10',
        initial_capital=100_000.0,
        stats=BacktestStats(
            sharpe=1.2, max_drawdown_pct=-5.0, trade_count=4,
            win_rate=75.0, max_daily_loss_pct=-1.5,
            total_return_pct=8.0, final_equity=108_000.0,
        ),
        zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        final_equity=108_000.0,
        daily_records=[{'date': '2025-01-02', 'equity': 100_500.0,
                        'cash': 50_000.0, 'pnl_pct': 0.5,
                        'trade_count': 1, 'won': 1}],
        trades=[{'date': '2025-01-02', 'code': '600519.SH',
                 'action': 'buy', 'shares': 100, 'price': 500.0, 'fee': 15.0}],
        thinking=[{'date': '2025-01-02', 'reasoning': 'strong brand',
                   'tool_calls': [], 'decisions': []}],
    )
    store.insert(result)

    fetched = store.get('r1')
    assert fetched is not None
    assert len(fetched.daily_records) == 1
    assert fetched.daily_records[0]['equity'] == 100_500.0
    assert fetched.trades[0]['code'] == '600519.SH'
    assert fetched.thinking[0]['reasoning'] == 'strong brand'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_backtest_observability.py::test_sqlite_backtests_roundtrips_observability_fields -v`
Expected: FAIL — store ignores the 3 new fields.

- [ ] **Step 3: Store insert + select 覆盖新列**

Edit `storage/sqlite_backtests.py`:

Update `_row_to_result` to read trailing columns:

```python
def _row_to_result(row):
    from backtest.base import BacktestResult, BacktestStats, ZoneStats
    stats_d = json.loads(row[9])
    stats = BacktestStats(**stats_d)
    zone_raw = json.loads(row[10])
    zones = [ZoneStats(**z) for z in zone_raw]
    # row[11]=quality_gate_label, row[12]=quality_gate_json
    # row[13]=daily_records_json, row[14]=trades_json, row[15]=thinking_json
    daily_records = json.loads(row[13]) if len(row) > 13 and row[13] else []
    trades = json.loads(row[14]) if len(row) > 14 and row[14] else []
    thinking = json.loads(row[15]) if len(row) > 15 and row[15] else []
    return BacktestResult(
        id=row[0], session_id=row[1], agent_id=row[2],
        persona_id=row[3], model_id=row[4],
        start_date=row[5], end_date=row[6],
        initial_capital=row[7], final_equity=row[8],
        stats=stats, zone_stats=zones,
        quality_gate_label=row[11],
        quality_gate_criteria=json.loads(row[12]),
        daily_records=daily_records,
        trades=trades,
        thinking=thinking,
    )
```

Update `_select_cols`:

```python
    def _select_cols(self):
        return ('id, session_id, agent_id, persona_id, model_id, '
                'start_date, end_date, initial_capital, final_equity, '
                'stats_json, zone_stats_json, quality_gate_label, '
                'quality_gate_json, daily_records_json, '
                'trades_json, thinking_json')
```

Update `insert`:

```python
    def insert(self, result) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_BACKTEST_RESULTS)
            from data_schema.backtest_state import ensure_observability_columns
            ensure_observability_columns(con)  # migrate old schema if needed
            zone_serial = json.dumps(
                [asdict(z) for z in result.zone_stats], ensure_ascii=False,
            )
            daily_records = getattr(result, 'daily_records', None) or []
            trades = getattr(result, 'trades', None) or []
            thinking = getattr(result, 'thinking', None) or []
            con.execute(
                '''INSERT OR REPLACE INTO backtest_results
                   (id, session_id, agent_id, persona_id, model_id,
                    start_date, end_date, initial_capital, final_equity,
                    stats_json, zone_stats_json,
                    quality_gate_label, quality_gate_json,
                    daily_records_json, trades_json, thinking_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (result.id, result.session_id, result.agent_id,
                 result.persona_id, result.model_id,
                 result.start_date, result.end_date,
                 result.initial_capital, result.final_equity,
                 json.dumps(asdict(result.stats), ensure_ascii=False),
                 zone_serial,
                 result.quality_gate_label,
                 json.dumps(result.quality_gate_criteria, ensure_ascii=False),
                 json.dumps(daily_records, ensure_ascii=False,
                            default=str),
                 json.dumps(trades, ensure_ascii=False, default=str),
                 json.dumps(thinking, ensure_ascii=False, default=str)),
            )
            con.commit()
        finally:
            con.close()
```

`init_schema` also needs to call `ensure_observability_columns` for migration:

```python
    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_BACKTEST_SESSIONS)
            con.executescript(SCHEMA_BACKTEST_RESULTS)
            from data_schema.backtest_state import ensure_observability_columns
            ensure_observability_columns(con)
            con.commit()
        finally:
            con.close()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_backtest_observability.py -v`
Expected: 5 passed.

- [ ] **Step 5: 跑全量测试 — 确认不破坏旧测试**

Run: `python -m pytest -q`
Expected: 全部 pass（当前基线 429 + P3-A 5 = 434）。

- [ ] **Step 6: commit**

```bash
git add storage/sqlite_backtests.py
git commit -m "feat(p3a): persist daily_records/trades/thinking to sqlite"
```

---

### Task 5: 3 个后端端点

**Files:**
- Modify: `api/backtests.py`
- Test: `tests/test_backtest_observability.py`

- [ ] **Step 1: 写端点测试**

Append to `tests/test_backtest_observability.py`:

```python
def test_nav_endpoint_returns_daily_curves(observability_storage, client):
    """GET /api/backtests/:id/nav returns agent curve + baseline curves."""
    import storage
    from backtest.base import BacktestResult, BacktestStats
    r = BacktestResult(
        id='nav1', session_id='s1', agent_id='a1',
        persona_id=None, model_id=None,
        start_date='2025-01-02', end_date='2025-01-08',
        initial_capital=100_000.0,
        stats=BacktestStats(sharpe=1.0, max_drawdown_pct=-1.0,
                            trade_count=0, win_rate=0.0,
                            max_daily_loss_pct=0.0, total_return_pct=2.0,
                            final_equity=102_000.0),
        zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        daily_records=[
            {'date': '2025-01-02', 'equity': 100_000.0, 'cash': 100_000.0,
             'pnl_pct': 0.0, 'trade_count': 0, 'won': 0},
            {'date': '2025-01-03', 'equity': 101_000.0, 'cash': 0.0,
             'pnl_pct': 1.0, 'trade_count': 1, 'won': 0},
        ],
    )
    storage.backtests().create_session('s1', '2025-01-02', '2025-01-08', ['a1'])
    storage.backtests().insert(r)

    resp = client.get('/api/backtests/nav1/nav')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'agent' in data
    assert len(data['agent']) == 2
    assert data['agent'][0]['date'] == '2025-01-02'
    assert data['agent'][0]['equity'] == 100_000.0
    assert 'baselines' in data
    assert isinstance(data['baselines'], list)


def test_nav_endpoint_404_on_missing(client):
    resp = client.get('/api/backtests/nope/nav')
    assert resp.status_code == 404


def test_trades_endpoint_returns_fills(observability_storage, client):
    import storage
    from backtest.base import BacktestResult, BacktestStats
    r = BacktestResult(
        id='tr1', session_id='s2', agent_id='a1',
        persona_id=None, model_id=None,
        start_date='2025-01-02', end_date='2025-01-08',
        initial_capital=100_000.0,
        stats=BacktestStats(sharpe=0.0, max_drawdown_pct=0.0, trade_count=1,
                            win_rate=0.0, max_daily_loss_pct=0.0,
                            total_return_pct=0.0, final_equity=100_000.0),
        zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        trades=[{'date': '2025-01-03', 'code': '600519.SH',
                 'action': 'buy', 'shares': 100, 'price': 500.0, 'fee': 15.0}],
    )
    storage.backtests().create_session('s2', '2025-01-02', '2025-01-08', ['a1'])
    storage.backtests().insert(r)

    resp = client.get('/api/backtests/tr1/trades')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'trades' in data
    assert data['trades'][0]['code'] == '600519.SH'


def test_thinking_endpoint_returns_per_day_reasoning(observability_storage, client):
    import storage
    from backtest.base import BacktestResult, BacktestStats
    r = BacktestResult(
        id='th1', session_id='s3', agent_id='a1',
        persona_id=None, model_id=None,
        start_date='2025-01-02', end_date='2025-01-08',
        initial_capital=100_000.0,
        stats=BacktestStats(sharpe=0.0, max_drawdown_pct=0.0, trade_count=0,
                            win_rate=0.0, max_daily_loss_pct=0.0,
                            total_return_pct=0.0, final_equity=100_000.0),
        zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        thinking=[{'date': '2025-01-02',
                   'reasoning': 'strong consumer brand',
                   'tool_calls': [],
                   'decisions': [{'action': 'buy', 'code': '600519.SH',
                                  'shares': 100, 'price': 1000.0,
                                  'outcome': 'ok',
                                  'reasoning': 'buy'}]}],
    )
    storage.backtests().create_session('s3', '2025-01-02', '2025-01-08', ['a1'])
    storage.backtests().insert(r)

    resp = client.get('/api/backtests/th1/thinking')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'thinking' in data
    assert data['thinking'][0]['reasoning'] == 'strong consumer brand'
    assert data['thinking'][0]['decisions'][0]['action'] == 'buy'
```

Also ensure `conftest.py` (repo root) has a `client` fixture or create one in this test file. Check existing tests for pattern. If `tests/conftest.py` exists with a client fixture, use it. Otherwise add at top:

```python
@pytest.fixture
def client(observability_storage):
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_backtest_observability.py -v -k endpoint`
Expected: FAIL — 3 routes 404.

- [ ] **Step 3: 实现 3 个端点**

Edit `api/backtests.py`, append at the end (but before any imports section if reorganizing). Add:

```python
@api_bp.route('/backtests/<result_id>/nav')
def get_backtest_nav(result_id):
    """Daily equity curve for one backtest + same-session baselines.

    Response: {
      'agent': [{date, equity, cash, pnl_pct}, ...],
      'baselines': [{name, curve: [{date, equity}, ...]}, ...]
    }
    """
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    agent_curve = [
        {'date': rec.get('date'),
         'equity': rec.get('equity'),
         'cash': rec.get('cash'),
         'pnl_pct': rec.get('pnl_pct')}
        for rec in (r.daily_records or [])
    ]
    # Join with session's baselines (they also have daily records)
    baselines_payload: list[dict] = []
    for b in storage.baselines().list_for_session(r.session_id):
        b_curve = []
        # BaselineResult may have daily_records attr (added to baseline dataclass
        # in Task 6 if desired) OR we skip and return empty curve for now.
        b_records = getattr(b, 'daily_records', None) or []
        for rec in b_records:
            b_curve.append({'date': rec.get('date'),
                            'equity': rec.get('equity')})
        baselines_payload.append({'name': b.name, 'curve': b_curve})
    return jsonify({
        'result_id': result_id,
        'agent': agent_curve,
        'baselines': baselines_payload,
    })


@api_bp.route('/backtests/<result_id>/trades')
def get_backtest_trades(result_id):
    """List all fills for a backtest (ordered chronologically)."""
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'result_id': result_id,
        'trades': list(r.trades or []),
    })


@api_bp.route('/backtests/<result_id>/thinking')
def get_backtest_thinking(result_id):
    """Per-day LLM reasoning + tool_calls + decisions for a backtest."""
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'result_id': result_id,
        'thinking': list(r.thinking or []),
    })
```

Note on baselines: if `BaselineResult` doesn't carry `daily_records` yet, the `baselines` key will always have empty curves. That's fine for this task — users still see the agent curve. Adding baseline NAV persistence is a nice-to-have, done in Task 6 (optional).

- [ ] **Step 4: 跑端点测试确认通过**

Run: `python -m pytest tests/test_backtest_observability.py -v`
Expected: 所有通过（5 + 4 = 9 total）。

- [ ] **Step 5: commit**

```bash
git add api/backtests.py tests/test_backtest_observability.py
git commit -m "feat(p3a): GET /api/backtests/:id/{nav,trades,thinking}"
```

---

### Task 6: Baseline NAV 持久化（可选增强）

**Files:**
- Modify: `backtest/baselines/base.py`
- Modify: `backtest/baselines/*.py` — buy_and_hold / equal_weight / csi300
- Modify: `storage/sqlite_baselines.py`
- Modify: `data_schema/baseline_state.py`
- Test: `tests/test_backtest_observability.py`

**Rationale:** 没有 baselines 的 daily_records 做对比，4-curve chart 就是 1 条曲线。花半天补上 baseline 的持久化。如果 baselines 是本次不做，Task 5 的 `baselines` 数组永远是空，前端要 tolerant。

- [ ] **Step 1: 决定范围**

用户选择：
- (A) 本任务做满，baselines 也有 daily_records
- (B) 跳过本任务，前端 4-curve 简化为 1-curve + 底部标注"对照组曲线即将上线"

默认 (A)。如果时间紧可换 (B)。

- [ ] **Step 2-N: 若选 (A)，镜像 Task 1 + 4 的改法到 baselines**

Steps omitted for brevity — same pattern. Add `daily_records_json` to baseline_results schema + `BaselineResult.daily_records` field + baseline runners collect it.

If (B): skip directly to Task 7 and add copy to `NavChart.tsx`: "对照组曲线将在后续版本支持"。

---

### Task 7: 前端安装 lightweight-charts + 加类型 + 加 hooks

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/hooks.ts`

- [ ] **Step 1: 安装 lightweight-charts**

```bash
cd frontend && npm install lightweight-charts@^4.2
```

Expected: `package.json` 和 `package-lock.json` 更新，`dependencies.lightweight-charts` 出现。

- [ ] **Step 2: 加类型定义**

Edit `frontend/src/api/types.ts`, append:

```typescript
export type NavPoint = {
  date: string;
  equity: number;
  cash?: number | null;
  pnl_pct?: number | null;
};

export type NavResponse = {
  result_id: string;
  agent: NavPoint[];
  baselines: Array<{ name: string; curve: Array<{ date: string; equity: number }> }>;
};

export type TradeRow = {
  date: string;
  code: string;
  action: 'buy' | 'sell';
  shares: number;
  price: number;
  fee: number;
};

export type TradesResponse = {
  result_id: string;
  trades: TradeRow[];
};

export type ThinkingEntry = {
  date: string;
  reasoning: string;
  tool_calls: Array<{ name: string; input: Record<string, unknown> }>;
  decisions: Array<{
    action: string;
    code?: string;
    shares?: number;
    price?: number;
    outcome?: string;
    reasoning?: string;
  }>;
};

export type ThinkingResponse = {
  result_id: string;
  thinking: ThinkingEntry[];
};

export type StrategyRating = {
  overall: number;
  letter: 'A+' | 'A' | 'B' | 'C' | 'D';
  returns: number;
  sharpe: number;
  drawdown: number;
  win_rate: number;
  consistency: number;
  notes: string[];
};
```

- [ ] **Step 3: 加 hooks**

Edit `frontend/src/api/hooks.ts`. Follow existing pattern (likely `useQuery` from TanStack). Append:

```typescript
export function useBacktestNav(resultId: string | undefined) {
  return useQuery({
    queryKey: ['backtest-nav', resultId],
    queryFn: async () => {
      const r = await fetch(`/api/backtests/${resultId}/nav`);
      if (!r.ok) throw new Error(`nav fetch failed: ${r.status}`);
      return (await r.json()) as NavResponse;
    },
    enabled: !!resultId,
  });
}

export function useBacktestTrades(resultId: string | undefined) {
  return useQuery({
    queryKey: ['backtest-trades', resultId],
    queryFn: async () => {
      const r = await fetch(`/api/backtests/${resultId}/trades`);
      if (!r.ok) throw new Error(`trades fetch failed: ${r.status}`);
      return (await r.json()) as TradesResponse;
    },
    enabled: !!resultId,
  });
}

export function useBacktestThinking(resultId: string | undefined) {
  return useQuery({
    queryKey: ['backtest-thinking', resultId],
    queryFn: async () => {
      const r = await fetch(`/api/backtests/${resultId}/thinking`);
      if (!r.ok) throw new Error(`thinking fetch failed: ${r.status}`);
      return (await r.json()) as ThinkingResponse;
    },
    enabled: !!resultId,
  });
}

export function useBacktestRating(resultId: string | undefined) {
  return useQuery({
    queryKey: ['backtest-rating', resultId],
    queryFn: async () => {
      const r = await fetch(`/api/backtests/${resultId}/rating`);
      if (!r.ok) throw new Error(`rating fetch failed: ${r.status}`);
      return (await r.json()) as StrategyRating;
    },
    enabled: !!resultId,
  });
}
```

Import `NavResponse` / `TradesResponse` / `ThinkingResponse` / `StrategyRating` at the top:

```typescript
import type {
  // ... existing imports ...
  NavResponse,
  TradesResponse,
  ThinkingResponse,
  StrategyRating,
} from './types';
```

- [ ] **Step 4: 跑前端构建确认不破 type check**

Run: `cd frontend && npm run build`
Expected: 构建成功，无 TS 错误。

- [ ] **Step 5: commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/api/types.ts frontend/src/api/hooks.ts
git commit -m "feat(p3a): frontend types + hooks for nav/trades/thinking/rating"
```

---

### Task 8: NavChart 4-curve 组件

**Files:**
- Create: `frontend/src/components/NavChart.tsx`

- [ ] **Step 1: 实现 NavChart**

Create `frontend/src/components/NavChart.tsx`. lightweight-charts 是命令式 API，用 `useEffect` 管理 chart 生命周期 + `useRef` 持有 DOM 容器：

```typescript
import { useEffect, useRef } from 'react';
import {
  createChart,
  ColorType,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import type { NavResponse } from '../api/types';

// Agent line = brand gold; baselines walk these accent colors
const COLORS = ['#c9a227', '#808080', '#3b82f6', '#a855f7', '#22c55e'];

function toTimestamp(dateStr: string): UTCTimestamp {
  // Shanghai close is 15:00 CST (UTC+8); lightweight-charts treats time as UTC
  // seconds. Using midnight UTC is fine — lib only uses date for x-axis labels.
  return Math.floor(new Date(dateStr + 'T00:00:00Z').getTime() / 1000) as UTCTimestamp;
}

export function NavChart({ data }: { data: NavResponse | undefined }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'>[]>([]);

  // Create chart once; destroy on unmount
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 320,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#8a8a8a',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(120,120,120,0.15)', style: LineStyle.Dotted },
        horzLines: { color: 'rgba(120,120,120,0.15)', style: LineStyle.Dotted },
      },
      timeScale: {
        borderColor: 'rgba(120,120,120,0.3)',
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: 'rgba(120,120,120,0.3)',
      },
      crosshair: {
        mode: 1, // magnet
      },
    });
    chartRef.current = chart;

    // Resize on container size change
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        chart.applyOptions({ width: e.contentRect.width });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = [];
    };
  }, []);

  // Rebuild series whenever data changes
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !data) return;

    // Remove existing series
    for (const s of seriesRef.current) {
      chart.removeSeries(s);
    }
    seriesRef.current = [];

    const agentSeries = chart.addLineSeries({
      color: COLORS[0],
      lineWidth: 2,
      title: 'Agent',
    });
    agentSeries.setData(
      data.agent.map((p) => ({
        time: toTimestamp(p.date),
        value: p.equity,
      })),
    );
    seriesRef.current.push(agentSeries);

    data.baselines.forEach((b, i) => {
      const s = chart.addLineSeries({
        color: COLORS[(i + 1) % COLORS.length],
        lineWidth: 1,
        title: b.name,
      });
      s.setData(
        b.curve.map((p) => ({
          time: toTimestamp(p.date),
          value: p.equity,
        })),
      );
      seriesRef.current.push(s);
    });

    chart.timeScale().fitContent();
  }, [data]);

  if (!data) {
    return <div className="text-text-faint text-sm">加载中…</div>;
  }
  if (data.agent.length === 0) {
    return (
      <div className="text-text-faint text-sm italic">
        本次回测没有每日权益数据。
      </div>
    );
  }

  const hasBaselines = data.baselines.length > 0;

  return (
    <div>
      <div ref={containerRef} style={{ width: '100%', height: 320 }} />
      <div className="flex flex-wrap gap-3 mt-2 text-[11px]">
        <LegendSwatch color={COLORS[0]} label="Agent" />
        {data.baselines.map((b, i) => (
          <LegendSwatch
            key={b.name}
            color={COLORS[(i + 1) % COLORS.length]}
            label={b.name}
          />
        ))}
        {!hasBaselines && (
          <span className="text-text-faint italic">
            （本次无 baseline 对照曲线）
          </span>
        )}
      </div>
    </div>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        style={{
          width: 14,
          height: 3,
          background: color,
          borderRadius: 1,
          display: 'inline-block',
        }}
      />
      <span className="text-text-dim">{label}</span>
    </span>
  );
}
```

**Notes for reviewer:**
- lightweight-charts is imperative: chart instance lives in a ref, not React state. Two separate useEffects — mount/unmount vs data-sync — are the documented pattern.
- Legend is hand-rolled because lightweight-charts v4 has no built-in Legend component. Colors come from a fixed palette, NOT CSS vars, because the lib wants hex strings (no var() support in canvas rendering).
- `toTimestamp` uses UTC midnight — safe for date-only daily data. Intraday (future P3) will need CST timezone conversion.

- [ ] **Step 2: 构建确认通过**

Run: `cd frontend && npm run build`
Expected: 构建成功。

- [ ] **Step 3: commit**

```bash
git add frontend/src/components/NavChart.tsx
git commit -m "feat(p3a): NavChart with agent + baseline curves"
```

---

### Task 9: TradesTable 组件

**Files:**
- Create: `frontend/src/components/TradesTable.tsx`

- [ ] **Step 1: 实现 TradesTable**

Create `frontend/src/components/TradesTable.tsx`:

```typescript
import { useMemo, useState } from 'react';
import type { TradeRow } from '../api/types';

type SortKey = 'date' | 'code' | 'action' | 'shares' | 'price' | 'fee';

export function TradesTable({
  trades,
  onRowClick,
}: {
  trades: TradeRow[];
  onRowClick?: (t: TradeRow) => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [sortDesc, setSortDesc] = useState(false);
  const [filterCode, setFilterCode] = useState('');
  const [filterAction, setFilterAction] = useState<'all' | 'buy' | 'sell'>('all');

  const filtered = useMemo(() => {
    let rows = trades;
    if (filterCode.trim()) {
      const q = filterCode.trim().toLowerCase();
      rows = rows.filter((t) => t.code.toLowerCase().includes(q));
    }
    if (filterAction !== 'all') {
      rows = rows.filter((t) => t.action === filterAction);
    }
    return [...rows].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === bv) return 0;
      const cmp = av < bv ? -1 : 1;
      return sortDesc ? -cmp : cmp;
    });
  }, [trades, sortKey, sortDesc, filterCode, filterAction]);

  if (trades.length === 0) {
    return (
      <div className="text-text-faint text-sm italic">
        本次回测没有成交记录。
      </div>
    );
  }

  const headerCls = 'cursor-pointer select-none';
  const toggleSort = (k: SortKey) => {
    if (k === sortKey) setSortDesc((d) => !d);
    else {
      setSortKey(k);
      setSortDesc(false);
    }
  };

  return (
    <div>
      <div className="flex gap-2 mb-2 flex-wrap">
        <input
          className="bg-bg-2 border border-panel-border-soft rounded px-2 py-1 text-xs text-text-hi"
          placeholder="过滤股票代码…"
          value={filterCode}
          onChange={(e) => setFilterCode(e.target.value)}
        />
        <select
          className="bg-bg-2 border border-panel-border-soft rounded px-2 py-1 text-xs text-text-hi"
          value={filterAction}
          onChange={(e) => setFilterAction(e.target.value as typeof filterAction)}
        >
          <option value="all">全部方向</option>
          <option value="buy">买入</option>
          <option value="sell">卖出</option>
        </select>
        <span className="text-text-faint text-xs self-center">
          {filtered.length} / {trades.length} 笔
        </span>
      </div>

      <div style={{ border: '1px solid var(--panel-border-soft)', borderRadius: 4, overflow: 'auto' }}>
        <table className="tbl" style={{ margin: 0 }}>
          <thead>
            <tr>
              <th className={headerCls} onClick={() => toggleSort('date')}>日期</th>
              <th className={headerCls} onClick={() => toggleSort('code')}>代码</th>
              <th className={headerCls} onClick={() => toggleSort('action')}>方向</th>
              <th className={`num ${headerCls}`} onClick={() => toggleSort('shares')}>股数</th>
              <th className={`num ${headerCls}`} onClick={() => toggleSort('price')}>成交价</th>
              <th className={`num ${headerCls}`} onClick={() => toggleSort('fee')}>费用</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t, i) => (
              <tr
                key={`${t.date}-${t.code}-${i}`}
                onClick={() => onRowClick?.(t)}
                style={{ cursor: onRowClick ? 'pointer' : 'default' }}
              >
                <td className="mono text-xs">{t.date}</td>
                <td className="mono text-xs">{t.code}</td>
                <td>
                  <span
                    className={`pill ${t.action === 'buy' ? 'up' : 'down'}`}
                    style={{ fontSize: 10 }}
                  >
                    {t.action === 'buy' ? '买' : '卖'}
                  </span>
                </td>
                <td className="num mono text-xs">{t.shares.toLocaleString()}</td>
                <td className="num mono text-xs">¥{t.price.toFixed(2)}</td>
                <td className="num mono text-xs">¥{t.fee.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 构建确认通过**

Run: `cd frontend && npm run build`
Expected: 构建成功。

- [ ] **Step 3: commit**

```bash
git add frontend/src/components/TradesTable.tsx
git commit -m "feat(p3a): TradesTable with filter + sort"
```

---

### Task 10: ThinkingDrawer 组件

**Files:**
- Create: `frontend/src/components/ThinkingDrawer.tsx`

- [ ] **Step 1: 实现 ThinkingDrawer**

Create `frontend/src/components/ThinkingDrawer.tsx`:

```typescript
import { useState } from 'react';
import type { ThinkingEntry } from '../api/types';

export function ThinkingDrawer({ thinking }: { thinking: ThinkingEntry[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (thinking.length === 0) {
    return (
      <div className="text-text-faint text-sm italic">
        本次回测没有 LLM 决策日志。
      </div>
    );
  }

  return (
    <div className="grid gap-2">
      {thinking.map((entry) => {
        const isOpen = expanded === entry.date;
        const hasContent =
          entry.reasoning || entry.tool_calls.length > 0 || entry.decisions.length > 0;
        return (
          <div
            key={entry.date}
            style={{
              background: 'var(--bg-3)',
              border: '1px solid var(--panel-border-soft)',
              borderRadius: 4,
              overflow: 'hidden',
            }}
          >
            <button
              onClick={() => setExpanded(isOpen ? null : entry.date)}
              className="w-full text-left px-3 py-2 flex items-center gap-2"
              style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
            >
              <span className="mono text-xs text-text-hi">{entry.date}</span>
              <span className="text-text-faint text-xs">
                {entry.decisions.length} 决策 · {entry.tool_calls.length} 工具
              </span>
              <span style={{ flex: 1 }} />
              <span className="text-text-faint text-xs">{isOpen ? '▲' : '▼'}</span>
            </button>
            {isOpen && hasContent && (
              <div className="px-3 py-2" style={{ borderTop: '1px solid var(--panel-border-soft)' }}>
                {entry.reasoning && (
                  <div className="mb-3">
                    <div className="text-[10px] text-text-ghost uppercase tracking-wider mb-1">
                      Reasoning
                    </div>
                    <div
                      className="text-xs text-text"
                      style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}
                    >
                      {entry.reasoning}
                    </div>
                  </div>
                )}
                {entry.tool_calls.length > 0 && (
                  <div className="mb-3">
                    <div className="text-[10px] text-text-ghost uppercase tracking-wider mb-1">
                      Tool Calls
                    </div>
                    <div className="grid gap-1">
                      {entry.tool_calls.map((tc, i) => (
                        <div
                          key={i}
                          className="mono text-[11px]"
                          style={{
                            padding: '4px 8px',
                            background: 'var(--bg-2)',
                            borderRadius: 3,
                          }}
                        >
                          <span className="text-brand">{tc.name}</span>
                          <span className="text-text-faint">
                            ({JSON.stringify(tc.input)})
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {entry.decisions.length > 0 && (
                  <div>
                    <div className="text-[10px] text-text-ghost uppercase tracking-wider mb-1">
                      Decisions
                    </div>
                    <div className="grid gap-1">
                      {entry.decisions.map((d, i) => (
                        <div
                          key={i}
                          className="text-xs flex items-center gap-2"
                          style={{
                            padding: '4px 8px',
                            background: 'var(--bg-2)',
                            borderRadius: 3,
                          }}
                        >
                          <span
                            className={`pill ${d.action === 'buy' ? 'up' : d.action === 'sell' ? 'down' : ''}`}
                            style={{ fontSize: 9 }}
                          >
                            {d.action}
                          </span>
                          {d.code && <span className="mono">{d.code}</span>}
                          {d.shares != null && <span className="num mono">{d.shares}股</span>}
                          {d.price != null && <span className="num mono">¥{d.price.toFixed(2)}</span>}
                          {d.outcome && (
                            <span
                              className="pill"
                              style={{
                                fontSize: 9,
                                background: d.outcome === 'rejected' ? 'var(--down-bg)' : 'var(--bg-2)',
                                color: d.outcome === 'rejected' ? 'var(--down)' : 'var(--text-faint)',
                              }}
                            >
                              {d.outcome}
                            </span>
                          )}
                          {d.reasoning && (
                            <span className="text-text-faint italic">{d.reasoning}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: 构建确认通过**

Run: `cd frontend && npm run build`
Expected: 构建成功。

- [ ] **Step 3: commit**

```bash
git add frontend/src/components/ThinkingDrawer.tsx
git commit -m "feat(p3a): ThinkingDrawer per-day collapsible reasoning"
```

---

### Task 11: QualityGatePanel + StrategyRatingPanel

**Files:**
- Create: `frontend/src/components/QualityGatePanel.tsx`
- Create: `frontend/src/components/StrategyRatingPanel.tsx`

- [ ] **Step 1: QualityGatePanel**

Create `frontend/src/components/QualityGatePanel.tsx`:

```typescript
import type { BacktestResult } from '../api/types';

type Criterion = {
  key: string;
  label: string;
  value: number | string | boolean;
  passed: boolean;
  threshold?: string;
};

function buildCriteria(r: BacktestResult): Criterion[] {
  const c = r.quality_gate_criteria as Record<string, { passed: boolean; value: unknown; threshold?: string }>;
  return Object.entries(c).map(([k, v]) => ({
    key: k,
    label: k.replace(/_/g, ' '),
    value: v.value as number | string | boolean,
    passed: v.passed,
    threshold: v.threshold,
  }));
}

export function QualityGatePanel({ result }: { result: BacktestResult | undefined }) {
  if (!result) return null;
  const items = buildCriteria(result);
  if (items.length === 0) return null;

  const passCount = items.filter((i) => i.passed).length;

  return (
    <div className="panel p-5">
      <div className="flex items-baseline gap-2 mb-3 flex-wrap">
        <h2 className="text-text-hi text-base font-semibold">质量门</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          Quality Gate
        </span>
        <span style={{ flex: 1 }} />
        <span
          className={`pill ${result.quality_gate_label === 'pass' ? 'brand' : result.quality_gate_label === 'warn' ? '' : 'down'}`}
        >
          {result.quality_gate_label === 'pass' ? '达标' : result.quality_gate_label === 'warn' ? '观察' : '不通过'}
          {' · '}
          {passCount}/{items.length}
        </span>
      </div>
      <div className="grid gap-2">
        {items.map((c) => (
          <div
            key={c.key}
            className="flex items-center gap-2"
            style={{
              padding: '6px 10px',
              background: 'var(--bg-3)',
              border: `1px solid ${c.passed ? 'var(--brand)' : 'var(--down-border)'}`,
              borderRadius: 4,
            }}
          >
            <span
              style={{
                width: 18,
                height: 18,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 999,
                background: c.passed ? 'var(--brand)' : 'var(--down)',
                color: 'var(--bg)',
                fontSize: 11,
                fontWeight: 'bold',
              }}
            >
              {c.passed ? '✓' : '✗'}
            </span>
            <span className="text-xs text-text-hi capitalize">{c.label}</span>
            <span style={{ flex: 1 }} />
            <span className="mono text-xs text-text-faint">
              {String(c.value)}
              {c.threshold ? ` / ${c.threshold}` : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: StrategyRatingPanel**

Create `frontend/src/components/StrategyRatingPanel.tsx`:

```typescript
import type { StrategyRating } from '../api/types';

const SUB_ROWS: Array<{ key: keyof Pick<StrategyRating, 'returns' | 'sharpe' | 'drawdown' | 'win_rate' | 'consistency'>; label: string; weight: number }> = [
  { key: 'returns', label: '收益 Returns', weight: 30 },
  { key: 'sharpe', label: '风险调整 Sharpe', weight: 30 },
  { key: 'drawdown', label: '最大回撤 Drawdown', weight: 15 },
  { key: 'win_rate', label: '胜率 Win Rate', weight: 15 },
  { key: 'consistency', label: '一致性 Consistency', weight: 10 },
];

function letterColor(letter: StrategyRating['letter']) {
  switch (letter) {
    case 'A+':
    case 'A':
      return 'var(--brand)';
    case 'B':
      return 'var(--text-hi)';
    case 'C':
      return 'var(--warn)';
    case 'D':
    default:
      return 'var(--down)';
  }
}

export function StrategyRatingPanel({ rating }: { rating: StrategyRating | undefined }) {
  if (!rating) {
    return (
      <div className="panel p-5">
        <div className="text-text-faint text-sm">评级加载中…</div>
      </div>
    );
  }

  return (
    <div className="panel p-5">
      <div className="flex items-baseline gap-2 mb-3 flex-wrap">
        <h2 className="text-text-hi text-base font-semibold">策略评级</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          Strategy Rating
        </span>
        <span style={{ flex: 1 }} />
        <span
          className="text-3xl font-bold"
          style={{ color: letterColor(rating.letter) }}
        >
          {rating.letter}
        </span>
        <span className="mono text-xs text-text-faint">
          {rating.overall.toFixed(1)} / 100
        </span>
      </div>

      <div className="grid gap-2 mb-3">
        {SUB_ROWS.map((row) => {
          const v = rating[row.key] as number;
          const pct = Math.max(0, Math.min(100, v));
          return (
            <div key={row.key}>
              <div className="flex items-baseline justify-between text-xs mb-0.5">
                <span className="text-text">
                  {row.label}
                  <span className="text-text-faint ml-1">({row.weight}%)</span>
                </span>
                <span className="mono text-text-hi">{v.toFixed(1)}</span>
              </div>
              <div
                style={{
                  height: 4,
                  background: 'var(--bg-2)',
                  borderRadius: 2,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: `${pct}%`,
                    height: '100%',
                    background: 'var(--brand)',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {rating.notes.length > 0 && (
        <div className="text-text-faint text-[11px]" style={{ lineHeight: 1.5 }}>
          <div className="text-[10px] uppercase tracking-wider mb-1">Notes</div>
          {rating.notes.map((n, i) => (
            <div key={i}>· {n}</div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 构建确认通过**

Run: `cd frontend && npm run build`
Expected: 构建成功。

- [ ] **Step 4: commit**

```bash
git add frontend/src/components/QualityGatePanel.tsx frontend/src/components/StrategyRatingPanel.tsx
git commit -m "feat(p3a): QualityGatePanel + StrategyRatingPanel"
```

---

### Task 12: BacktestLab 集成新组件

**Files:**
- Modify: `frontend/src/pages/BacktestLab.tsx`

- [ ] **Step 1: 拆出 ResultDetail 子组件容纳 5 个新面板**

Edit `frontend/src/pages/BacktestLab.tsx`. In the imports area, add:

```typescript
import { NavChart } from '../components/NavChart';
import { TradesTable } from '../components/TradesTable';
import { ThinkingDrawer } from '../components/ThinkingDrawer';
import { QualityGatePanel } from '../components/QualityGatePanel';
import { StrategyRatingPanel } from '../components/StrategyRatingPanel';
import {
  useBacktestNav,
  useBacktestTrades,
  useBacktestThinking,
  useBacktestRating,
  // ... existing hook imports
} from '../api/hooks';
```

Add new subcomponent before `BacktestLab`:

```typescript
function ResultDetailPanels({ result }: { result: BacktestResult }) {
  const nav = useBacktestNav(result.id);
  const trades = useBacktestTrades(result.id);
  const thinking = useBacktestThinking(result.id);
  const rating = useBacktestRating(result.id);

  return (
    <div className="grid gap-4 mt-4">
      {/* NAV 曲线 */}
      <div className="panel p-5">
        <div className="flex items-baseline gap-2 mb-3 flex-wrap">
          <h2 className="text-text-hi text-base font-semibold">权益曲线</h2>
          <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
            NAV Curve
          </span>
        </div>
        <NavChart data={nav.data} />
      </div>

      {/* 两栏：左评级 + 质量门 / 右 Thinking */}
      <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <div className="grid gap-4">
          <StrategyRatingPanel rating={rating.data} />
          <QualityGatePanel result={result} />
        </div>
        <div className="panel p-5">
          <div className="flex items-baseline gap-2 mb-3 flex-wrap">
            <h2 className="text-text-hi text-base font-semibold">决策日志</h2>
            <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
              LLM Thinking
            </span>
          </div>
          <ThinkingDrawer thinking={thinking.data?.thinking ?? []} />
        </div>
      </div>

      {/* 成交流水 */}
      <div className="panel p-5">
        <div className="flex items-baseline gap-2 mb-3 flex-wrap">
          <h2 className="text-text-hi text-base font-semibold">成交流水</h2>
          <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
            Trade Log
          </span>
        </div>
        <TradesTable trades={trades.data?.trades ?? []} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 挂 ResultDetailPanels 到 JobPanel.complete 分支**

Find the block:

```typescript
      {job?.state === 'complete' && session && (
        <>
          <ResultsTable session={session} />
          <ZoneMetricsPanel session={session} />
        </>
      )}
```

Replace with:

```typescript
      {job?.state === 'complete' && session && (
        <>
          <ResultsTable session={session} />
          <ZoneMetricsPanel session={session} />
          {session.agents.map((a) => (
            <ResultDetailPanels key={a.id} result={a} />
          ))}
        </>
      )}
```

- [ ] **Step 3: 构建确认通过**

Run: `cd frontend && npm run build`
Expected: 构建成功，无 TS 错误。

- [ ] **Step 4: 启 dev server 手动验收**

```bash
# 窗口1：跑 Flask
python app.py

# 窗口2：跑前端
cd frontend && npm run dev
```

打开 http://localhost:5173/backtest，跑一次回测（选 linyuan persona / MockLLM / 3 只票 / 2025-11-17～2025-11-28）。
完成后确认：
- NAV 曲线有 agent + baselines 4 条
- 策略评级显示字母 + 5 子分数条
- 质量门 7 个 criterion 显示 ✓/✗
- 决策日志可展开，显示 reasoning / tool_calls / decisions
- 成交流水表支持过滤 + 排序

若任何一项失败，修复到通过。

- [ ] **Step 5: commit**

```bash
git add frontend/src/pages/BacktestLab.tsx
git commit -m "feat(p3a): BacktestLab renders NAV/Trades/Thinking/Rating/QG panels"
```

---

### Task 13: 端到端 smoke + status-and-roadmap 更新

**Files:**
- Modify: `docs/superpowers/plans/2026-04-23-status-and-roadmap.md`

- [ ] **Step 1: 跑全量测试**

Run: `python -m pytest -q`
Expected: 全部通过（原 429 + P3-A 新增 ~9 = ~438 passed）。

- [ ] **Step 2: 前端构建 + lint**

```bash
cd frontend
npm run build
npm run lint
```

Expected: 均通过。

- [ ] **Step 3: 更新 status-and-roadmap 标记 P3-A done**

Edit `docs/superpowers/plans/2026-04-23-status-and-roadmap.md`. Find the P3-A section (around line 175) and prepend `✅ Done 2026-04-23` to the heading:

```
### ✅ Done 2026-04-23 · P3-A：回测可观察性（最迫切，~3 天）
```

Also at section 7 (历史 plan 档案), add:

```
- `2026-04-23-p3a-backtest-observability.md` ✅ Done
```

- [ ] **Step 4: Final commit**

```bash
git add docs/superpowers/plans/2026-04-23-status-and-roadmap.md
git commit -m "docs(p3a): mark observability done + link plan"
```

---

## Self-Review

**Spec coverage check:**
- spec §15.4 `GET /backtest/:id/nav` → Task 5 ✅
- spec §15.4 `GET /backtest/:id/trades` → Task 5 ✅
- spec §15.4 `GET /backtest/:id/thinking` → Task 5 ✅
- spec §16 Backtest equity chart 4 curves → Task 8 ✅
- spec §16 Trade log → Task 9 ✅
- spec §16 Strategy rating A+/A/B/C 5 子分数 → Task 11 ✅
- spec §16 Quality gate panel → Task 11 ✅

**Missing from spec §15.4:**
- `POST /backtest/:id/cancel` — 不在 P3-A 范围（用户中断是 P3-D 细粒度 SSE 顺带做）
- `GET /backtest/:id/stream` 的 phase/progress/tool_call/decision/blocked/baseline_done events — P3-D

**Type consistency:**
- `BacktestResult.daily_records` (list[dict]) — 后端 dataclass + 前端 `NavResponse.agent` (NavPoint[])
- `TradeRow` shape — 后端 dict from book.fills + 前端 type 匹配
- `ThinkingEntry` shape — backend `{date, reasoning, tool_calls, decisions}` + frontend type

**Placeholder scan:** 无 TODO/TBD 残留；每步均有完整代码块。

---

## Execution Handoff

按 subagent-driven-development 一个任务一个 subagent。控制台协调每任务收口后的 spec-reviewer + code-quality-reviewer。

Backend tasks (1-6) 可串行。Frontend tasks (7-11) 可部分并行（组件相互独立），但 Task 12（集成）依赖全部组件。Task 13 最后。

单任务预估：
- Task 1: 20 min
- Task 2: 30 min
- Task 3: 40 min（AgentRunner 变更需要小心）
- Task 4: 30 min
- Task 5: 40 min
- Task 6: 60 min（可选）
- Task 7: 15 min
- Task 8: 30 min
- Task 9: 30 min
- Task 10: 40 min
- Task 11: 40 min
- Task 12: 40 min
- Task 13: 15 min

总计：~7 小时单人工时 + subagent 开销 ≈ 1.5 天。
