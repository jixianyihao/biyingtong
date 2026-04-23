# P2d: Baselines + Divergence + Agent Rating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make backtests comparable (vs passive baselines), detectable (cross-cutoff divergence), and rateable (agent health score → trust rating). Also pay down P2c's book-integrity debt: real commissions and strict T+1.

**Architecture:**
- **Book class** centralizes cash + tranched positions with per-tranche `buy_date` for T+1 enforcement and applies A-share commission/stamp-duty on fills. `BacktestRunner` delegates to it.
- **Baselines** run through the same date/price/zone pipeline as agent backtests, producing `BaselineResult` rows in a sibling table. Three MVP baselines: buy-and-hold (equal-weight universe at start), equal-weight monthly rebalance, CSI 300 index tracker.
- **Divergence** computed from `zone_stats`: normalized distance between pollution-zone and clean-zone returns (with min-sample guards). Fills the previously-hardcoded `divergence_flag`.
- **Health score** uses Spec § 8.1 formula with `live_deviation_pts=0` in MVP (no live deployment yet). Reads audit_log + backtest_results; writes to `agents.health_score` + `agents.trust_rating`.
- **P2c debt pay-down:** unknown model emits audit warning, Book enforces T+1 + fees, divergence_flag wired live.

**Tech stack:** Python 3.10+, sqlite3, existing P2a-c stack. No new deps.

---

## File Structure

### New files
- `backtest/book.py` — `Book` class with tranche-level positions + T+1 + commission
- `backtest/commission.py` — `FeeModel` (buy 0.03%, sell 0.13%)
- `backtest/divergence.py` — zone divergence metric + flag
- `backtest/baselines/__init__.py`
- `backtest/baselines/base.py` — `BaselineResult` dataclass + common runner helpers
- `backtest/baselines/buy_and_hold.py`
- `backtest/baselines/equal_weight.py` — monthly rebalance
- `backtest/baselines/csi300.py`
- `backtest/baselines/runner.py` — `BaselineRunner` orchestrator (runs all 3 under one session)
- `agents/rating.py` — `compute_health` + `classify_trust_rating`
- `storage/sqlite_baselines.py` — `SQLiteBaselineResultStore`
- `data_schema/baseline_state.py` — DDL for `baseline_results` table
- Tests: one `test_*.py` per module + E2E

### Modified files
- `storage/base.py` — append `BaselineResultStore` Protocol
- `storage/__init__.py` — add `baselines()` factory + setter + reset
- `storage/sqlite_agents.py` — add `update_health(agent_id, health, rating)` method (+ extend `AgentStore` Protocol in base)
- `backtest/runner.py` — use `Book`, fill `divergence_flag`, emit unknown-model audit entry
- `storage/base.py` — append `update_health` to `AgentStore` Protocol

---

## Task 1: Commission / FeeModel

**Files:**
- Create: `backtest/commission.py`
- Test: `tests/test_commission.py`

**Spec:** Given a fill (`side`, `shares`, `price`), compute fees. A-share defaults:
- Buy fee = 0.03% of notional (brokerage only)
- Sell fee = 0.13% of notional (0.03% brokerage + 0.1% stamp duty)
- Configurable via `FeeModel(buy_bps=3.0, sell_bps=13.0)`; 1 bp = 0.01%.

- [ ] **Step 1: Write failing test**

```python
# tests/test_commission.py
"""FeeModel — A-share buy/sell fees."""


def test_default_buy_fee():
    from backtest.commission import FeeModel
    m = FeeModel()
    # 100 shares @ 1000 = 100,000 notional; buy 0.03% = 30
    assert abs(m.fee(side='buy', shares=100, price=1000.0) - 30.0) < 1e-6


def test_default_sell_fee():
    from backtest.commission import FeeModel
    m = FeeModel()
    # 100 shares @ 1000 = 100,000 notional; sell 0.13% = 130
    assert abs(m.fee(side='sell', shares=100, price=1000.0) - 130.0) < 1e-6


def test_custom_rates():
    from backtest.commission import FeeModel
    m = FeeModel(buy_bps=5.0, sell_bps=20.0)
    assert abs(m.fee(side='buy', shares=1000, price=10.0) - 5.0) < 1e-6
    assert abs(m.fee(side='sell', shares=1000, price=10.0) - 20.0) < 1e-6


def test_zero_shares_is_zero_fee():
    from backtest.commission import FeeModel
    m = FeeModel()
    assert m.fee(side='buy', shares=0, price=100.0) == 0.0


def test_unknown_side_raises():
    import pytest
    from backtest.commission import FeeModel
    m = FeeModel()
    with pytest.raises(ValueError):
        m.fee(side='short', shares=100, price=10.0)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_commission.py -v` → `ModuleNotFoundError: backtest.commission`

- [ ] **Step 3: Implement**

```python
# backtest/commission.py
"""A-share commission + stamp duty model."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeeModel:
    """Fee expressed as basis points (1 bp = 0.01%).

    A-share MVP defaults: 3 bp buy (brokerage only), 13 bp sell
    (3 bp brokerage + 10 bp stamp duty).
    """
    buy_bps: float = 3.0
    sell_bps: float = 13.0

    def fee(self, *, side: str, shares: int, price: float) -> float:
        if side == 'buy':
            bps = self.buy_bps
        elif side == 'sell':
            bps = self.sell_bps
        else:
            raise ValueError(f'unknown side: {side!r}')
        if shares <= 0 or price <= 0:
            return 0.0
        notional = shares * price
        return notional * (bps / 10_000.0)
```

- [ ] **Step 4: Verify + commit**

```bash
python -m pytest tests/test_commission.py -v       # 5 PASSED
python -m pytest -q                                 # all green
git add backtest/commission.py tests/test_commission.py
git commit -m "feat(p2d): FeeModel — A-share buy/sell commission"
```

---

## Task 2: Book class — tranche positions + T+1 + commission

**Files:**
- Create: `backtest/book.py`
- Test: `tests/test_book.py`

**Spec:**
- `Book(cash, fee_model)` — mutable book.
- `execute_buy(code, shares, price, date) -> Fill | None` — deduct `cash` by (shares*price + fee); reject (return None) if insufficient cash. Store a `Tranche(shares, avg_price=price, buy_date=date)` per buy — multiple tranches per code.
- `execute_sell(code, shares, price, date) -> Fill | None` — only consume tranches where `buy_date < date` (T+1). FIFO. Proceeds = shares*price - fee. Reject if no sellable shares.
- `positions_view() -> dict[code, {shares, avg_price}]` — aggregated for portfolio builder. `shares` sums all tranches; `avg_price` is cost-weighted.
- `equity(mark_prices) -> float` — cash + sum(shares * mark_prices[code] for each position).
- `total_fees` accumulator.

- [ ] **Step 1: Write failing test**

```python
# tests/test_book.py
"""Book — tranche positions + T+1 + commission."""
from datetime import date


def _book(cash=1_000_000.0):
    from backtest.book import Book
    from backtest.commission import FeeModel
    return Book(cash=cash, fee_model=FeeModel())


def test_buy_deducts_cash_plus_fee():
    b = _book()
    fill = b.execute_buy('X.SH', shares=100, price=1000.0, d=date(2024, 3, 1))
    assert fill is not None
    # cost 100k + fee 30 (0.03%) = 100_030
    assert abs(b.cash - (1_000_000 - 100_030)) < 1e-6
    assert b.total_fees == 30.0


def test_buy_with_insufficient_cash_returns_none():
    b = _book(cash=1000.0)
    fill = b.execute_buy('X.SH', shares=100, price=1000.0, d=date(2024, 3, 1))
    assert fill is None
    assert b.cash == 1000.0


def test_sell_same_day_rejected_t_plus_1():
    """T+1: cannot sell shares bought today."""
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    fill = b.execute_sell('X.SH', shares=100, price=110.0, d=date(2024, 3, 1))
    assert fill is None  # same-day sell rejected


def test_sell_next_day_allowed():
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    fill = b.execute_sell('X.SH', shares=100, price=110.0, d=date(2024, 3, 2))
    assert fill is not None
    # proceeds = 100 * 110 = 11,000; sell fee 0.13% = 14.3; net 10,985.7
    expected_cash = 1_000_000 - (100 * 100 + 3.0) + (11_000 - 14.3)
    assert abs(b.cash - expected_cash) < 0.01


def test_sell_fifo_tranches():
    """Multiple buys create multiple tranches; sell consumes oldest first."""
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    b.execute_buy('X.SH', shares=100, price=120.0, d=date(2024, 3, 2))
    # Day 3: sell 100 — should consume the 100@100 tranche (FIFO)
    b.execute_sell('X.SH', shares=100, price=130.0, d=date(2024, 3, 3))
    view = b.positions_view()
    assert view['X.SH']['shares'] == 100
    assert abs(view['X.SH']['avg_price'] - 120.0) < 1e-6


def test_sell_over_shares_sells_what_it_can():
    """Requesting more than owned sells available qty; rejection is for 0."""
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    fill = b.execute_sell('X.SH', shares=500, price=110.0, d=date(2024, 3, 2))
    assert fill is not None
    assert fill.shares == 100
    assert b.positions_view().get('X.SH', {}).get('shares', 0) == 0


def test_positions_view_excludes_empty():
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    b.execute_sell('X.SH', shares=100, price=110.0, d=date(2024, 3, 2))
    assert 'X.SH' not in b.positions_view()


def test_equity_marks_to_market():
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    # mark @ 150 → cash (999_970 - 0 = 999_970 after buy cost+fee) + 100*150 = 1_014_970
    eq = b.equity(mark_prices={'X.SH': 150.0})
    assert abs(eq - (1_000_000 - 10_003 + 100 * 150)) < 1e-6


def test_cost_weighted_avg_price_across_tranches():
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    b.execute_buy('X.SH', shares=300, price=200.0, d=date(2024, 3, 2))
    # avg = (100*100 + 300*200) / 400 = 70_000 / 400 = 175
    view = b.positions_view()
    assert abs(view['X.SH']['avg_price'] - 175.0) < 1e-6
    assert view['X.SH']['shares'] == 400
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_book.py -v`
Expected: 9 FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement**

```python
# backtest/book.py
"""Book — cash + tranched positions with T+1 + commission.

A-share T+1: shares bought on day D may only be sold on day D+1 or later.
Each buy creates a Tranche with its own buy_date; sells FIFO-consume tranches
where `buy_date < today`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .commission import FeeModel


@dataclass
class Tranche:
    shares: int
    price: float        # entry price (avg within this tranche = entry)
    buy_date: date


@dataclass
class Fill:
    code: str
    side: str           # 'buy' | 'sell'
    shares: int
    price: float
    fee: float
    date: date


@dataclass
class Book:
    cash: float
    fee_model: FeeModel
    _tranches: dict = field(default_factory=dict)  # code -> list[Tranche]
    total_fees: float = 0.0

    def execute_buy(self, code: str, *, shares: int, price: float,
                    d: date) -> Fill | None:
        if shares <= 0 or price <= 0:
            return None
        notional = shares * price
        fee = self.fee_model.fee(side='buy', shares=shares, price=price)
        total_cost = notional + fee
        if total_cost > self.cash:
            return None
        self.cash -= total_cost
        self.total_fees += fee
        self._tranches.setdefault(code, []).append(
            Tranche(shares=shares, price=price, buy_date=d)
        )
        return Fill(code=code, side='buy', shares=shares, price=price,
                    fee=fee, date=d)

    def execute_sell(self, code: str, *, shares: int, price: float,
                     d: date) -> Fill | None:
        if shares <= 0 or price <= 0:
            return None
        tranches = self._tranches.get(code, [])
        # Only tranches bought strictly before today are sellable (T+1)
        sellable = [t for t in tranches if t.buy_date < d]
        available = sum(t.shares for t in sellable)
        if available <= 0:
            return None
        to_sell = min(shares, available)
        # FIFO-consume from oldest sellable tranche
        remaining = to_sell
        for t in sellable:
            if remaining <= 0:
                break
            take = min(t.shares, remaining)
            t.shares -= take
            remaining -= take
        # Purge zero-share tranches, preserve non-sellable (same-day) ones
        self._tranches[code] = [t for t in tranches if t.shares > 0]
        if not self._tranches[code]:
            del self._tranches[code]

        notional = to_sell * price
        fee = self.fee_model.fee(side='sell', shares=to_sell, price=price)
        proceeds = notional - fee
        self.cash += proceeds
        self.total_fees += fee
        return Fill(code=code, side='sell', shares=to_sell, price=price,
                    fee=fee, date=d)

    def positions_view(self) -> dict:
        """Aggregated per-code: shares + cost-weighted avg_price.

        Excludes codes with zero total shares.
        """
        out: dict = {}
        for code, tranches in self._tranches.items():
            total_shares = sum(t.shares for t in tranches)
            if total_shares <= 0:
                continue
            total_cost = sum(t.shares * t.price for t in tranches)
            out[code] = {
                'shares': total_shares,
                'avg_price': total_cost / total_shares,
            }
        return out

    def equity(self, mark_prices: dict) -> float:
        eq = self.cash
        for code, info in self.positions_view().items():
            mark = mark_prices.get(code, info['avg_price'])
            eq += info['shares'] * mark
        return eq
```

- [ ] **Step 4: Verify + commit**

```bash
python -m pytest tests/test_book.py -v     # 9 PASSED
python -m pytest -q                         # all green
git add backtest/book.py tests/test_book.py
git commit -m "feat(p2d): Book with tranche positions + T+1 + commission"
```

---

## Task 3: Rewire BacktestRunner to use Book

**Files:**
- Modify: `backtest/runner.py`
- Modify: `tests/test_backtest_runner.py` (update expectations if needed)
- Modify: `tests/test_p2c_e2e.py` (same)

**Spec:** Replace the inline cash + positions dict with a `Book` instance. Decision execution becomes `book.execute_buy(...)` / `book.execute_sell(...)`. Portfolio passed to `AgentRunner` is built from `book.positions_view()` via existing `build_portfolio`.

- [ ] **Step 1: Read current runner.py**

Load `backtest/runner.py` in your head — identify the daily loop body that handles `action == 'buy'` / `action == 'sell'`. That block gets replaced.

- [ ] **Step 2: Replace the daily-loop body**

The loop over decisions becomes:

```python
            trade_count_today = 0
            wins_today = 0
            for dec in decisions:
                action = dec.get('action')
                code = dec.get('code')
                shares = int(dec.get('shares') or dec.get('qty') or 0)
                px = mark_prices.get(code, float(dec.get('price', 0.0)))
                if action == 'buy':
                    fill = book.execute_buy(code, shares=shares,
                                             price=px, d=d)
                    if fill:
                        trade_count_today += 1
                elif action == 'sell':
                    # Track win via avg price before sell removes tranches
                    avg_before = book.positions_view().get(
                        code, {}).get('avg_price', 0.0)
                    fill = book.execute_sell(code, shares=shares,
                                              price=px, d=d)
                    if fill:
                        trade_count_today += 1
                        if px > avg_before:
                            wins_today += 1
```

And initialize `book` before the day loop:

```python
        from .book import Book
        from .commission import FeeModel
        book = Book(cash=cap, fee_model=FeeModel())
```

Replace references to `cash` / `positions` in `build_portfolio(...)` with `book.cash` and `book.positions_view()`. Replace `equity = cash + ...` computation with `equity = book.equity(mark_prices)`.

- [ ] **Step 3: Update existing tests if expectations changed**

Existing tests in `tests/test_backtest_runner.py`:
- `test_run_produces_backtest_result` — 10 hold days, no trades → no fees impact. Should still pass.
- `test_buy_decision_reduces_cash` — Day 1 buy 100 @ 100 = 10k + fee (3). Days 2+ hold (with T+1 constraint, can't sell day 1's buy until day 2). The assertion `stats.trade_count >= 1` still holds. `final_equity != 1_000_000` still holds (fee reduces it).

Existing `tests/test_p2c_e2e.py`:
- `test_e2e_full_pipeline` — similar; buy day 1 passes, equity movement now includes fees. Assertions should still hold.
- `test_e2e_rerun_uses_cache` — 3 hold days, nothing changes. Still passes.
- `test_zone_stats_split_across_cutoff` — 30 hold days. Still passes.

Run to confirm. If any break, update test expectations (don't change code).

- [ ] **Step 4: Verify + commit**

```bash
python -m pytest tests/test_backtest_runner.py tests/test_p2c_e2e.py tests/test_p2c_multi_persona.py -v
python -m pytest -q
git add backtest/runner.py tests/
git commit -m "feat(p2d): BacktestRunner uses Book (T+1 + commissions)"
```

---

## Task 4: Zone divergence calculator

**Files:**
- Create: `backtest/divergence.py`
- Test: `tests/test_divergence.py`

**Spec:** Given `zone_stats: list[ZoneStats]`, compute a `divergence_flag: bool`. The signal fires when pollution-zone Sharpe materially differs from clean-zone Sharpe (likely memorization). Also returns the raw metric for audit.

Rule (MVP):
- If either zone has `days < 10` or empty `stats` dict → return `(False, None)` (not enough data to judge; be conservative — fail-open).
- Let `p = pollution.stats['total_return_pct']`, `c = clean.stats['total_return_pct']`.
- Normalized distance: `d = |p - c| / (|p| + |c| + 1e-6)`
- Flag = `d > 0.5` (> 50% relative difference). Threshold argument configurable.

- [ ] **Step 1: Write failing test**

```python
# tests/test_divergence.py
"""Zone divergence metric."""


def _zone(zone, days, total_return):
    from backtest.base import ZoneStats
    return ZoneStats(
        zone=zone, days=days,
        stats={'total_return_pct': total_return, 'sharpe': 1.0,
               'max_drawdown_pct': -5, 'trade_count': 5,
               'win_rate': 50, 'max_daily_loss_pct': -1,
               'final_equity': 100_000},
    )


def test_flag_false_when_pollution_and_clean_match():
    from backtest.divergence import compute_divergence
    zones = [_zone('pollution', 60, 10.0),
             _zone('buffer', 10, 5.0),
             _zone('clean', 60, 10.5)]
    flag, metric = compute_divergence(zones)
    assert flag is False


def test_flag_true_when_pollution_far_exceeds_clean():
    """Classic memorization pattern: 20% in pollution, -5% in clean."""
    from backtest.divergence import compute_divergence
    zones = [_zone('pollution', 60, 20.0),
             _zone('buffer', 10, 0.0),
             _zone('clean', 60, -5.0)]
    flag, metric = compute_divergence(zones)
    assert flag is True
    assert metric is not None and metric > 0.5


def test_insufficient_clean_days_fails_open():
    from backtest.divergence import compute_divergence
    zones = [_zone('pollution', 60, 20.0),
             _zone('buffer', 5, 0.0),
             _zone('clean', 5, -5.0)]  # only 5 clean days
    flag, metric = compute_divergence(zones)
    assert flag is False
    assert metric is None


def test_missing_zone_fails_open():
    from backtest.divergence import compute_divergence
    from backtest.base import ZoneStats
    zones = [ZoneStats('pollution', 60, {}),
             ZoneStats('buffer', 10, {}),
             ZoneStats('clean', 0, {})]
    flag, _ = compute_divergence(zones)
    assert flag is False


def test_custom_threshold():
    from backtest.divergence import compute_divergence
    zones = [_zone('pollution', 60, 10.0),
             _zone('buffer', 10, 5.0),
             _zone('clean', 60, 5.0)]
    # p=10, c=5 → metric = 5/15 = 0.333. Below 0.5 default → False
    flag_default, metric = compute_divergence(zones)
    assert flag_default is False
    # With tighter threshold 0.2 → True
    flag_strict, _ = compute_divergence(zones, threshold=0.2)
    assert flag_strict is True
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_divergence.py -v`
Expected: 5 FAIL

- [ ] **Step 3: Implement**

```python
# backtest/divergence.py
"""Cross-cutoff divergence detector.

Fires when pollution-zone returns materially exceed clean-zone returns
(classic training-data-memorization signature). Requires ≥10 days in each zone.
"""
from __future__ import annotations

_MIN_DAYS = 10
_DEFAULT_THRESHOLD = 0.5  # 50% relative distance


def compute_divergence(zone_stats: list, threshold: float = _DEFAULT_THRESHOLD):
    """Return (flag, metric).

    flag=True when |pollution_return - clean_return| / (|p|+|c|+eps) > threshold
    and both zones have >= _MIN_DAYS of data. Otherwise fail-open.
    """
    by_zone = {z.zone: z for z in zone_stats}
    pollution = by_zone.get('pollution')
    clean = by_zone.get('clean')
    if pollution is None or clean is None:
        return False, None
    if pollution.days < _MIN_DAYS or clean.days < _MIN_DAYS:
        return False, None
    if not pollution.stats or not clean.stats:
        return False, None
    p = float(pollution.stats.get('total_return_pct', 0.0))
    c = float(clean.stats.get('total_return_pct', 0.0))
    denom = abs(p) + abs(c) + 1e-6
    metric = abs(p - c) / denom
    return (metric > threshold), metric
```

- [ ] **Step 4: Verify + commit**

```bash
python -m pytest tests/test_divergence.py -v      # 5 PASSED
git add backtest/divergence.py tests/test_divergence.py
git commit -m "feat(p2d): cross-cutoff divergence detector"
```

---

## Task 5: Wire divergence_flag + unknown-model audit into BacktestRunner

**Files:**
- Modify: `backtest/runner.py`
- Modify: `tests/test_backtest_runner.py` (append one test)

**Spec:**
1. In `run()`, after `aggregate(...)` returns `(overall, zones)`, call `compute_divergence(zones)` and pass the flag into `gate_input['divergence_flag']`.
2. If the agent's `model_id` is non-empty but `storage.models().get(model_id)` returns None, emit an `AuditEntry(kind='warning', agent_id, details={'kind': 'unknown_model', 'model_id': model_id})` before falling back to `cutoff = '2099-12-31'`.

- [ ] **Step 1: Append failing test**

```python
def test_unknown_model_audits_warning(wired_full, monkeypatch):
    """Unknown model_id emits an audit warning and uses fallback cutoff."""
    import backtest.runner as mod
    import storage
    from datetime import date, timedelta
    from llm.mock import MockLLM
    from backtest.runner import BacktestRunner

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='nonexistent-model-xyz',
        display_name='Unknown',
    )

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(3)]
    prices = [(d, 100.0) for d in days]
    monkeypatch.setattr(mod, '_load_daily_closes', lambda c, s, e: prices)
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)

    hold = {'tool_calls': [{'id': 'c', 'name': 'place_decision',
                            'input': {'action': 'hold',
                                      'reason': 'nothing to trade',
                                      'thinking': 't'}}],
            'stop_reason': 'tool_use'}
    llm = MockLLM([hold, hold, hold])
    BacktestRunner(llm=llm).run(
        session_id='unk', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-03',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )

    warns = [r for r in storage.audit().query_by_agent(agent.id)
             if r['kind'] == 'warning']
    assert len(warns) >= 1
    assert any(w['details'].get('kind') == 'unknown_model' for w in warns)


def test_divergence_flag_is_computed(wired_full, monkeypatch):
    """BacktestRunner fills divergence_flag from zone_stats."""
    import backtest.runner as mod
    import storage
    from datetime import date, timedelta
    from llm.mock import MockLLM
    from backtest.runner import BacktestRunner

    # Override model cutoff to mid-window
    class _M:
        training_cutoff = '2024-03-15'
    monkeypatch.setattr(storage.models(), 'get', lambda _id: _M())

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='DivTest',
    )

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(90)]
    # Flat prices → zero return in both zones → metric=0 → flag False
    prices = [(d, 100.0) for d in days]
    monkeypatch.setattr(mod, '_load_daily_closes', lambda c, s, e: prices)
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    hold = {'tool_calls': [{'id': 'c', 'name': 'place_decision',
                            'input': {'action': 'hold',
                                      'reason': 'holding pattern at current levels',
                                      'thinking': 't'}}],
            'stop_reason': 'tool_use'}
    llm = MockLLM([hold] * 90)
    result = BacktestRunner(llm=llm).run(
        session_id='div', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-05-29',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )
    # divergence_flag enters quality_gate_criteria as max_divergence_flag
    gate = result.quality_gate_criteria
    assert 'max_divergence_flag' in gate
    # With flat prices, both zones have ~0 return → divergence False
    assert gate['max_divergence_flag']['ok'] is True
```

- [ ] **Step 2: Modify `backtest/runner.py`**

Replace the section where `gate_input` is built. New version:

```python
        # Aggregate + divergence + quality gate
        cutoff = '2099-12-31'
        model = storage.models().get(model_id) if model_id else None
        if model is not None:
            cutoff = model.training_cutoff
        elif model_id:
            # Non-empty model_id but not in registry → log warning
            from validation.base import AuditEntry
            storage.audit().log(AuditEntry(
                kind='warning', agent_id=agent_id,
                persona_id=persona_id, model_id=model_id,
                details={'kind': 'unknown_model', 'model_id': model_id},
            ))

        overall, zones = aggregate(daily_records, cutoff=cutoff,
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
```

- [ ] **Step 3: Verify + commit**

```bash
python -m pytest tests/test_backtest_runner.py -v
python -m pytest -q
git add backtest/runner.py tests/test_backtest_runner.py
git commit -m "feat(p2d): wire divergence_flag + unknown-model audit warning"
```

---

## Task 6: Baseline result dataclass + schema + Protocol + store

**Files:**
- Create: `data_schema/baseline_state.py`
- Create: `backtest/baselines/__init__.py`, `backtest/baselines/base.py`
- Modify: `storage/base.py` (append Protocol)
- Create: `storage/sqlite_baselines.py`
- Tests: `tests/test_baseline_schema.py`, `tests/test_baseline_base.py`, `tests/test_storage_baselines.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_baseline_schema.py
"""DDL sanity for baseline_results."""
import sqlite3


def test_schema_creates_table(tmp_path):
    from data_schema.baseline_state import SCHEMA_BASELINE_RESULTS
    db = tmp_path / 'x.db'
    con = sqlite3.connect(db)
    try:
        con.executescript(SCHEMA_BASELINE_RESULTS)
        names = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    finally:
        con.close()
    assert 'baseline_results' in names


def test_indexes_present():
    from data_schema.baseline_state import SCHEMA_BASELINE_RESULTS
    assert 'baselines_by_session' in SCHEMA_BASELINE_RESULTS
```

```python
# tests/test_baseline_base.py
"""BaselineResult dataclass shape."""


def test_baseline_result_fields():
    from backtest.baselines.base import BaselineResult
    from backtest.base import BacktestStats
    stats = BacktestStats(
        sharpe=0.2, max_drawdown_pct=-8, trade_count=1,
        win_rate=100, max_daily_loss_pct=-2,
        total_return_pct=3, final_equity=1_030_000,
    )
    r = BaselineResult(
        id='b1', session_id='s1', name='buy_and_hold',
        start_date='2024-01-01', end_date='2024-03-01',
        initial_capital=1_000_000, stats=stats, final_equity=1_030_000,
    )
    assert r.name == 'buy_and_hold'
    assert r.stats.total_return_pct == 3
```

```python
# tests/test_storage_baselines.py
"""SQLiteBaselineResultStore."""


def _make(id='b1', name='buy_and_hold'):
    from backtest.base import BacktestStats
    from backtest.baselines.base import BaselineResult
    stats = BacktestStats(
        sharpe=0.2, max_drawdown_pct=-8, trade_count=1,
        win_rate=100, max_daily_loss_pct=-2,
        total_return_pct=3, final_equity=1_030_000,
    )
    return BaselineResult(
        id=id, session_id='s1', name=name,
        start_date='2024-01-01', end_date='2024-03-01',
        initial_capital=1_000_000, stats=stats, final_equity=1_030_000,
    )


def test_insert_then_get(tmp_path):
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    s = SQLiteBaselineResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.insert(_make())
    got = s.get('b1')
    assert got is not None
    assert got.name == 'buy_and_hold'


def test_list_for_session(tmp_path):
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    s = SQLiteBaselineResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.insert(_make(id='b1', name='buy_and_hold'))
    s.insert(_make(id='b2', name='csi300'))
    rows = s.list_for_session('s1')
    assert {r.name for r in rows} == {'buy_and_hold', 'csi300'}


def test_protocol_exposed():
    from storage.base import BaselineResultStore
    for m in ('init_schema', 'insert', 'get', 'list_for_session'):
        assert hasattr(BaselineResultStore, m), f'missing {m}'
```

- [ ] **Step 2: Run & verify failure**

```bash
python -m pytest tests/test_baseline_schema.py tests/test_baseline_base.py tests/test_storage_baselines.py -v
```

Expected: all FAIL.

- [ ] **Step 3: Implement**

```python
# data_schema/baseline_state.py
"""DDL for baseline_results (P2d)."""

SCHEMA_BASELINE_RESULTS = '''
CREATE TABLE IF NOT EXISTS baseline_results (
    id                TEXT PRIMARY KEY,
    session_id        TEXT NOT NULL,
    name              TEXT NOT NULL,
    start_date        TEXT NOT NULL,
    end_date          TEXT NOT NULL,
    initial_capital   REAL NOT NULL,
    final_equity      REAL,
    stats_json        TEXT NOT NULL,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS baselines_by_session
    ON baseline_results(session_id);
'''
```

```python
# backtest/baselines/__init__.py
"""Passive-strategy baselines for benchmarking agents (P2d)."""
```

```python
# backtest/baselines/base.py
"""BaselineResult dataclass + shared signatures."""
from __future__ import annotations

from dataclasses import dataclass

from backtest.base import BacktestStats


@dataclass
class BaselineResult:
    id: str
    session_id: str
    name: str                    # 'buy_and_hold' | 'equal_weight' | 'csi300'
    start_date: str
    end_date: str
    initial_capital: float
    stats: BacktestStats
    final_equity: float | None = None
```

Append to `storage/base.py`:

```python
@runtime_checkable
class BaselineResultStore(Protocol):
    """baseline_results table."""
    def init_schema(self) -> None: ...
    def insert(self, result) -> None:
        """Persist a BaselineResult. Idempotent by id."""
        ...
    def get(self, result_id: str): ...
    def list_for_session(self, session_id: str) -> list: ...
```

```python
# storage/sqlite_baselines.py
"""SQLiteBaselineResultStore."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from data_schema.baseline_state import SCHEMA_BASELINE_RESULTS

from .base import BaselineResultStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _row_to_result(row):
    from backtest.base import BacktestStats
    from backtest.baselines.base import BaselineResult
    stats = BacktestStats(**json.loads(row[7]))
    return BaselineResult(
        id=row[0], session_id=row[1], name=row[2],
        start_date=row[3], end_date=row[4],
        initial_capital=row[5], final_equity=row[6],
        stats=stats,
    )


class SQLiteBaselineResultStore(BaselineResultStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_BASELINE_RESULTS)
            con.commit()
        finally:
            con.close()

    def insert(self, result) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_BASELINE_RESULTS)
            con.execute(
                '''INSERT OR REPLACE INTO baseline_results
                   (id, session_id, name, start_date, end_date,
                    initial_capital, final_equity, stats_json)
                   VALUES (?,?,?,?,?,?,?,?)''',
                (result.id, result.session_id, result.name,
                 result.start_date, result.end_date,
                 result.initial_capital, result.final_equity,
                 json.dumps(asdict(result.stats), ensure_ascii=False)),
            )
            con.commit()
        finally:
            con.close()

    def _cols(self):
        return ('id, session_id, name, start_date, end_date, '
                'initial_capital, final_equity, stats_json')

    def get(self, result_id: str):
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                f'SELECT {self._cols()} FROM baseline_results WHERE id = ?',
                (result_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return _row_to_result(row) if row else None

    def list_for_session(self, session_id: str):
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                f'SELECT {self._cols()} '
                f'FROM baseline_results WHERE session_id = ? '
                f'ORDER BY name ASC',
                (session_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_result(r) for r in rows]
```

- [ ] **Step 4: Verify + commit**

```bash
python -m pytest tests/test_baseline_schema.py tests/test_baseline_base.py tests/test_storage_baselines.py -v
python -m pytest -q
git add data_schema/baseline_state.py backtest/baselines/ storage/base.py storage/sqlite_baselines.py tests/test_baseline_schema.py tests/test_baseline_base.py tests/test_storage_baselines.py
git commit -m "feat(p2d): BaselineResult + schema + Protocol + SQLite store"
```

---

## Task 7: Storage factory for baselines

**Files:**
- Modify: `storage/__init__.py`
- Test: `tests/test_storage_factories_p2d.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_storage_factories_p2d.py
"""Factory + set + reset for BaselineResultStore."""


def test_baselines_factory_singleton():
    import storage
    storage.reset()
    assert storage.baselines() is storage.baselines()


def test_set_baselines_overrides(tmp_path):
    import storage
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    s = SQLiteBaselineResultStore(tmp_path=tmp_path)
    storage.set_baselines(s)
    assert storage.baselines() is s


def test_reset_clears_baselines(tmp_path):
    import storage
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    storage.set_baselines(SQLiteBaselineResultStore(tmp_path=tmp_path))
    storage.reset()
    assert isinstance(storage.baselines(), SQLiteBaselineResultStore)
```

- [ ] **Step 2: Extend `storage/__init__.py`**

1. Append `BaselineResultStore` to base imports.
2. Add `_baselines: BaselineResultStore | None = None`.
3. Add `baselines()` factory function.
4. Add `set_baselines(impl)` setter.
5. Extend `reset()` to null `_baselines`.

- [ ] **Step 3: Verify + commit**

```bash
python -m pytest tests/test_storage_factories_p2d.py -v    # 3 PASSED
python -m pytest -q
git add storage/__init__.py tests/test_storage_factories_p2d.py
git commit -m "feat(p2d): storage factory baselines()"
```

---

## Task 8: Buy-and-Hold baseline

**Files:**
- Create: `backtest/baselines/buy_and_hold.py`
- Test: `tests/test_baseline_buy_and_hold.py`

**Spec:** On the first trading day, buy equal-weight across the universe (ignore fractional-share issues — use `floor(cash/N/price/100)*100` lot-aligned per stock). Hold to end. Commission applies per buy. Produce `BaselineResult` with final equity + stats via `aggregate()`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_baseline_buy_and_hold.py
"""Buy-and-hold baseline."""
from datetime import date, timedelta


def test_buy_and_hold_single_stock(monkeypatch, tmp_path):
    from backtest.baselines.buy_and_hold import run_buy_and_hold
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt)

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(10)]
    # Monotone +1%/day: 100 → 100*1.01^9 ≈ 109.37
    prices = {'X.SH': [(d, 100.0 * (1.01 ** i)) for i, d in enumerate(days)]}

    import backtest.baselines.buy_and_hold as mod
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(mod, '_load_prices',
                        lambda code, s, e: prices[code])

    result = run_buy_and_hold(
        session_id='s1', start_date='2024-03-01', end_date='2024-03-10',
        initial_capital=1_000_000.0, universe=['X.SH'],
    )
    assert result.name == 'buy_and_hold'
    assert result.stats.trade_count == 1  # day-1 buy
    # With +9% price move on full position, expect ~8-9% gross return minus fees
    assert 5.0 < result.stats.total_return_pct < 10.0


def test_buy_and_hold_equal_weight_multi_stock(monkeypatch, tmp_path):
    from backtest.baselines.buy_and_hold import run_buy_and_hold
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt)

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    prices = {
        'A.SH': [(d, 100.0) for d in days],
        'B.SZ': [(d, 100.0) for d in days],
    }
    import backtest.baselines.buy_and_hold as mod
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(mod, '_load_prices',
                        lambda code, s, e: prices[code])

    result = run_buy_and_hold(
        session_id='s2', start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0, universe=['A.SH', 'B.SZ'],
    )
    # trade_count should be 2 (one buy per stock on day 1)
    assert result.stats.trade_count == 2
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_baseline_buy_and_hold.py -v`
Expected: 2 FAIL

- [ ] **Step 3: Implement**

```python
# backtest/baselines/buy_and_hold.py
"""Buy-and-hold baseline: equal-weight at day 1, hold to end."""
from __future__ import annotations

import math
import uuid
from datetime import date, datetime

from backtest.base import BacktestStats
from backtest.book import Book
from backtest.commission import FeeModel
from backtest.stats import aggregate

from .base import BaselineResult


def _parse(s: str) -> date:
    return datetime.strptime(s, '%Y-%m-%d').date()


def _trading_days(start: str, end: str) -> list:
    import storage
    return storage.calendar().get_trading_days(_parse(start), _parse(end))


def _load_prices(code: str, start, end) -> list:
    """[(date, close), ...] ascending."""
    import storage
    from datetime import datetime as _dt
    bars = storage.kline().load_range(
        code, '1d',
        _dt(start.year, start.month, start.day),
        _dt(end.year, end.month, end.day),
    )
    return [(b.datetime.date(), float(b.close_price)) for b in bars]


def _lot_floor(shares: float) -> int:
    return max(0, int(math.floor(shares / 100.0)) * 100)


def run_buy_and_hold(*, session_id: str, start_date: str, end_date: str,
                     initial_capital: float, universe: list[str],
                     persist: bool = True) -> BaselineResult:
    days = _trading_days(start_date, end_date)
    if not days:
        raise ValueError('no trading days in range')

    start = _parse(start_date)
    end = _parse(end_date)
    price_series = {code: dict(_load_prices(code, start, end))
                    for code in universe}

    book = Book(cash=initial_capital, fee_model=FeeModel())
    entry_day = days[0]

    # Day-1 equal-weight buy
    alloc_per_stock = initial_capital / max(1, len(universe))
    for code in universe:
        px = price_series[code].get(entry_day)
        if px is None or px <= 0:
            continue
        shares_raw = alloc_per_stock / px
        shares = _lot_floor(shares_raw)
        if shares < 100:
            continue
        book.execute_buy(code, shares=shares, price=px, d=entry_day)

    # Walk the rest of days to collect daily equity for stats
    daily_records = []
    prev_equity = initial_capital
    for d in days:
        mark_prices = {}
        for code in universe:
            p = price_series[code].get(d)
            if p is None:
                past = [v for dt, v in price_series[code].items() if dt <= d]
                if past:
                    p = past[-1]
            if p is not None:
                mark_prices[code] = p
        equity = book.equity(mark_prices)
        pnl_pct = ((equity - prev_equity) / prev_equity * 100.0
                   if prev_equity > 0 else 0.0)
        prev_equity = equity
        trades_today = (len(universe) if d == entry_day else 0)
        daily_records.append({
            'date': d, 'pnl_pct': pnl_pct, 'equity': equity,
            'trade_count': trades_today, 'won': 0,
        })

    overall, _zones = aggregate(daily_records, cutoff='2099-12-31',
                                initial_capital=initial_capital)
    result = BaselineResult(
        id=str(uuid.uuid4()), session_id=session_id,
        name='buy_and_hold',
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital,
        stats=overall, final_equity=prev_equity,
    )
    if persist:
        import storage
        storage.baselines().insert(result)
    return result
```

- [ ] **Step 4: Verify + commit**

```bash
python -m pytest tests/test_baseline_buy_and_hold.py -v    # 2 PASSED
python -m pytest -q
git add backtest/baselines/buy_and_hold.py tests/test_baseline_buy_and_hold.py
git commit -m "feat(p2d): buy-and-hold baseline (equal-weight, hold to end)"
```

---

## Task 9: CSI 300 index baseline

**Files:**
- Create: `backtest/baselines/csi300.py`
- Test: `tests/test_baseline_csi300.py`

**Spec:** Track the CSI 300 index (`000300.SH`) return over the window. No trading — synthesize equity curve from index bars. Produce a `BaselineResult` with stats = index passive return. `trade_count=0`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_baseline_csi300.py
"""CSI 300 index baseline."""
from datetime import date, timedelta


def test_csi300_tracks_index(monkeypatch, tmp_path):
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt)

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    # Index 1000 → 1020 over 4 days = +2% total
    prices = [(d, 1000.0 * (1 + 0.005 * i)) for i, d in enumerate(days)]

    import backtest.baselines.csi300 as mod
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(mod, '_load_index_series', lambda s, e: prices)

    result = mod.run_csi300(
        session_id='s1', start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0,
    )
    assert result.name == 'csi300'
    assert result.stats.trade_count == 0  # passive
    # +2% gross return on 1M = 1_020_000 final
    assert abs(result.stats.final_equity - 1_020_000) < 10.0


def test_csi300_empty_days_raises(monkeypatch, tmp_path):
    import pytest
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt)

    import backtest.baselines.csi300 as mod
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: [])
    monkeypatch.setattr(mod, '_load_index_series', lambda s, e: [])
    with pytest.raises(ValueError):
        mod.run_csi300(session_id='s', start_date='2024-03-01',
                       end_date='2024-03-05', initial_capital=1_000_000.0)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_baseline_csi300.py -v`
Expected: 2 FAIL

- [ ] **Step 3: Implement**

```python
# backtest/baselines/csi300.py
"""CSI 300 index baseline: passive tracker of 000300.SH."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from backtest.stats import aggregate

from .base import BaselineResult


_INDEX_CODE = '000300.SH'


def _parse(s: str) -> date:
    return datetime.strptime(s, '%Y-%m-%d').date()


def _trading_days(start: str, end: str) -> list:
    import storage
    return storage.calendar().get_trading_days(_parse(start), _parse(end))


def _load_index_series(start, end) -> list:
    import storage
    from datetime import datetime as _dt
    bars = storage.kline().load_range(
        _INDEX_CODE, '1d',
        _dt(start.year, start.month, start.day),
        _dt(end.year, end.month, end.day),
    )
    return [(b.datetime.date(), float(b.close_price)) for b in bars]


def run_csi300(*, session_id: str, start_date: str, end_date: str,
               initial_capital: float,
               persist: bool = True) -> BaselineResult:
    days = _trading_days(start_date, end_date)
    start = _parse(start_date)
    end = _parse(end_date)
    index_bars = _load_index_series(start, end)
    index_by_day = dict(index_bars)

    if not days or not index_bars:
        raise ValueError('no index bars in range')

    base_px = index_bars[0][1]
    daily_records = []
    prev_equity = initial_capital
    for d in days:
        px = index_by_day.get(d)
        if px is None:
            past = [v for dt, v in index_bars if dt <= d]
            if past:
                px = past[-1]
        if px is None:
            continue
        # Equity = capital × (today's index / start index)
        equity = initial_capital * (px / base_px)
        pnl_pct = ((equity - prev_equity) / prev_equity * 100.0
                   if prev_equity > 0 else 0.0)
        prev_equity = equity
        daily_records.append({
            'date': d, 'pnl_pct': pnl_pct, 'equity': equity,
            'trade_count': 0, 'won': 0,
        })

    overall, _zones = aggregate(daily_records, cutoff='2099-12-31',
                                initial_capital=initial_capital)
    result = BaselineResult(
        id=str(uuid.uuid4()), session_id=session_id, name='csi300',
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital,
        stats=overall, final_equity=prev_equity,
    )
    if persist:
        import storage
        storage.baselines().insert(result)
    return result
```

- [ ] **Step 4: Verify + commit**

```bash
python -m pytest tests/test_baseline_csi300.py -v    # 2 PASSED
git add backtest/baselines/csi300.py tests/test_baseline_csi300.py
git commit -m "feat(p2d): CSI 300 index baseline (passive tracker)"
```

---

## Task 10: Equal-weight monthly rebalance baseline

**Files:**
- Create: `backtest/baselines/equal_weight.py`
- Test: `tests/test_baseline_equal_weight.py`

**Spec:** Same as buy-and-hold BUT rebalance to equal weight on the first trading day of each month. For each rebalance: compute target value per stock = equity / N, sell the overweight positions (T+1 safe — yesterday's buys can be sold next rebalance) then buy the underweight. `trade_count` accumulates.

For simplicity, rebalance by: on month-start day, sell everything that can be sold (T+1 permitting), then buy equal-weight with available cash.

- [ ] **Step 1: Write failing test**

```python
# tests/test_baseline_equal_weight.py
"""Equal-weight monthly rebalance baseline."""
from datetime import date, timedelta


def test_equal_weight_rebalances_monthly(monkeypatch, tmp_path):
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt)

    # 60 days spanning ~2 month boundaries
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(60)]
    prices = {
        'A.SH': [(d, 100.0 + i) for i, d in enumerate(days)],
        'B.SZ': [(d, 200.0 - i * 0.5) for i, d in enumerate(days)],
    }
    import backtest.baselines.equal_weight as mod
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(mod, '_load_prices',
                        lambda code, s, e: prices[code])

    result = mod.run_equal_weight(
        session_id='s1', start_date='2024-03-01', end_date='2024-04-29',
        initial_capital=1_000_000.0, universe=['A.SH', 'B.SZ'],
    )
    assert result.name == 'equal_weight'
    # Should rebalance at least twice (day 1 buy + at least one month-start)
    assert result.stats.trade_count >= 2


def test_equal_weight_single_stock_degenerate(monkeypatch, tmp_path):
    """With 1 stock, equal-weight is identical to buy-and-hold."""
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt)

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(10)]
    prices = {'X.SH': [(d, 100.0) for d in days]}
    import backtest.baselines.equal_weight as mod
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(mod, '_load_prices',
                        lambda code, s, e: prices[code])

    result = mod.run_equal_weight(
        session_id='s2', start_date='2024-03-01', end_date='2024-03-10',
        initial_capital=1_000_000.0, universe=['X.SH'],
    )
    # Trade count = 1 (no month boundary crossed within 10 days)
    assert result.stats.trade_count == 1
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_baseline_equal_weight.py -v`
Expected: 2 FAIL

- [ ] **Step 3: Implement**

```python
# backtest/baselines/equal_weight.py
"""Equal-weight monthly rebalance baseline."""
from __future__ import annotations

import math
import uuid
from datetime import date, datetime

from backtest.book import Book
from backtest.commission import FeeModel
from backtest.stats import aggregate

from .base import BaselineResult


def _parse(s: str) -> date:
    return datetime.strptime(s, '%Y-%m-%d').date()


def _trading_days(start: str, end: str) -> list:
    import storage
    return storage.calendar().get_trading_days(_parse(start), _parse(end))


def _load_prices(code: str, start, end) -> list:
    import storage
    from datetime import datetime as _dt
    bars = storage.kline().load_range(
        code, '1d',
        _dt(start.year, start.month, start.day),
        _dt(end.year, end.month, end.day),
    )
    return [(b.datetime.date(), float(b.close_price)) for b in bars]


def _lot_floor(shares: float) -> int:
    return max(0, int(math.floor(shares / 100.0)) * 100)


def _is_month_start(d: date, prev_d: date | None) -> bool:
    """First trading day we see in a new (year, month) vs the previous day."""
    if prev_d is None:
        return True
    return (d.year, d.month) != (prev_d.year, prev_d.month)


def run_equal_weight(*, session_id: str, start_date: str, end_date: str,
                     initial_capital: float, universe: list[str],
                     persist: bool = True) -> BaselineResult:
    days = _trading_days(start_date, end_date)
    if not days:
        raise ValueError('no trading days in range')

    start = _parse(start_date)
    end = _parse(end_date)
    price_series = {code: dict(_load_prices(code, start, end))
                    for code in universe}

    book = Book(cash=initial_capital, fee_model=FeeModel())
    daily_records = []
    prev_equity = initial_capital
    prev_d = None
    n = max(1, len(universe))

    for d in days:
        mark_prices = {}
        for code in universe:
            p = price_series[code].get(d)
            if p is None:
                past = [v for dt, v in price_series[code].items() if dt <= d]
                if past:
                    p = past[-1]
            if p is not None:
                mark_prices[code] = p

        trades_today = 0
        if _is_month_start(d, prev_d):
            # Sell everything sellable (T+1 permitting), then buy equal-weight
            for code in list(book.positions_view().keys()):
                pos = book.positions_view().get(code, {})
                shares = pos.get('shares', 0)
                if shares > 0 and code in mark_prices:
                    fill = book.execute_sell(
                        code, shares=shares, price=mark_prices[code], d=d,
                    )
                    if fill:
                        trades_today += 1

            equity_now = book.equity(mark_prices)
            target_per_stock = equity_now / n
            for code in universe:
                px = mark_prices.get(code)
                if px is None or px <= 0:
                    continue
                shares_raw = target_per_stock / px
                shares = _lot_floor(shares_raw)
                if shares < 100:
                    continue
                fill = book.execute_buy(code, shares=shares, price=px, d=d)
                if fill:
                    trades_today += 1

        equity = book.equity(mark_prices)
        pnl_pct = ((equity - prev_equity) / prev_equity * 100.0
                   if prev_equity > 0 else 0.0)
        prev_equity = equity
        prev_d = d
        daily_records.append({
            'date': d, 'pnl_pct': pnl_pct, 'equity': equity,
            'trade_count': trades_today, 'won': 0,
        })

    overall, _zones = aggregate(daily_records, cutoff='2099-12-31',
                                initial_capital=initial_capital)
    result = BaselineResult(
        id=str(uuid.uuid4()), session_id=session_id, name='equal_weight',
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital,
        stats=overall, final_equity=prev_equity,
    )
    if persist:
        import storage
        storage.baselines().insert(result)
    return result
```

- [ ] **Step 4: Verify + commit**

```bash
python -m pytest tests/test_baseline_equal_weight.py -v    # 2 PASSED
git add backtest/baselines/equal_weight.py tests/test_baseline_equal_weight.py
git commit -m "feat(p2d): equal-weight monthly rebalance baseline"
```

---

## Task 11: BaselineRunner orchestrator

**Files:**
- Create: `backtest/baselines/runner.py`
- Test: `tests/test_baseline_runner.py`

**Spec:** `run_all(session_id, start_date, end_date, initial_capital, universe)` runs all three baselines in turn under the same session_id, returning `list[BaselineResult]`. This is the convenience entry point used by E2E tests and downstream comparison UIs.

- [ ] **Step 1: Write failing test**

```python
# tests/test_baseline_runner.py
"""BaselineRunner orchestrator."""
from datetime import date, timedelta


def test_run_all_three_baselines(monkeypatch, tmp_path):
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    bl = SQLiteBaselineResultStore(tmp_path=tmp_path); bl.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt); storage.set_baselines(bl)

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    stock_prices = [(d, 100.0 + i) for i, d in enumerate(days)]
    index_prices = [(d, 1000.0 + i * 2) for i, d in enumerate(days)]

    import backtest.baselines.buy_and_hold as bh_mod
    import backtest.baselines.equal_weight as ew_mod
    import backtest.baselines.csi300 as csi_mod
    monkeypatch.setattr(bh_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(bh_mod, '_load_prices', lambda c, s, e: stock_prices)
    monkeypatch.setattr(ew_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(ew_mod, '_load_prices', lambda c, s, e: stock_prices)
    monkeypatch.setattr(csi_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(csi_mod, '_load_index_series', lambda s, e: index_prices)

    from backtest.baselines.runner import run_all
    results = run_all(
        session_id='s1', start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0, universe=['X.SH'],
    )
    assert {r.name for r in results} == {'buy_and_hold', 'equal_weight',
                                          'csi300'}

    # All persisted under session
    stored = storage.baselines().list_for_session('s1')
    assert len(stored) == 3
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_baseline_runner.py -v`
Expected: 1 FAIL

- [ ] **Step 3: Implement**

```python
# backtest/baselines/runner.py
"""Run all three MVP baselines under a shared session."""
from __future__ import annotations

from .buy_and_hold import run_buy_and_hold
from .csi300 import run_csi300
from .equal_weight import run_equal_weight


def run_all(*, session_id: str, start_date: str, end_date: str,
            initial_capital: float, universe: list[str]) -> list:
    common = dict(
        session_id=session_id,
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital,
    )
    results = []
    # Buy and hold
    results.append(run_buy_and_hold(universe=universe, **common))
    # Equal weight
    results.append(run_equal_weight(universe=universe, **common))
    # CSI 300 (index-only, no universe arg)
    results.append(run_csi300(**common))
    return results
```

- [ ] **Step 4: Verify + commit**

```bash
python -m pytest tests/test_baseline_runner.py -v    # 1 PASSED
python -m pytest -q
git add backtest/baselines/runner.py tests/test_baseline_runner.py
git commit -m "feat(p2d): BaselineRunner.run_all orchestrator"
```

---

## Task 12: AgentStore.update_health + rating classifier

**Files:**
- Modify: `storage/base.py` (append method to AgentStore Protocol)
- Modify: `storage/sqlite_agents.py` (implement `update_health`)
- Create: `agents/rating.py` — pure rating classifier
- Test: `tests/test_rating.py`, `tests/test_storage_agents.py` (append)

**Spec for classifier (Spec § 8.2):**
- health ≥ 90 → `'A+'`
- 80 ≤ health < 90 → `'A'`
- 60 ≤ health < 80 → `'B'`
- 0 ≤ health < 60 → `'C'`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_rating.py
"""Trust rating classifier."""


def test_a_plus_at_90():
    from agents.rating import classify_rating
    assert classify_rating(100) == 'A+'
    assert classify_rating(90) == 'A+'


def test_a_range():
    from agents.rating import classify_rating
    assert classify_rating(89) == 'A'
    assert classify_rating(80) == 'A'


def test_b_range():
    from agents.rating import classify_rating
    assert classify_rating(79) == 'B'
    assert classify_rating(60) == 'B'


def test_c_range():
    from agents.rating import classify_rating
    assert classify_rating(59) == 'C'
    assert classify_rating(0) == 'C'


def test_clamps_negative_to_c():
    from agents.rating import classify_rating
    assert classify_rating(-5) == 'C'
```

Append to `tests/test_storage_agents.py`:

```python
def test_update_health_persists(tmp_path):
    import storage
    from storage.sqlite_personas import SQLitePersonaStore
    from storage.sqlite_agents import SQLiteAgentStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    from storage.sqlite_models import SQLiteModelStore
    from personas import seed as seed_personas

    for cls, setter in [
        (SQLitePersonaStore, 'set_personas'),
        (SQLiteAgentStore, 'set_agents'),
        (SQLitePromptVersionStore, 'set_prompt_versions'),
        (SQLiteModelStore, 'set_models'),
    ]:
        inst = cls(tmp_path=tmp_path); inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()
    seed_personas()

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='HealthTest',
    )
    storage.agents().update_health(agent.id, health=75, rating='B')
    reloaded = storage.agents().get(agent.id)
    assert reloaded.health_score == 75
    assert reloaded.trust_rating == 'B'
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_rating.py tests/test_storage_agents.py -v`
Expected: rating 5 FAIL + agents 1 FAIL

- [ ] **Step 3: Implement**

```python
# agents/rating.py
"""Trust rating classifier (Spec § 8.2)."""
from __future__ import annotations


def classify_rating(health: int) -> str:
    h = max(0, int(health))
    if h >= 90:
        return 'A+'
    if h >= 80:
        return 'A'
    if h >= 60:
        return 'B'
    return 'C'
```

Append to `AgentStore` Protocol in `storage/base.py`:

```python
    def update_health(self, agent_id: str, health: int,
                      rating: str) -> None:
        """Persist health_score + trust_rating on the agent row."""
        ...
```

Append method to `SQLiteAgentStore` in `storage/sqlite_agents.py` (read current file first — find the class and add):

```python
    def update_health(self, agent_id: str, health: int,
                      rating: str) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(
                '''UPDATE agents
                   SET health_score = ?, trust_rating = ?
                   WHERE id = ?''',
                (int(health), rating, agent_id),
            )
            con.commit()
        finally:
            con.close()
```

- [ ] **Step 4: Verify + commit**

```bash
python -m pytest tests/test_rating.py tests/test_storage_agents.py -v
python -m pytest -q
git add agents/rating.py storage/base.py storage/sqlite_agents.py tests/test_rating.py tests/test_storage_agents.py
git commit -m "feat(p2d): trust rating classifier + AgentStore.update_health"
```

---

## Task 13: Health score computation

**Files:**
- Modify: `agents/rating.py` (add `compute_health`)
- Test: `tests/test_rating.py` (append)

**Spec (Spec § 8.1):**
```
health = max(0, 100 - violations_7d * 3 - backtest_deviation_pts * 2 - parse_failures_7d * 1)
```

For MVP:
- `violations_7d` = count of `audit_log` rows with `kind='validation'` AND `details.outcome in ('rejected','modified')` for this agent in last 7 calendar days.
- `backtest_deviation_pts = 0` (no live deployment yet).
- `parse_failures_7d` = count of `audit_log` rows with `kind='parse_failure'` for this agent in last 7 days. (We don't emit these yet; accept 0.)

- [ ] **Step 1: Append failing tests to `tests/test_rating.py`**

```python
def test_compute_health_from_audit(tmp_path):
    """Health formula: 100 - 3*violations - 2*live_dev - 1*parse_failures."""
    import storage
    from storage.sqlite_audit import SQLiteAuditStore
    from validation.base import AuditEntry
    au = SQLiteAuditStore(tmp_path=tmp_path); au.init_schema()
    storage.set_audit(au)

    # Seed: 3 rejected + 2 modified + 4 approved over arbitrary dates today
    for _ in range(3):
        au.log(AuditEntry(kind='validation', agent_id='a1',
                          details={'outcome': 'rejected'}))
    for _ in range(2):
        au.log(AuditEntry(kind='validation', agent_id='a1',
                          details={'outcome': 'modified'}))
    for _ in range(4):
        au.log(AuditEntry(kind='validation', agent_id='a1',
                          details={'outcome': 'approved'}))

    from agents.rating import compute_health
    h = compute_health('a1')
    # 5 violations * 3 = 15; 0 live_dev; 0 parse_failures → 100 - 15 = 85
    assert h == 85


def test_compute_health_floors_at_zero(tmp_path):
    import storage
    from storage.sqlite_audit import SQLiteAuditStore
    from validation.base import AuditEntry
    au = SQLiteAuditStore(tmp_path=tmp_path); au.init_schema()
    storage.set_audit(au)

    # 40 rejected → 40*3=120 → would be -20 → clamp to 0
    for _ in range(40):
        au.log(AuditEntry(kind='validation', agent_id='a1',
                          details={'outcome': 'rejected'}))
    from agents.rating import compute_health
    assert compute_health('a1') == 0


def test_compute_health_no_data_is_100():
    import storage
    storage.reset()
    # Fresh store — no audit rows
    from agents.rating import compute_health
    assert compute_health('nope') == 100
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_rating.py -v`
Expected: 3 new tests FAIL

- [ ] **Step 3: Extend `agents/rating.py`**

Append:

```python
from datetime import datetime, timedelta


def compute_health(agent_id: str,
                   *, live_deviation_pts: int = 0,
                   window_days: int = 7) -> int:
    """Health score per Spec § 8.1.

    violations_7d + parse_failures_7d come from audit_log. live_deviation_pts
    is a caller-supplied measure (0 in MVP since live mode is not wired).
    """
    import storage
    audit = storage.audit()
    rows = audit.query_by_agent(agent_id, limit=10_000)
    # Filter by timestamp within window (keeps the store interface simple)
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    violations = 0
    parse_failures = 0
    for r in rows:
        ts = r.get('timestamp')
        try:
            dt = datetime.strptime(ts[:19], '%Y-%m-%d %H:%M:%S')
        except Exception:
            dt = datetime.utcnow()  # fall back to now (include)
        if dt < cutoff:
            continue
        if r['kind'] == 'validation' and r.get('details', {}).get('outcome') \
                in ('rejected', 'modified'):
            violations += 1
        elif r['kind'] == 'parse_failure':
            parse_failures += 1
    raw = 100 - violations * 3 - live_deviation_pts * 2 - parse_failures
    return max(0, raw)
```

- [ ] **Step 4: Verify + commit**

```bash
python -m pytest tests/test_rating.py -v
python -m pytest -q
git add agents/rating.py tests/test_rating.py
git commit -m "feat(p2d): compute_health from audit_log (Spec § 8.1)"
```

---

## Task 14: E2E test — agent + baselines + divergence + health

**Files:**
- Create: `tests/test_p2d_e2e.py`

**Responsibility:** Run the full pipeline end-to-end:
1. Create an agent, run a 5-day backtest via `BacktestRunner`
2. Run `baselines.runner.run_all()` on the same session
3. Compute `compute_health` + `classify_rating` for the agent, persist via `update_health`
4. Assert: 1 `backtest_results` row + 3 `baseline_results` rows + agent has health/rating persisted

- [ ] **Step 1: Write failing test**

```python
# tests/test_p2d_e2e.py
"""P2d E2E — agent + baselines + rating."""
from datetime import date, timedelta
import pytest


@pytest.fixture
def wired_full(tmp_path):
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.sqlite_audit import SQLiteAuditStore
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    from storage.sqlite_personas import SQLitePersonaStore
    from storage.sqlite_agents import SQLiteAgentStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    from storage.sqlite_models import SQLiteModelStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    from storage.sqlite_calendar import SQLiteCalendarStore
    from validation.base import DEFAULT_REDLINES

    for cls, setter in [
        (SQLiteRedLineStore,        'set_redline'),
        (SQLiteStockStatusStore,    'set_stock_status'),
        (SQLiteAuditStore,          'set_audit'),
        (SQLiteLLMDecisionCache,    'set_llm_cache'),
        (SQLitePersonaStore,        'set_personas'),
        (SQLiteAgentStore,          'set_agents'),
        (SQLitePromptVersionStore,  'set_prompt_versions'),
        (SQLiteModelStore,          'set_models'),
        (SQLiteBacktestResultStore, 'set_backtests'),
        (SQLiteBaselineResultStore, 'set_baselines'),
        (SQLiteCalendarStore,       'set_calendar'),
    ]:
        inst = cls(tmp_path=tmp_path); inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()

    from validation import rules
    rules.reset()
    from validation.handlers.position_max_pct import Handler as H1
    from validation.handlers.ban_st import Handler as H2
    from validation.handlers.max_holdings import Handler as H3
    from validation.handlers.daily_loss_limit_pct import Handler as H4
    rules.register(H1()); rules.register(H2())
    rules.register(H3()); rules.register(H4())

    storage.redline().set({**DEFAULT_REDLINES, 'position_max_pct': 15.0})
    from personas import seed as seed_personas
    seed_personas()
    return storage


def test_e2e_agent_plus_baselines_plus_rating(wired_full, monkeypatch):
    import storage
    from backtest.runner import BacktestRunner
    from backtest.baselines.runner import run_all
    from agents.rating import compute_health, classify_rating
    from llm.mock import MockLLM

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='E2E',
    )

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    stock_prices = [(d, 100.0 + i * 0.5) for i, d in enumerate(days)]
    index_prices = [(d, 1000.0 + i) for i, d in enumerate(days)]

    import backtest.runner as run_mod
    import backtest.baselines.buy_and_hold as bh_mod
    import backtest.baselines.equal_weight as ew_mod
    import backtest.baselines.csi300 as csi_mod
    monkeypatch.setattr(run_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(run_mod, '_load_daily_closes', lambda c, s, e: stock_prices)
    monkeypatch.setattr(bh_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(bh_mod, '_load_prices', lambda c, s, e: stock_prices)
    monkeypatch.setattr(ew_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(ew_mod, '_load_prices', lambda c, s, e: stock_prices)
    monkeypatch.setattr(csi_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(csi_mod, '_load_index_series', lambda s, e: index_prices)

    hold = {'tool_calls': [{'id': 'c', 'name': 'place_decision',
                            'input': {'action': 'hold',
                                      'reason': 'nothing to trade today',
                                      'thinking': 't'}}],
            'stop_reason': 'tool_use'}
    llm = MockLLM([hold] * 5)
    agent_result = BacktestRunner(llm=llm).run(
        session_id='e2e-p2d', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )

    baselines = run_all(
        session_id='e2e-p2d',
        start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )

    # Assert 1: all 3 baselines persisted under the session
    assert len(storage.baselines().list_for_session('e2e-p2d')) == 3

    # Assert 2: agent backtest persisted
    assert storage.backtests().get(agent_result.id) is not None

    # Assert 3: health + rating computed and persisted
    health = compute_health(agent.id)
    rating = classify_rating(health)
    storage.agents().update_health(agent.id, health=health, rating=rating)

    reloaded = storage.agents().get(agent.id)
    assert reloaded.health_score == health
    assert reloaded.trust_rating == rating
```

- [ ] **Step 2: Verify**

Run: `python -m pytest tests/test_p2d_e2e.py -v`
Expected: 1 PASSED

Full suite: `python -m pytest -q`
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add tests/test_p2d_e2e.py
git commit -m "test(p2d): E2E — agent + baselines + divergence + health+rating"
```

---

## Task 15: Full suite verification

- [ ] **Step 1: Run**

```bash
python -m pytest -q
```

Expected: ~297 (P2c) + ~50 new ≈ ~347 total, all green.

- [ ] **Step 2: Sanity-check commit log**

```bash
git log --oneline main..HEAD
```

Expected: ~14 `feat/fix/test(p2d):` + 1 plan commit.

---

## Post-plan verification

Integration invariants to check by eye:
- Book's T+1 enforces across runner invocations (each day's book is preserved between LLM calls)
- `divergence_flag` feeds quality_gate correctly (`divergence_flag=True` → `max_divergence_flag` criterion fails → label='fail')
- `compute_health` uses current-time window (can't mock `datetime.utcnow` trivially — the timestamp in audit_log is the store's `CURRENT_TIMESTAMP`, which will be near-now for freshly-inserted rows, so the 7-day window catches everything)
- Baselines ignore RedLine/ValidationEngine (they're passive benchmarks, not validated agents)

**Not in P2d scope** (future):
- **P2e:** `/api/backtests`, `/api/baselines`, `/api/agents/<id>/health` endpoints + SSE progress stream + RiskMonitor / BacktestResult frontend panels + live trading hookup
- **Deferred:** real tool execution in the agent tool loop (still `{'ack': true}`), T+1 UI indicator, intraday backtest data, health score incorporation of live performance deviation, multi-agent parallel execution

## Execution handoff

> Plan complete at `docs/superpowers/plans/2026-04-22-p2d-baselines-rating.md`.
>
> Two execution options:
> 1. Subagent-Driven (recommended) — fresh subagent per task with two-stage review
> 2. Inline execution — batch with manual checkpoints
>
> Which approach?
