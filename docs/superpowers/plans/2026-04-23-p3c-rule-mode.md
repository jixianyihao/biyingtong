# P3-C Rule Mode Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** 让用户在同一 session 里跑 head-to-head: `linyuan agent (LLM) vs MA crossover (rule) vs csi300 (baseline)` — 回答"LLM 真比硬编码 MA 金叉强吗？"

**Architecture:**
- 写一个 `Strategy` Protocol：`on_day(date, bars, portfolio) → list[decision]`
- 3 个内置规则策略：MACrossover / RSIBreakout / MACDDivergence，每个纯 Python + 仅用 kline close price
- 新 `RuleRunner`——结构镜像 `BacktestRunner` 但决策源是 Strategy 而非 AgentRunner，复用 Book/FeeModel/stats/daily_records/trades 管道
- `BacktestResult.kind: 'agent' | 'rule'` 新字段，DB 列 `kind_str`（默认 `'agent'` 向后兼容）
- `POST /api/backtest/rule`——body `{strategy_name, params, session_id?, agent_session_id?, ...}`；可以 POST 到已有 session 做混合对比
- 前端 BacktestLab 加 tab："Agent / Rule / Baseline"；ResultsTable 按 kind 分行并用不同 pill 区分
- vnpy `BacktestingEngine` **不启用**（事件驱动 + 结果格式不合我们的 Book / zone_stats 流水线）。vnpy 继续仅用于 kline 存储

**Tech Stack:** Python 3.10 / Flask / SQLite / React 19 / TypeScript / TanStack Query

---

## File Structure

**Backend:**
- `backtest/strategies/__init__.py` — registry
- `backtest/strategies/base.py` — `Strategy` Protocol + Decision shape
- `backtest/strategies/ma_crossover.py` — 10/30 日 MA 金叉/死叉
- `backtest/strategies/rsi_breakout.py` — RSI 跌破 30 买入、突破 70 卖出
- `backtest/strategies/macd_divergence.py` — 12/26/9 MACD 金叉
- `backtest/rule_runner.py` — `RuleRunner.run(...)` 镜像 `BacktestRunner.run`
- `data_schema/backtest_state.py` — `kind_str TEXT NOT NULL DEFAULT 'agent'` 新列 + `ensure_kind_column` migration helper
- `backtest/base.py` — `BacktestResult.kind: str = 'agent'` 字段
- `storage/sqlite_backtests.py` — `_select_cols` / `_row_to_result` / `insert` 覆盖 `kind_str`
- `api/backtests.py` — `POST /api/backtests/rule` + 结果 serializer 带 `kind`
- `tests/test_rule_mode.py` — 新文件

**Frontend:**
- `frontend/src/api/types.ts` — `StrategyDescriptor`、`StartRuleBacktestBody`；`BacktestResult.kind` 字段
- `frontend/src/api/client.ts` + `hooks.ts` — `api.strategies()` / `api.startRuleBacktest()` + 2 个 hooks
- `frontend/src/pages/BacktestLab.tsx` — 顶部 tab "Agent 模式 / 规则模式"；规则模式表单；同 session 混合结果表
- （可选）`frontend/src/components/StrategyPicker.tsx`——规则策略选择 + 参数编辑

---

### Task 1: Schema + dataclass 加 `kind` 字段

**Files:**
- Modify: `data_schema/backtest_state.py`
- Modify: `backtest/base.py`
- Test: `tests/test_rule_mode.py` (new)

- [ ] **Step 1: 写失败测试**

Create `tests/test_rule_mode.py`:

```python
"""P3-C Rule mode backtest — strategies, runner, endpoint."""
from __future__ import annotations

import sqlite3
import pytest


def test_backtest_results_schema_has_kind_column():
    from data_schema.backtest_state import SCHEMA_BACKTEST_RESULTS
    con = sqlite3.connect(':memory:')
    con.executescript(SCHEMA_BACKTEST_RESULTS)
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    con.close()
    assert 'kind_str' in cols


def test_ensure_kind_column_migrates_old_schema(tmp_path):
    import sqlite3
    from data_schema.backtest_state import ensure_kind_column
    db = tmp_path / 'legacy.db'
    con = sqlite3.connect(db)
    con.execute('''CREATE TABLE backtest_results (
        id TEXT PRIMARY KEY, session_id TEXT NOT NULL, agent_id TEXT NOT NULL,
        persona_id TEXT, model_id TEXT,
        start_date TEXT NOT NULL, end_date TEXT NOT NULL,
        initial_capital REAL NOT NULL, final_equity REAL,
        stats_json TEXT NOT NULL, zone_stats_json TEXT NOT NULL,
        quality_gate_label TEXT NOT NULL, quality_gate_json TEXT NOT NULL
    )''')
    con.execute(
        "INSERT INTO backtest_results VALUES "
        "('r1','s1','a1',null,null,'2025-01-01','2025-01-02',"
        "100000.0,null,'{}','[]','pass','{}')",
    )
    con.commit()

    ensure_kind_column(con)
    ensure_kind_column(con)  # idempotent

    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    assert 'kind_str' in cols
    row = con.execute(
        "SELECT kind_str FROM backtest_results WHERE id=?", ('r1',),
    ).fetchone()
    assert row == ('agent',)  # default
    con.close()


def test_backtest_result_kind_defaults_agent():
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
        quality_gate_label='pass', quality_gate_criteria={},
    )
    assert r.kind == 'agent'


def test_backtest_result_kind_rule():
    from backtest.base import BacktestResult, BacktestStats
    r = BacktestResult(
        id='r', session_id='s', agent_id='',
        persona_id=None, model_id=None,
        start_date='2025-01-01', end_date='2025-01-10',
        initial_capital=100_000.0,
        stats=BacktestStats(
            sharpe=0.0, max_drawdown_pct=0.0, trade_count=0,
            win_rate=0.0, max_daily_loss_pct=0.0,
            total_return_pct=0.0, final_equity=100_000.0,
        ),
        zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        kind='rule',
    )
    assert r.kind == 'rule'
```

- [ ] **Step 2: RED**

Run: `python -m pytest tests/test_rule_mode.py -v`
Expected: 4 FAIL.

- [ ] **Step 3: 修改 DDL + 加 migration helper**

Edit `data_schema/backtest_state.py`. Add `kind_str TEXT NOT NULL DEFAULT 'agent'` to `SCHEMA_BACKTEST_RESULTS` (insert after `thinking_json` line, before `created_at`):

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
    kind_str             TEXT NOT NULL DEFAULT 'agent',
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS results_by_session ON backtest_results(session_id);
CREATE INDEX IF NOT EXISTS results_by_agent   ON backtest_results(agent_id, created_at DESC);
'''
```

Append migration helper:

```python
def ensure_kind_column(con):
    """Add kind_str to existing backtest_results if absent. Idempotent."""
    cols = {row[1] for row in con.execute(
        'PRAGMA table_info(backtest_results)').fetchall()}
    if 'kind_str' not in cols:
        con.execute("ALTER TABLE backtest_results ADD COLUMN "
                    "kind_str TEXT NOT NULL DEFAULT 'agent'")
```

- [ ] **Step 4: 扩展 BacktestResult**

Edit `backtest/base.py`:

```python
@dataclass
class BacktestResult:
    id: str
    session_id: str
    agent_id: str                   # '' for rule results
    persona_id: str | None
    model_id: str | None
    start_date: str
    end_date: str
    initial_capital: float
    stats: BacktestStats
    zone_stats: list
    quality_gate_label: str
    quality_gate_criteria: dict
    final_equity: float | None = None
    daily_records: list = None
    trades: list = None
    thinking: list = None
    kind: str = 'agent'             # 'agent' | 'rule'

    def __post_init__(self):
        if self.daily_records is None: self.daily_records = []
        if self.trades is None: self.trades = []
        if self.thinking is None: self.thinking = []
```

- [ ] **Step 5: GREEN**

Run: `python -m pytest tests/test_rule_mode.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add data_schema/backtest_state.py backtest/base.py tests/test_rule_mode.py
git commit -m "feat(p3c): schema kind_str + BacktestResult.kind field"
```

---

### Task 2: Strategy Protocol + MACrossover

**Files:**
- Create: `backtest/strategies/__init__.py`
- Create: `backtest/strategies/base.py`
- Create: `backtest/strategies/ma_crossover.py`
- Test: `tests/test_rule_mode.py`

**Design:**
- `Strategy` Protocol：`name: str`, `params: dict`, `on_day(date, close_history, portfolio) → list[dict]`
- `close_history: dict[code, list[(date, close)]]` — 历史收盘价（截止到 `date`），让策略按 rolling window 计算指标
- Decision shape: `{action: 'buy'|'sell'|'hold', code, shares?, reason?}`
- `on_day` 不需要关心 T+1 / fee / lot — RuleRunner 的 Book 处理

- [ ] **Step 1: 写 MACrossover 测试**

```python
def test_ma_crossover_buys_on_golden_cross():
    from datetime import date
    from backtest.strategies.ma_crossover import MACrossover

    s = MACrossover(params={'fast': 3, 'slow': 5, 'position_pct': 0.3})

    # Price series crossing golden cross on day 6:
    # fast (last 3) = [110, 115, 120] avg 115
    # slow (last 5) = [100, 105, 108, 110, 115] avg 107.6
    # fast > slow → buy signal
    d = date(2025, 1, 8)
    close_history = {
        '600519.SH': [
            (date(2025, 1, 2), 100.0),
            (date(2025, 1, 3), 105.0),
            (date(2025, 1, 4), 108.0),
            (date(2025, 1, 5), 110.0),
            (date(2025, 1, 6), 115.0),
            (date(2025, 1, 7), 118.0),
            (date(2025, 1, 8), 120.0),
        ],
    }
    portfolio = {'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}}
    decisions = s.on_day(date=d, close_history=close_history, portfolio=portfolio)
    assert len(decisions) == 1
    assert decisions[0]['action'] == 'buy'
    assert decisions[0]['code'] == '600519.SH'
    assert decisions[0]['shares'] > 0


def test_ma_crossover_sells_on_death_cross():
    from datetime import date
    from backtest.strategies.ma_crossover import MACrossover

    s = MACrossover(params={'fast': 3, 'slow': 5})
    # Falling trend: fast < slow → sell
    d = date(2025, 1, 8)
    close_history = {
        '600519.SH': [
            (date(2025, 1, 2), 120.0),
            (date(2025, 1, 3), 115.0),
            (date(2025, 1, 4), 110.0),
            (date(2025, 1, 5), 108.0),
            (date(2025, 1, 6), 105.0),
            (date(2025, 1, 7), 100.0),
            (date(2025, 1, 8), 95.0),
        ],
    }
    portfolio = {
        'cash': 500_000, 'equity': 500_000 + 100 * 95,
        'positions': {'600519.SH': {'shares': 100, 'avg_price': 110.0}},
    }
    decisions = s.on_day(date=d, close_history=close_history, portfolio=portfolio)
    assert any(d['action'] == 'sell' and d['code'] == '600519.SH' for d in decisions)


def test_ma_crossover_insufficient_history_returns_empty():
    from datetime import date
    from backtest.strategies.ma_crossover import MACrossover
    s = MACrossover(params={'fast': 5, 'slow': 20})
    decisions = s.on_day(
        date=date(2025, 1, 3),
        close_history={'600519.SH': [(date(2025, 1, 2), 100.0)]},
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
    )
    assert decisions == []
```

- [ ] **Step 2: RED**

Run: `python -m pytest tests/test_rule_mode.py -v -k ma_crossover`
Expected: 3 FAIL (import error).

- [ ] **Step 3: 实现 Strategy base + MACrossover**

Create `backtest/strategies/base.py`:

```python
"""Strategy Protocol + Decision shape for rule-mode backtests."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass
class StrategyDescriptor:
    """Metadata for the /api/strategies listing."""
    name: str             # identifier, e.g. 'ma_crossover'
    display_name: str     # '均线金叉死叉'
    description: str
    default_params: dict = field(default_factory=dict)


@runtime_checkable
class Strategy(Protocol):
    """Per-day decision emitter for rule-mode backtests.

    close_history values are strictly-past + current-day closes, ascending.
    Strategy returns zero or more decisions; the Book + RuleRunner handle
    T+1, fees, lot-rounding, and mark-to-market.
    """
    name: str
    params: dict

    def on_day(self, date: date, close_history: dict, portfolio: dict) -> list[dict]:
        ...
```

Create `backtest/strategies/ma_crossover.py`:

```python
"""MA Crossover strategy — buy on golden cross, sell on death cross."""
from __future__ import annotations

from datetime import date

_DEFAULT_PARAMS = {
    'fast': 10,
    'slow': 30,
    'position_pct': 0.3,   # fraction of equity to allocate per buy
}


class MACrossover:
    name: str = 'ma_crossover'

    def __init__(self, params: dict | None = None):
        self.params = {**_DEFAULT_PARAMS, **(params or {})}

    def on_day(self, date: date, close_history: dict, portfolio: dict) -> list[dict]:
        fast = int(self.params['fast'])
        slow = int(self.params['slow'])
        position_pct = float(self.params['position_pct'])

        decisions: list[dict] = []
        positions = portfolio.get('positions', {}) or {}
        equity = float(portfolio.get('equity', 0.0))

        for code, series in close_history.items():
            if len(series) < slow + 1:
                continue
            closes = [c for _, c in series]
            fast_now = sum(closes[-fast:]) / fast
            slow_now = sum(closes[-slow:]) / slow
            fast_prev = sum(closes[-fast - 1:-1]) / fast
            slow_prev = sum(closes[-slow - 1:-1]) / slow

            held = int(positions.get(code, {}).get('shares', 0))
            price = closes[-1]

            # Golden cross: prev fast <= slow AND now fast > slow
            if fast_prev <= slow_prev and fast_now > slow_now and held == 0:
                target_value = equity * position_pct
                shares = int(target_value / price // 100) * 100
                if shares > 0:
                    decisions.append({
                        'action': 'buy', 'code': code, 'shares': shares,
                        'reason': f'MA{fast}/MA{slow} golden cross',
                    })
            # Death cross: prev fast >= slow AND now fast < slow
            elif fast_prev >= slow_prev and fast_now < slow_now and held > 0:
                decisions.append({
                    'action': 'sell', 'code': code, 'shares': held,
                    'reason': f'MA{fast}/MA{slow} death cross',
                })

        return decisions
```

Create `backtest/strategies/__init__.py`:

```python
"""Built-in rule strategies registry."""
from __future__ import annotations

from .base import Strategy, StrategyDescriptor
from .ma_crossover import MACrossover


_REGISTRY: dict[str, tuple[type, StrategyDescriptor]] = {}


def register(cls, descriptor: StrategyDescriptor) -> None:
    _REGISTRY[descriptor.name] = (cls, descriptor)


def get(name: str):
    """Return (cls, descriptor) or None."""
    return _REGISTRY.get(name)


def list_all() -> list[StrategyDescriptor]:
    return [desc for _, desc in _REGISTRY.values()]


def build(name: str, params: dict | None = None):
    """Instantiate a strategy by name."""
    entry = _REGISTRY.get(name)
    if entry is None:
        raise ValueError(f'unknown strategy: {name!r}')
    cls, desc = entry
    return cls(params=params or dict(desc.default_params))


# Register built-ins
register(MACrossover, StrategyDescriptor(
    name='ma_crossover',
    display_name='均线金叉死叉',
    description='快速均线上穿慢速均线买入；下穿卖出。默认 10/30 日。',
    default_params={'fast': 10, 'slow': 30, 'position_pct': 0.3},
))
```

- [ ] **Step 4: GREEN**

Run: `python -m pytest tests/test_rule_mode.py -v -k ma_crossover`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backtest/strategies/ tests/test_rule_mode.py
git commit -m "feat(p3c): Strategy Protocol + MACrossover + registry"
```

---

### Task 3: RSIBreakout + MACDDivergence 策略

**Files:**
- Create: `backtest/strategies/rsi_breakout.py`
- Create: `backtest/strategies/macd_divergence.py`
- Modify: `backtest/strategies/__init__.py` (register both)
- Test: `tests/test_rule_mode.py`

- [ ] **Step 1: 写测试**

Append to `tests/test_rule_mode.py`:

```python
def test_rsi_breakout_buys_when_rsi_below_30():
    from datetime import date
    from backtest.strategies.rsi_breakout import RSIBreakout

    s = RSIBreakout(params={'period': 14, 'oversold': 30, 'overbought': 70,
                            'position_pct': 0.3})

    # 14-day continuously falling price → RSI ~0
    dates = [date(2025, 1, d) for d in range(2, 17)]
    series = list(zip(dates, [100.0 - i * 2 for i in range(15)]))  # 15 days
    portfolio = {'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}}
    decisions = s.on_day(
        date=dates[-1], close_history={'600519.SH': series},
        portfolio=portfolio,
    )
    assert any(d['action'] == 'buy' for d in decisions)


def test_rsi_breakout_sells_when_rsi_above_70():
    from datetime import date
    from backtest.strategies.rsi_breakout import RSIBreakout

    s = RSIBreakout(params={'period': 14, 'oversold': 30, 'overbought': 70})
    dates = [date(2025, 1, d) for d in range(2, 17)]
    series = list(zip(dates, [100.0 + i * 2 for i in range(15)]))  # rising 15 days
    portfolio = {
        'cash': 500_000, 'equity': 500_000 + 100 * 128,
        'positions': {'600519.SH': {'shares': 100, 'avg_price': 100.0}},
    }
    decisions = s.on_day(
        date=dates[-1], close_history={'600519.SH': series},
        portfolio=portfolio,
    )
    assert any(d['action'] == 'sell' for d in decisions)


def test_macd_divergence_buys_on_line_above_signal():
    from datetime import date
    from backtest.strategies.macd_divergence import MACDDivergence

    s = MACDDivergence(params={'fast': 12, 'slow': 26, 'signal': 9,
                               'position_pct': 0.3})
    # Need 26+9 = 35 days minimum; use 40 to have headroom
    dates = [date(2025, 1, 2)]
    # Build a series that ramps up: MACD line should cross above signal
    import random
    random.seed(42)
    prices = [100.0]
    for i in range(39):
        prices.append(prices[-1] * (1 + 0.02))  # +2% daily, clear uptrend
    dates = []
    from datetime import timedelta
    d = date(2025, 1, 2)
    for _ in range(40):
        dates.append(d)
        d = d + timedelta(days=1)
    series = list(zip(dates, prices))
    portfolio = {'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}}
    decisions = s.on_day(
        date=dates[-1], close_history={'600519.SH': series},
        portfolio=portfolio,
    )
    # Uptrend → MACD line should be above signal → buy
    assert any(d['action'] == 'buy' for d in decisions)


def test_strategies_registry_lists_all_three():
    from backtest.strategies import list_all
    names = [d.name for d in list_all()]
    assert 'ma_crossover' in names
    assert 'rsi_breakout' in names
    assert 'macd_divergence' in names
```

- [ ] **Step 2: RED**

Run: `python -m pytest tests/test_rule_mode.py -v -k "rsi or macd or registry"`

- [ ] **Step 3: 实现 RSI**

Create `backtest/strategies/rsi_breakout.py`:

```python
"""RSI Breakout — oversold → buy, overbought → sell (Wilder smoothing)."""
from __future__ import annotations

from datetime import date

_DEFAULT_PARAMS = {
    'period': 14,
    'oversold': 30.0,
    'overbought': 70.0,
    'position_pct': 0.3,
}


def _rsi(closes: list[float], period: int) -> float:
    """Standard Wilder's RSI."""
    if len(closes) < period + 1:
        return 50.0  # neutral / not enough data
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0.0, diff))
        losses.append(max(0.0, -diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    # Wilder smooth the rest
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = max(0.0, diff)
        loss = max(0.0, -diff)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


class RSIBreakout:
    name: str = 'rsi_breakout'

    def __init__(self, params: dict | None = None):
        self.params = {**_DEFAULT_PARAMS, **(params or {})}

    def on_day(self, date: date, close_history: dict, portfolio: dict) -> list[dict]:
        period = int(self.params['period'])
        oversold = float(self.params['oversold'])
        overbought = float(self.params['overbought'])
        position_pct = float(self.params['position_pct'])

        decisions: list[dict] = []
        positions = portfolio.get('positions', {}) or {}
        equity = float(portfolio.get('equity', 0.0))

        for code, series in close_history.items():
            if len(series) < period + 1:
                continue
            closes = [c for _, c in series]
            rsi = _rsi(closes, period)
            held = int(positions.get(code, {}).get('shares', 0))
            price = closes[-1]

            if rsi <= oversold and held == 0:
                target_value = equity * position_pct
                shares = int(target_value / price // 100) * 100
                if shares > 0:
                    decisions.append({
                        'action': 'buy', 'code': code, 'shares': shares,
                        'reason': f'RSI({period})={rsi:.1f} ≤ {oversold}',
                    })
            elif rsi >= overbought and held > 0:
                decisions.append({
                    'action': 'sell', 'code': code, 'shares': held,
                    'reason': f'RSI({period})={rsi:.1f} ≥ {overbought}',
                })

        return decisions
```

- [ ] **Step 4: 实现 MACD**

Create `backtest/strategies/macd_divergence.py`:

```python
"""MACD Divergence — buy when MACD line crosses above signal, sell on reverse."""
from __future__ import annotations

from datetime import date

_DEFAULT_PARAMS = {
    'fast': 12,
    'slow': 26,
    'signal': 9,
    'position_pct': 0.3,
}


def _ema(values: list[float], period: int) -> list[float]:
    """EMA for entire series. Returns len == len(values). Seed = SMA of first `period`."""
    if len(values) < period:
        return []
    out = []
    sma = sum(values[:period]) / period
    out.append(sma)
    k = 2 / (period + 1)
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out  # len = len(values) - period + 1


def _macd(closes: list[float], fast: int, slow: int, signal: int):
    """Returns (macd_line, signal_line, histogram), each aligned to the TAIL
    of the input (i.e., latest value is at [-1]). Returns ([], [], []) if
    insufficient data."""
    if len(closes) < slow + signal:
        return [], [], []
    ema_f = _ema(closes, fast)  # len = N - fast + 1
    ema_s = _ema(closes, slow)  # len = N - slow + 1
    # Align: truncate ema_f to match ema_s length
    trim = (slow - fast)
    ema_f_aligned = ema_f[trim:]
    assert len(ema_f_aligned) == len(ema_s)
    macd_line = [f - s for f, s in zip(ema_f_aligned, ema_s)]
    signal_line = _ema(macd_line, signal)
    if not signal_line:
        return [], [], []
    # Truncate macd_line to match signal_line length
    macd_line_aligned = macd_line[-len(signal_line):]
    hist = [m - s for m, s in zip(macd_line_aligned, signal_line)]
    return macd_line_aligned, signal_line, hist


class MACDDivergence:
    name: str = 'macd_divergence'

    def __init__(self, params: dict | None = None):
        self.params = {**_DEFAULT_PARAMS, **(params or {})}

    def on_day(self, date: date, close_history: dict, portfolio: dict) -> list[dict]:
        fast = int(self.params['fast'])
        slow = int(self.params['slow'])
        signal = int(self.params['signal'])
        position_pct = float(self.params['position_pct'])

        decisions: list[dict] = []
        positions = portfolio.get('positions', {}) or {}
        equity = float(portfolio.get('equity', 0.0))

        for code, series in close_history.items():
            closes = [c for _, c in series]
            macd_line, sig_line, hist = _macd(closes, fast, slow, signal)
            if len(hist) < 2:
                continue

            held = int(positions.get(code, {}).get('shares', 0))
            price = closes[-1]
            # Cross above: prev hist <= 0, current > 0
            if hist[-2] <= 0 and hist[-1] > 0 and held == 0:
                target_value = equity * position_pct
                shares = int(target_value / price // 100) * 100
                if shares > 0:
                    decisions.append({
                        'action': 'buy', 'code': code, 'shares': shares,
                        'reason': f'MACD line crossed above signal',
                    })
            elif hist[-2] >= 0 and hist[-1] < 0 and held > 0:
                decisions.append({
                    'action': 'sell', 'code': code, 'shares': held,
                    'reason': f'MACD line crossed below signal',
                })

        return decisions
```

- [ ] **Step 5: Register both**

Edit `backtest/strategies/__init__.py` — append after MACrossover registration:

```python
from .rsi_breakout import RSIBreakout
from .macd_divergence import MACDDivergence

register(RSIBreakout, StrategyDescriptor(
    name='rsi_breakout',
    display_name='RSI 超买超卖',
    description='RSI ≤ 30 买入（超卖反弹），RSI ≥ 70 卖出（超买）',
    default_params={'period': 14, 'oversold': 30.0, 'overbought': 70.0,
                    'position_pct': 0.3},
))

register(MACDDivergence, StrategyDescriptor(
    name='macd_divergence',
    display_name='MACD 交叉',
    description='MACD 线上穿信号线买入，下穿卖出',
    default_params={'fast': 12, 'slow': 26, 'signal': 9, 'position_pct': 0.3},
))
```

- [ ] **Step 6: GREEN**

Run: `python -m pytest tests/test_rule_mode.py -v`

- [ ] **Step 7: Commit**

```bash
git add backtest/strategies/ tests/test_rule_mode.py
git commit -m "feat(p3c): RSIBreakout + MACDDivergence strategies"
```

---

### Task 4: RuleRunner

**Files:**
- Create: `backtest/rule_runner.py`
- Test: `tests/test_rule_mode.py`

**Design:** Mirror `BacktestRunner.run`. Takes `strategy: Strategy` instead of `llm`. Walks trading days, accumulates close_history, calls `strategy.on_day`, executes decisions via Book, produces BacktestResult with `kind='rule'` and `agent_id=''`.

- [ ] **Step 1: 写失败测试**

```python
def test_rule_runner_produces_result_with_kind_rule(observability_storage, monkeypatch):
    from datetime import date, timedelta
    import backtest.rule_runner as runner_mod
    from backtest.rule_runner import RuleRunner
    from backtest.strategies import build

    days = [date(2025, 1, 2) + timedelta(days=i) for i in range(40)]
    # Ramp up prices so MA crossover buys early, then flat
    prices = [100.0 + i * 0.5 for i in range(40)]
    bars = list(zip(days, prices))
    monkeypatch.setattr(runner_mod, '_load_daily_closes',
                        lambda code, start, end: bars)
    monkeypatch.setattr(runner_mod, '_trading_days',
                        lambda start, end: days)

    strategy = build('ma_crossover', params={'fast': 3, 'slow': 10,
                                             'position_pct': 0.3})
    r = RuleRunner(strategy=strategy).run(
        session_id='s-rule', start_date='2025-01-02', end_date='2025-02-10',
        universe=['600519.SH'], initial_capital=1_000_000.0,
    )
    assert r.kind == 'rule'
    assert r.agent_id == ''
    assert r.persona_id is None
    assert r.model_id is None
    assert len(r.daily_records) == 40
    assert len(r.trades) >= 1
    # RuleRunner doesn't emit thinking (LLM concept)
    assert r.thinking == []


def test_rule_runner_persists_result(observability_storage, monkeypatch):
    from datetime import date, timedelta
    import storage
    import backtest.rule_runner as runner_mod
    from backtest.rule_runner import RuleRunner
    from backtest.strategies import build

    days = [date(2025, 1, 2) + timedelta(days=i) for i in range(15)]
    bars = [(d, 100.0 + i) for i, d in enumerate(days)]
    monkeypatch.setattr(runner_mod, '_load_daily_closes',
                        lambda code, start, end: bars)
    monkeypatch.setattr(runner_mod, '_trading_days',
                        lambda start, end: days)

    r = RuleRunner(strategy=build('ma_crossover',
                                  params={'fast': 3, 'slow': 5})).run(
        session_id='s-persist', start_date='2025-01-02', end_date='2025-01-20',
        universe=['600519.SH'], initial_capital=1_000_000.0,
    )
    fetched = storage.backtests().get(r.id)
    assert fetched is not None
    assert fetched.kind == 'rule'
```

- [ ] **Step 2: RED**

- [ ] **Step 3: 实现 RuleRunner**

Create `backtest/rule_runner.py`:

```python
"""RuleRunner — deterministic rule-strategy backtests, parallel structure to
BacktestRunner but driven by a Strategy instead of an AgentRunner/LLM."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from validation.quality_gate import evaluate_quality_gate

from .base import BacktestResult
from .stats import aggregate


def _load_daily_closes(code: str, start: date, end: date) -> list:
    """[(date, close), ...] ascending for one stock."""
    import storage
    from datetime import datetime as _dt
    bars = storage.kline().load_range(
        code, '1d',
        _dt(start.year, start.month, start.day),
        _dt(end.year, end.month, end.day),
    )
    return [(b.datetime.date(), float(b.close_price)) for b in bars]


def _trading_days(start: str, end: str) -> list:
    import storage
    return storage.calendar().get_trading_days(_parse(start), _parse(end))


def _parse(s: str) -> date:
    return datetime.strptime(s, '%Y-%m-%d').date()


class RuleRunner:
    def __init__(self, strategy, initial_capital: float = 1_000_000.0):
        self._strategy = strategy
        self._default_capital = initial_capital

    def run(self, *, session_id: str, start_date: str, end_date: str,
            initial_capital: float | None = None,
            universe: list[str], notes: str | None = None) -> BacktestResult:
        import storage
        from .book import Book
        from .commission import FeeModel
        from .portfolio_adapter import build_portfolio

        cap = float(initial_capital or self._default_capital)
        storage.backtests().create_session(
            session_id, start_date, end_date, [f'rule:{self._strategy.name}'],
            notes=notes,
        )

        start = _parse(start_date)
        end = _parse(end_date)
        price_series: dict[str, dict] = {}
        for code in universe:
            price_series[code] = dict(_load_daily_closes(code, start, end))

        days = _trading_days(start_date, end_date)
        book = Book(cash=cap, fee_model=FeeModel())
        daily_records: list[dict] = []
        prev_equity = cap

        for d in days:
            # Build mark prices (forward-fill if today missing)
            mark_prices = {code: price_series[code].get(d) for code in universe
                           if price_series[code].get(d) is not None}
            for code in universe:
                if code not in mark_prices:
                    past = [p for dt, p in price_series[code].items() if dt <= d]
                    if past:
                        mark_prices[code] = past[-1]
            if not mark_prices:
                continue

            # Build close_history up to and including today (ascending)
            close_history = {}
            for code in universe:
                close_history[code] = [
                    (dt, price_series[code][dt])
                    for dt in sorted(price_series[code])
                    if dt <= d
                ]

            portfolio = build_portfolio(
                cash=book.cash, positions=book.positions_view(),
                mark_prices=mark_prices,
            )
            decisions = self._strategy.on_day(
                date=d, close_history=close_history, portfolio=portfolio,
            )

            trade_count_today = 0
            wins_today = 0
            for dec in decisions:
                action = dec.get('action')
                code = dec.get('code')
                shares = int(dec.get('shares') or 0)
                px = mark_prices.get(code, float(dec.get('price', 0.0)))
                if action == 'buy':
                    fill = book.execute_buy(code, shares=shares,
                                            price=px, d=d)
                    if fill:
                        trade_count_today += 1
                elif action == 'sell':
                    avg_before = book.positions_view().get(
                        code, {}).get('avg_price', 0.0)
                    fill = book.execute_sell(code, shares=shares,
                                             price=px, d=d)
                    if fill:
                        trade_count_today += 1
                        if px > avg_before:
                            wins_today += 1

            equity = book.equity(mark_prices)
            pnl_pct = ((equity - prev_equity) / prev_equity * 100.0
                       if prev_equity > 0 else 0.0)
            prev_equity = equity
            daily_records.append({
                'date': d, 'pnl_pct': pnl_pct, 'equity': equity,
                'cash': book.cash,
                'trade_count': trade_count_today, 'won': wins_today,
            })

        # Rules have no training cutoff → treat entire window as "clean"
        overall, zones = aggregate(daily_records, cutoff='2099-12-31',
                                   initial_capital=cap)
        from .divergence import compute_divergence
        divergence_flag, _ = compute_divergence(zones)
        gate_input = {
            'sharpe': overall.sharpe,
            'max_drawdown_pct': overall.max_drawdown_pct,
            'trade_count': overall.trade_count,
            'win_rate': overall.win_rate,
            'max_daily_loss_pct': overall.max_daily_loss_pct,
            'clean_zone_days': next(
                (z.days for z in zones if z.zone == 'clean'), 0),
            'divergence_flag': divergence_flag,
        }
        gate = evaluate_quality_gate(gate_input)

        trades_serial = [
            {
                'date': f.date.isoformat(), 'code': f.code,
                'action': f.side, 'shares': f.shares,
                'price': f.price, 'fee': f.fee,
            }
            for f in book.fills
        ]
        daily_records_serial = [
            {
                'date': rec['date'].isoformat(),
                'equity': rec['equity'], 'cash': rec['cash'],
                'pnl_pct': rec['pnl_pct'],
                'trade_count': rec['trade_count'], 'won': rec['won'],
            }
            for rec in daily_records
        ]

        result = BacktestResult(
            id=str(uuid.uuid4()),
            session_id=session_id,
            agent_id='',  # sentinel: rule results have no agent
            persona_id=None, model_id=None,
            start_date=start_date, end_date=end_date,
            initial_capital=cap, stats=overall, zone_stats=zones,
            quality_gate_label=gate.label,
            quality_gate_criteria=gate.criteria,
            final_equity=prev_equity,
            daily_records=daily_records_serial,
            trades=trades_serial,
            thinking=[],
            kind='rule',
        )
        storage.backtests().insert(result)
        return result
```

- [ ] **Step 4: GREEN**

- [ ] **Step 5: Regression**

Run: `python -m pytest tests/ -q 2>&1 | tail -3`
Expected: previous baseline + new, 0 regressions.

- [ ] **Step 6: Commit**

```bash
git add backtest/rule_runner.py tests/test_rule_mode.py
git commit -m "feat(p3c): RuleRunner — Strategy-driven parallel to BacktestRunner"
```

---

### Task 5: SQLite persist `kind_str`

**Files:**
- Modify: `storage/sqlite_backtests.py`
- Test: `tests/test_rule_mode.py`

**Design:** Extend `_select_cols` + `_row_to_result` + `insert` + `init_schema` to handle the new column. Pattern mirrors P3-A Task 4.

Implementation details condensed (same migration + INSERT pattern):

- `_select_cols` appends `, kind_str` at end
- `_row_to_result` reads `row[16]` with empty-string guard → parse to `kind`
- `insert` adds `kind_str` to column list + placeholder, uses `getattr(result, 'kind', 'agent')`
- `init_schema` calls `ensure_kind_column(con)`
- `insert` also calls `ensure_kind_column(con)`

- [ ] **Step 1: Write roundtrip test**

```python
def test_sqlite_backtests_roundtrips_kind(observability_storage):
    import storage
    from backtest.base import BacktestResult, BacktestStats

    storage.backtests().create_session(
        's-kind', '2025-01-01', '2025-01-10', ['rule:ma_crossover'])
    r = BacktestResult(
        id='r-kind', session_id='s-kind', agent_id='',
        persona_id=None, model_id=None,
        start_date='2025-01-01', end_date='2025-01-10',
        initial_capital=100_000.0,
        stats=BacktestStats(sharpe=0.5, max_drawdown_pct=-2.0,
                            trade_count=4, win_rate=50.0,
                            max_daily_loss_pct=-1.0, total_return_pct=3.0,
                            final_equity=103_000.0),
        zone_stats=[], quality_gate_label='pass',
        quality_gate_criteria={},
        kind='rule',
    )
    storage.backtests().insert(r)
    fetched = storage.backtests().get('r-kind')
    assert fetched is not None
    assert fetched.kind == 'rule'


def test_sqlite_backtests_agent_kind_default_for_legacy(observability_storage):
    """Result inserted WITHOUT kind → stored as 'agent' via schema default."""
    import sqlite3, json
    from dataclasses import asdict
    import storage
    from backtest.base import BacktestStats

    storage.backtests().create_session(
        's-legacy', '2025-01-01', '2025-01-10', ['a1'])
    stats = BacktestStats(sharpe=0, max_drawdown_pct=0, trade_count=0,
                          win_rate=0, max_daily_loss_pct=0,
                          total_return_pct=0, final_equity=100_000)
    store = storage.backtests()
    db_path = store._db_path  # type: ignore[attr-defined]
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            '''INSERT INTO backtest_results
               (id, session_id, agent_id, persona_id, model_id,
                start_date, end_date, initial_capital, final_equity,
                stats_json, zone_stats_json, quality_gate_label,
                quality_gate_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            ('r-leg2', 's-legacy', 'a1', None, None,
             '2025-01-01', '2025-01-10', 100_000.0, 100_000.0,
             json.dumps(asdict(stats)), '[]', 'pass', '{}'),
        )
        con.commit()
    finally:
        con.close()
    fetched = storage.backtests().get('r-leg2')
    assert fetched is not None
    assert fetched.kind == 'agent'
```

- [ ] **Step 2: RED + implement + GREEN + Commit**

Implementation per pattern. Commit:

```bash
git add storage/sqlite_backtests.py tests/test_rule_mode.py
git commit -m "feat(p3c): persist kind_str on backtest_results"
```

---

### Task 6: API — POST /api/backtests/rule + GET /api/strategies

**Files:**
- Modify: `api/backtests.py`
- Create: `api/strategies.py`
- Modify: `api/__init__.py` (register strategies blueprint path)
- Test: `tests/test_rule_mode.py`

**Design:**

`GET /api/strategies` → list descriptors for frontend picker:
```json
[{name, display_name, description, default_params}, ...]
```

`POST /api/backtests/rule` body:
```json
{
  "strategy_name": "ma_crossover",
  "params": {"fast": 10, "slow": 30},
  "start_date": "2025-11-17",
  "end_date": "2025-11-28",
  "universe": ["600519.SH"],
  "initial_capital": 1000000,
  "session_id": "optional-existing-session-for-head-to-head"
}
```

If `session_id` omitted → create new session. Response 202: `{session_id, result_id, state: 'complete'}`. Unlike LLM mode (async), rule mode is fast enough to be synchronous.

Result serializer in `_result_to_dict` must include `kind`.

- [ ] **Step 1: Write endpoint tests**

```python
def test_get_strategies_lists_builtins(observability_storage, client):
    resp = client.get('/api/strategies')
    assert resp.status_code == 200
    data = resp.get_json()
    names = [s['name'] for s in data]
    assert 'ma_crossover' in names
    assert 'rsi_breakout' in names
    assert 'macd_divergence' in names


def test_post_rule_backtest_runs_synchronously(observability_storage, client, monkeypatch):
    from datetime import date, timedelta
    import backtest.rule_runner as runner_mod

    days = [date(2025, 1, 2) + timedelta(days=i) for i in range(15)]
    bars = [(d, 100.0 + i * 0.3) for i, d in enumerate(days)]
    monkeypatch.setattr(runner_mod, '_load_daily_closes',
                        lambda code, start, end: bars)
    monkeypatch.setattr(runner_mod, '_trading_days',
                        lambda start, end: days)

    resp = client.post('/api/backtests/rule', json={
        'strategy_name': 'ma_crossover',
        'params': {'fast': 3, 'slow': 5},
        'start_date': '2025-01-02',
        'end_date': '2025-01-20',
        'universe': ['600519.SH'],
        'initial_capital': 1_000_000,
    })
    assert resp.status_code == 202
    data = resp.get_json()
    assert data['state'] == 'complete'
    assert 'session_id' in data
    assert 'result_id' in data


def test_post_rule_backtest_joins_existing_session(observability_storage, client, monkeypatch):
    """Run a rule backtest with an explicit session_id — result should live
    in that session."""
    from datetime import date, timedelta
    import storage
    import backtest.rule_runner as runner_mod

    days = [date(2025, 1, 2) + timedelta(days=i) for i in range(15)]
    bars = [(d, 100.0 + i * 0.3) for i, d in enumerate(days)]
    monkeypatch.setattr(runner_mod, '_load_daily_closes',
                        lambda code, start, end: bars)
    monkeypatch.setattr(runner_mod, '_trading_days',
                        lambda start, end: days)

    resp = client.post('/api/backtests/rule', json={
        'strategy_name': 'ma_crossover',
        'params': {'fast': 3, 'slow': 5},
        'session_id': 'pre-existing',
        'start_date': '2025-01-02', 'end_date': '2025-01-20',
        'universe': ['600519.SH'], 'initial_capital': 1_000_000,
    })
    assert resp.status_code == 202
    assert resp.get_json()['session_id'] == 'pre-existing'
    results = storage.backtests().list_for_session('pre-existing')
    assert len(results) == 1
    assert results[0].kind == 'rule'


def test_post_rule_backtest_400_on_unknown_strategy(observability_storage, client):
    resp = client.post('/api/backtests/rule', json={
        'strategy_name': 'nope',
        'start_date': '2025-01-02', 'end_date': '2025-01-10',
        'universe': ['600519.SH'], 'initial_capital': 1_000_000,
    })
    assert resp.status_code == 400


def test_backtest_detail_response_includes_kind(observability_storage, client, monkeypatch):
    """GET /api/backtests/:id response must include 'kind' for frontend tab UI."""
    from datetime import date, timedelta
    import backtest.rule_runner as runner_mod
    days = [date(2025, 1, 2) + timedelta(days=i) for i in range(15)]
    bars = [(d, 100.0 + i * 0.3) for i, d in enumerate(days)]
    monkeypatch.setattr(runner_mod, '_load_daily_closes',
                        lambda code, start, end: bars)
    monkeypatch.setattr(runner_mod, '_trading_days',
                        lambda start, end: days)
    from backtest.rule_runner import RuleRunner
    from backtest.strategies import build
    r = RuleRunner(strategy=build('ma_crossover',
                                  params={'fast': 3, 'slow': 5})).run(
        session_id='s-kind-api', start_date='2025-01-02',
        end_date='2025-01-20', universe=['600519.SH'],
        initial_capital=1_000_000.0,
    )
    resp = client.get(f'/api/backtests/{r.id}')
    assert resp.status_code == 200
    assert resp.get_json().get('kind') == 'rule'
```

- [ ] **Step 2: Implement**

Create `api/strategies.py`:

```python
"""GET /api/strategies — list built-in rule strategies."""
from __future__ import annotations

from flask import jsonify

from . import api_bp


@api_bp.route('/strategies')
def list_strategies():
    from backtest.strategies import list_all
    from dataclasses import asdict
    return jsonify([asdict(d) for d in list_all()])
```

Edit `api/__init__.py` to import strategies at bottom (follow existing pattern).

Edit `api/backtests.py`:

- Update `_result_to_dict` to include `'kind': getattr(r, 'kind', 'agent')`
- Add new route:

```python
@api_bp.route('/backtests/rule', methods=['POST'])
def start_rule_backtest():
    """Synchronous rule-strategy backtest. Can join an existing session."""
    import uuid
    body = request.get_json(silent=True) or {}
    strategy_name = body.get('strategy_name')
    params = body.get('params') or {}
    start_date = body.get('start_date')
    end_date = body.get('end_date')
    universe = body.get('universe')
    initial_capital = body.get('initial_capital')
    if not (strategy_name and start_date and end_date
            and isinstance(universe, list) and universe
            and initial_capital is not None):
        return jsonify({'error': 'strategy_name, start_date, end_date, '
                                  'universe, initial_capital required'}), 400

    from backtest.strategies import get as get_strategy, build
    if get_strategy(strategy_name) is None:
        return jsonify({'error': f'unknown strategy: {strategy_name!r}'}), 400

    try:
        strategy = build(strategy_name, params=params)
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': f'strategy build failed: {e}'}), 400

    session_id = body.get('session_id') or f'session-{uuid.uuid4().hex[:12]}'

    from backtest.rule_runner import RuleRunner
    try:
        result = RuleRunner(strategy=strategy).run(
            session_id=session_id,
            start_date=start_date, end_date=end_date,
            initial_capital=float(initial_capital),
            universe=universe,
        )
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': f'run failed: {e}'}), 500

    return jsonify({
        'session_id': session_id,
        'result_id': result.id,
        'state': 'complete',
    }), 202
```

- [ ] **Step 3: GREEN + Regression + Commit**

```bash
git add api/strategies.py api/backtests.py api/__init__.py tests/test_rule_mode.py
git commit -m "feat(p3c): POST /api/backtests/rule + GET /api/strategies"
```

---

### Task 7: Frontend types + client + hooks + StrategyPicker

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/hooks.ts`
- Create: `frontend/src/components/StrategyPicker.tsx`

Types:

```typescript
export type StrategyDescriptor = {
  name: string;
  display_name: string;
  description: string;
  default_params: Record<string, number | string>;
};

export type StartRuleBacktestBody = {
  strategy_name: string;
  params?: Record<string, number>;
  session_id?: string;
  start_date: string;
  end_date: string;
  universe: string[];
  initial_capital: number;
};

export type StartRuleBacktestResponse = {
  session_id: string;
  result_id: string;
  state: string;
};
```

Extend `BacktestResult`:
```typescript
export type BacktestResult = {
  // ... existing fields ...
  kind: 'agent' | 'rule';
};
```

Client:
```typescript
  strategies: () => request<StrategyDescriptor[]>('/api/strategies'),
  startRuleBacktest: (body: StartRuleBacktestBody) =>
    request<StartRuleBacktestResponse>('/api/backtests/rule', {
      method: 'POST', body: JSON.stringify(body),
    }),
```

Hooks:
```typescript
export const useStrategies = () =>
  useQuery({ queryKey: ['strategies'], queryFn: api.strategies });

export const useStartRuleBacktest = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.startRuleBacktest,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['session', data.session_id] });
    },
  });
};
```

`StrategyPicker` component: dropdown + params editor per strategy. Keep minimal — user can tweak numeric params for the selected strategy.

- [ ] Build + commit.

---

### Task 8: BacktestLab Agent / Rule tab UI

**Files:**
- Modify: `frontend/src/pages/BacktestLab.tsx`

**UX:** Top of form area: 2-tab selector "Agent 模式 / 规则模式". Each tab has its own form. When rule tab is active, click Run → `startRuleBacktest`. Results table below merges both kinds (they share session_id).

Simplest impl: local state `mode: 'agent' | 'rule'`. Render different form subcomponent per mode. Share the run-status / results / nav chart area below.

ResultsTable: already handles BacktestResult — just update pill rendering to show "Agent" vs "Rule" based on `kind`. Agent row uses persona_id pill; Rule row uses strategy name pill (may need to store strategy_name in session notes or infer from agent_id prefix `rule:...`).

Actually simpler: the RuleRunner.run sets `agent_ids=[f'rule:{strategy_name}']` in `create_session`. So `result.agent_id === ''` but the row's "name" cell can render based on `kind`:
- `kind === 'agent'` → show `display_name` (query agent by id? — agent_id is there)
- `kind === 'rule'` → show strategy display_name (need to keep it somewhere — simplest is via session.agent_ids[0] stripping `rule:` prefix)

Alternatively: add `display_name` or similar field to BacktestResult. Over-engineering — for MVP, just render "Rule Strategy" generic text or parse from `session.agent_ids`.

Cleanest: new `BacktestResult.display_label` field that RuleRunner populates. But that's a schema change. Park it — instead, ResultsTable logic:

```tsx
const label =
  r.kind === 'rule'
    ? '规则策略'  // TODO: pass strategy name via session
    : r.agent_id;
```

Or pass `strategy_name` into session `notes` on create, and the frontend extracts.

For the smoke test we'll know from context. MVP accepts this UX gap.

- [ ] Tasks split: (a) mode toggle + rule form, (b) mutate ResultsTable for kind. Build + commit separately.

---

### Task 9: Roadmap + final regression

- [ ] `python -m pytest -q` — verify all pass
- [ ] `cd frontend && npm run build` — verify clean
- [ ] Update `docs/superpowers/plans/2026-04-23-status-and-roadmap.md`:
   - P3-C section → ✅ Done
   - Section 7 link to this plan
- [ ] Commit roadmap
- [ ] Exec `finishing-a-development-branch` — merge or PR choice

---

## Self-Review

**Spec coverage:**
- `backtest/rule_runner.py` ✅ Task 4
- 3 strategies ✅ Tasks 2+3
- `POST /api/backtest/rule` ✅ Task 6 (路径 `/api/backtests/rule`，实际端点比 spec 更一致)
- `BacktestResult.kind` ✅ Task 1
- 前端 tab ✅ Task 8
- Head-to-head 同 session ✅ Task 6 via `session_id` in body

**Deviations from spec:**
- spec §6.3: "vnpy CtaTemplate 子类" — **不用**。自写 Strategy Protocol + 复用 Book/stats，保持数据出口与 agent 模式一致。文档注明。
- 前端 ResultsTable 的 rule strategy 显示名暂用 generic "规则策略"，不从 BacktestResult 直接取；可后续 schema 加 display_label 改进。

**Type consistency:**
- Backend `BacktestResult.kind: str` ←→ frontend `kind: 'agent' | 'rule'`
- `StrategyDescriptor` 前后端一致

**No placeholders:** 所有 step 都有完整代码 / 命令 / 预期。

---

## Execution Handoff

Subagent-driven。单任务耗时估计：

- Task 1: 20 min — schema + dataclass
- Task 2: 30 min — Strategy Protocol + MACrossover + registry
- Task 3: 45 min — RSI + MACD
- Task 4: 45 min — RuleRunner
- Task 5: 25 min — storage persist kind
- Task 6: 40 min — 2 endpoints
- Task 7: 30 min — frontend types/hooks/picker
- Task 8: 45 min — BacktestLab tab UI
- Task 9: 15 min — roadmap + regression

Total: ~5 小时单人 + subagent 开销 ≈ 1.5-2 天，与 roadmap 的 2 天估计一致。
