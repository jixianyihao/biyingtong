# Design Memo — VnpyBacktestRunner Integration

> **Scope:** Batch B Task 1 output. Read-only investigation of vnpy_portfoliostrategy
> BacktestingEngine to resolve concrete integration questions BEFORE writing the new
> `VnpyBacktestRunner` (Task 3). NO code changes here — memo only.
>
> **Reviewed tree:** `feature/framework-first-batch-b` (HEAD `7457fcf`), working
> against installed `vnpy_portfoliostrategy` wheel on this host.
>
> **Related plan:** `docs/superpowers/plans/2026-04-24-framework-first-batch-b-vnpy-runner.md`

---

## 1. LLMPortfolioStrategy state audit

File: `backtest/strategy.py` (79 lines).

### What exists today

- Inherits `vnpy_portfoliostrategy.StrategyTemplate` (falls back to empty base when
  vnpy is not importable so unit tests in isolated contexts do not explode).
- `__init__` constructs an `AgentRunner`, pulls `agent_id`, `initial_capital`, and
  `llm` from the `setting` dict, initializes in-memory mirrors `self._cash` and
  `self._positions`, and an empty `self.daily_decisions: list`.
- `on_init` / `on_start` — **no-ops**.
- `on_bars(bars)` — calls `_process_bars(bars)` and appends
  `(date_str, decisions)` to `self.daily_decisions`. **That is all.**
- `_extract_date(bars)` — takes the `.datetime` of the first bar in the dict.
- `_process_bars(bars)`:
  1. Builds `mark_prices` dict keyed by our biyingtong code (`'600519.SH'`).
  2. Builds `portfolio` via `backtest.portfolio_adapter.build_portfolio(cash=self._cash, positions=self._positions, mark_prices=...)`.
  3. Calls `self._runner.run_day(agent_id, date, portfolio, market_context={}, mark_prices)`.
  4. Returns the decisions list verbatim.
- Helper `vt_to_biyingtong(symbol, exchange)` converts `'600519'+'SSE' → '600519.SH'`.

### What is missing (Task 2 scope)

| Missing piece                                                  | Impact                                            |
|---------------------------------------------------------------|---------------------------------------------------|
| Decision → vnpy order translation (`self.buy` / `self.sell`) | vnpy trade ledger stays empty; no positions move |
| Reverse `biyingtong_to_vt` helper                              | Cannot look up the right bar in `bars` dict      |
| T+1 enforcement                                                | Same-day sells would fill (futures semantics)    |
| Local cash/position mirror update after fills                 | `portfolio` passed to LLM next day is stale      |
| `on_trade` / `update_trade` override (optional)                | To keep local mirrors in sync with engine trades |
| `_bought_today` reset at `on_bars` entry                       | Required for T+1 bookkeeping                     |
| Per-day thinking capture hook                                  | `runner.last_thinking` is only the LAST day      |

### Reverse converter spec

```python
_BIYINGTONG_TO_EXCHANGE = {'SH': 'SSE', 'SZ': 'SZSE'}

def biyingtong_to_vt(code: str) -> str:
    """'600519.SH' → '600519.SSE'; '000858.SZ' → '000858.SZSE'."""
    bare, _, suffix = code.partition('.')
    return f'{bare}.{_BIYINGTONG_TO_EXCHANGE.get(suffix.upper(), suffix.upper())}'
```

Round-trip parity checks:

| Input          | `biyingtong_to_vt` | `vt_to_biyingtong` back |
|----------------|--------------------|-------------------------|
| `600519.SH`    | `600519.SSE`       | `600519.SH`             |
| `000858.SZ`    | `000858.SZSE`      | `000858.SZ`             |
| `300750.SZ`    | `300750.SZSE`      | `300750.SZ`             |

Note: indices like `000300.SH` follow the same rule because `_exchange_for` in
`storage/sqlite_kline.py` already prefers the explicit suffix over the
numeric-prefix heuristic.

---

## 2. BacktestingEngine API reference

From `inspect.signature` on the installed wheel:

```python
BacktestingEngine.set_parameters(
    self,
    vt_symbols: list[str],
    interval: vnpy.trader.constant.Interval,
    start: datetime.datetime,
    rates: dict[str, float],
    slippages: dict[str, float],
    sizes: dict[str, float],
    priceticks: dict[str, float],
    capital: float = 0,
    end: datetime.datetime | None = None,
    risk_free: float = 0,
    annual_days: int = 240,
) -> None
```

Every dict keyed by vt_symbol is **required for all symbols in `vt_symbols`** — a
missing key will KeyError deep inside `cross_limit_order` or `calculate_pnl`.

```python
BacktestingEngine.add_strategy(
    self,
    strategy_class: type[StrategyTemplate],
    setting: dict,
) -> None
```

Setting dict is passed through to `strategy.__init__(strategy_engine, strategy_name, vt_symbols, setting)`.
Our keys: `{'agent_id', 'llm', 'initial_capital'}`.

```python
BacktestingEngine.load_data(self) -> None
```

Calls `vnpy_portfoliostrategy.backtesting.load_bar_data` per vt_symbol. That
helper queries vnpy's configured SQLite database. For daily bars (our case) it
loads the whole range in one call; for minute bars it chunks 30-day windows. It
populates `self.history_data: dict[(dt, vt_symbol), BarData]` and a sorted set
`self.dts`. **No return value.** Silently logs progress via `self.output`.

```python
BacktestingEngine.run_backtesting(self) -> None
```

Synchronous. Two loops over `self.dts`:
1. Warm-up phase — keeps running until `day_count >= self.days` to satisfy
   `load_bars(days, interval)` prefetch. Strategy's `trading` flag stays False.
2. Main phase — continues through the remaining dts with `strategy.trading=True`.

For every dt:
- Build `bars: dict[vt_symbol, BarData]` with fill-forward for missing symbols
  (synthesizes a flat bar from previous close).
- `cross_limit_order()` — matches any outstanding limit orders against CURRENT
  bar's low/high using `bar.open_price` as the best price.
- `strategy.on_bars(bars)` — strategy can submit new orders here; they join the
  active queue and will be matched in the NEXT bar's `cross_limit_order()`.
- `update_daily_close(self.bars, dt)` — pushes a new `PortfolioDailyResult`.

```python
BacktestingEngine.calculate_result(self) -> pandas.DataFrame
```

Indexed by `date`. Columns:
`['trade_count', 'turnover', 'commission', 'slippage', 'trading_pnl', 'holding_pnl', 'total_pnl', 'net_pnl']`.
After `calculate_statistics`, the same df has columns `balance`, `return`,
`highlevel`, `drawdown`, `ddpercent` added in-place.

Returns `None` if `self.trades` is empty (edge case we must handle).

```python
BacktestingEngine.calculate_statistics(df=None, output=True) -> dict
```

Keys (verified by reading source):

```
start_date, end_date, total_days, profit_days, loss_days,
capital, end_balance,
max_drawdown, max_ddpercent, max_drawdown_duration,
total_net_pnl, daily_net_pnl,
total_commission, daily_commission,
total_slippage, daily_slippage,
total_turnover, daily_turnover,
total_trade_count, daily_trade_count,
total_return, annual_return, daily_return, return_std,
sharpe_ratio, return_drawdown_ratio,
```

**Edge case:** if any daily `balance <= 0` the function returns a dict with all
numeric fields at their initial `0`/`""` values (no real stats). We must detect
this (`stats.get('end_balance', 0) == 0`) and fall back gracefully.

Sharpe formula: `(daily_return - daily_risk_free) / return_std * sqrt(annual_days)` where `annual_days=240` default.
Our hand-rolled `stats.py::_sharpe` uses `sqrt(252)` and no risk-free. **Known
divergence** — parity test must tolerate.

```python
BacktestingEngine.get_all_trades(self) -> list[TradeData]
```

Returns `list(self.trades.values())`. `TradeData` fields:
`symbol, exchange, orderid, tradeid, direction, offset, price, volume, datetime,
gateway_name`. `vt_symbol`/`vt_orderid`/`vt_tradeid` are derived in
`__post_init__`.

```python
BacktestingEngine.get_all_daily_results(self) -> list[PortfolioDailyResult]
```

Returns `list(self.daily_results.values())`. Each `PortfolioDailyResult` has:

- `date: date`
- `close_prices: dict[vt_symbol, float]`
- `pre_closes: dict[vt_symbol, float]`
- `start_poses: dict[vt_symbol, float]`
- `end_poses: dict[vt_symbol, float]`
- `contract_results: dict[vt_symbol, ContractDailyResult]`
- `trade_count: int`
- `turnover, commission, slippage: float`
- `trading_pnl, holding_pnl, total_pnl, net_pnl: float`

**Does NOT expose a `balance` nor a `cash` field directly.** Balance is only
computed inside `calculate_statistics` as the cumulative `net_pnl.cumsum() +
capital` applied to the df. For our `daily_records[i].equity` we must reconstruct
it ourselves:

```python
running = capital
daily_records = []
for r in engine.get_all_daily_results():
    running += r.net_pnl
    daily_records.append({'date': r.date, 'equity': running, ...})
```

There is **no separate cash tracking** in vnpy portfolio engine — it tracks
balance only. For `daily_records.cash` we must compute it in
`LLMPortfolioStrategy` (mirror attribute maintained on every fill) and snapshot
into an auxiliary `daily_cash: dict[date, float]` that `VnpyBacktestRunner`
reads.

---

## 3. vt_symbol ↔ biyingtong code mapping

Verified empirically:

```
BarData(symbol='600519', exchange=Exchange.SSE).vt_symbol == '600519.SSE'
Exchange.SSE.value   == 'SSE'
Exchange.SZSE.value  == 'SZSE'
```

| biyingtong code | vt_symbol     | Exchange enum  |
|-----------------|---------------|----------------|
| `600519.SH`     | `600519.SSE`  | `Exchange.SSE` |
| `000858.SZ`     | `000858.SZSE` | `Exchange.SZSE`|
| `300750.SZ`     | `300750.SZSE` | `Exchange.SZSE`|
| `000300.SH`     | `000300.SSE`  | `Exchange.SSE` |

`BacktestingEngine.set_parameters` takes a list of vt_symbols in the
`'{bare}.{EXCHANGE_VALUE}'` form, which matches what our storage already writes.

Our existing `vt_to_biyingtong` lives at `backtest/strategy.py:16`. The reverse
helper (`biyingtong_to_vt`) is NOT yet implemented — Task 2 adds it.

---

## 4. BarData compatibility check

`storage/sqlite_kline.py` writes via `vnpy_sqlite.Database().save_bar_data(bars)`
into the `dbbardata` peewee table. Bars are expected to already carry the right
`Exchange` enum. Helper `_exchange_for(code)` maps `.SH → Exchange.SSE` /
`.SZ → Exchange.SZSE`. The loader (`load_bar_data` inside vnpy_portfoliostrategy)
queries the same Database singleton with `(bare, Exchange.SSE, Interval.DAILY,
start, end)` and vnpy_portfoliostrategy instantiates `BacktestingEngine`'s
`load_data()` over the same path.

**Compatibility verdict:** ✅ Our existing kline rows should be readable by
`engine.load_data()` without format changes, as long as:

1. The caller uses the same `vnpy.trader.utility.get_file_path` DB location
   (both sides call `scripts/setup/vnpy_config::configure` before touching the
   DB, which points at the same `.db` file).
2. Symbols in `set_parameters` use `bare.EXCHANGE_VALUE` form (verified, Section 3).
3. Bars stored in the DB used `Interval.DAILY`, not some other granularity.
   `storage/sqlite_kline.py::_interval` only allows `1d / 1w / 1M`.

**Open concern:** our real data only covers HS300 2025-04-01 ~ 2026-04-01 (per
`MEMORY.md kline_data_coverage`) + `000300.SH` for 2026-04-22. A parity test that
straddles that window will have fill-forward bars for some tickers; vnpy's
`new_bars` synthesizes a flat-close bar for those dates, which is fine but MAY
cause trade_count divergence against the old runner if that one skips symbols
without same-day close.

---

## 5. T+1 enforcement strategy

vnpy's portfolio engine is built for futures: `buy` and `sell` freely settle on
the same bar. For A-share T+1 we must gate sells inside `LLMPortfolioStrategy`.

### Simple bookkeeping (recommended for Batch B)

```python
def on_bars(self, bars):
    self._bought_today = {}  # RESET at start of every day
    decisions = self._process_bars(bars)
    self.daily_decisions.append((self._extract_date(bars), decisions))

    for dec in decisions:
        action = dec.get('action')
        code = dec.get('code')
        shares = int(dec.get('shares') or 0)
        if shares <= 0 or not code or action not in ('buy', 'sell'):
            continue
        vt_symbol = biyingtong_to_vt(code)
        bar = bars.get(vt_symbol)
        if bar is None:
            continue  # no data this day; skip
        price = float(bar.close_price)

        if action == 'buy':
            self.buy(vt_symbol, price, shares)
            self._bought_today[vt_symbol] = (
                self._bought_today.get(vt_symbol, 0) + shares
            )
        elif action == 'sell':
            held_today = self._bought_today.get(vt_symbol, 0)
            sellable = max(0, self.get_pos(vt_symbol) - held_today)
            if sellable <= 0:
                continue
            volume = min(shares, sellable)
            self.sell(vt_symbol, price, volume)
```

### Why this works (and its limits)

- `self.get_pos(vt_symbol)` reads vnpy's maintained integer position.
- Buys submitted on day N will cross on day N+1 open (vnpy default). By the
  time `on_bars(day N+1)` runs, the trade has already been posted via
  `update_trade`, `get_pos` is incremented, and `_bought_today` is cleared.
  So a buy-then-sell across two days works natively.
- Same-day buy + sell: `self.buy` at day N queues the order → `cross_limit_order`
  crosses it at day N+1 open. Between submission and matching `get_pos` still
  shows 0 for that symbol; the `_bought_today` guard ONLY matters if the LLM
  issues a same-bar `sell` on a position it genuinely already held. In that
  case we refuse because the LLM has no way to tell us which lot is "today's
  buy" vs "prior holding."
- **Caveat:** this is A-share semantics approximated on a T+0 engine. If a trade
  doesn't cross (e.g. limit-down next day), `_bought_today` bookkeeping will be
  wrong — but vnpy's daily engine with `bar.low_price = long_cross_price` and
  our `price = close_price` means every order does cross. Acceptable for MVP.

---

## 6. Matching price decision — recommend (b)

vnpy queues orders submitted in `on_bars` for the NEXT bar's
`cross_limit_order`, which uses `bar.open_price` as the best price (subject to
price crossing `bar.low_price`). Our legacy `BacktestRunner.run` fills at
**today's close** in the same bar the LLM decided.

### Option (a): Force vnpy to match at close — NOT recommended

Would require overriding `cross_limit_order` or post-processing trades after
`run_backtesting` to rewrite `TradeData.price`. This fights vnpy's design
(post-fill state would be inconsistent — `trading_pnl` computed by
`ContractDailyResult.calculate_pnl` uses `trade.price`). Dangerous.

### Option (b): Accept 1-bar offset + document tolerance — recommended

- Document the divergence explicitly in `test_runner_parity.py` docstring.
- Parity test tolerance: `total_return_pct` within 0.5%, `final_equity` within
  1%, `trade_count` **exact** (decision count is deterministic from the LLM
  script; both runners should emit the same count even if fill prices differ by
  one bar).
- Accept one-bar-shifted fill prices as a product decision: vnpy is industry
  standard; our old "fill-at-close-same-day" was an MVP shortcut.
- If parity diverges beyond tolerance in practice, we can later submit orders
  using `bar.open_price` of the NEXT bar looked up from `self.history_data`
  (but that's a refinement, not Batch B).

**Decision for Batch B: (b).** Matching semantics differ; tolerances relaxed in
parity test with commentary.

---

## 7. Zone-stats post-processing approach

`engine.calculate_statistics(df, output=False)` is zone-blind. We still need
pollution/buffer/clean split driven by `model.training_cutoff`.

### Two candidate approaches

**Approach A — our existing `stats.aggregate()` over synthesized daily_records:**
Reconstruct a `daily_records` list from `get_all_daily_results()` +
`engine.trades` that matches the old shape (`{date, equity, cash, pnl_pct,
trade_count, won}`), then call `aggregate(daily_records, cutoff, initial_capital)`.
This reuses `cutoff.classify_date` and keeps the ZoneStats shape identical
across runners. **Downside:** overall-stats will come from our hand-rolled
`_sharpe` / `_max_drawdown_pct`, not from `engine.calculate_statistics`.

**Approach B — re-invoke `engine.calculate_statistics` per zone on a filtered df:**
Slice `engine.daily_df` by date → feed each slice to `calculate_statistics`.
This keeps vnpy's formulas end-to-end but **doubles the "capital" assumption**:
vnpy's `total_return = (end_balance / self.capital - 1) * 100`, computed off the
engine's initial `capital`, not the zone-starting balance. Zone-specific
`total_return` from vnpy would be misleading (it measures "return from engine
start," not "return during this zone").

### Decision — Hybrid

- **Overall `BacktestStats`:** use `engine.calculate_statistics()` verbatim,
  mapped to our dataclass (Section 8). Matches Task 6's stated goal
  ("use engine.calculate_statistics exclusively").
- **Zone stats:** Approach A — reconstruct `daily_records` (cheap) and call our
  existing `stats.aggregate(days, cutoff, initial_capital)`. Zones already have
  a coherent semantic ("stats restricted to this date range") and our
  `_stats_from_days` uses `initial_capital` as denominator, which makes
  pollution-zone `total_return_pct` meaningful. Helper lives in `vnpy_runner.py`
  as `_zone_stats_from_daily_results(daily_results, cutoff, initial_capital)`.

Rationale: vnpy's `calculate_statistics` is optimized for full-window analytics,
not cross-cutoff slices. Our hand-rolled zone stats are narrower by scope
(only zone-level Sharpe + MaxDD + trade_count + win_rate, as currently serialized
in `ZoneStats.stats`), so the mild mismatch with the overall `stats` is
acceptable and honest.

---

## 8. Output mapping table (vnpy → BacktestResult)

Target dataclass: `backtest.base.BacktestResult` + nested `BacktestStats` +
`ZoneStats[]`.

### BacktestStats ← engine.calculate_statistics

| BacktestStats field    | vnpy stats key          | Notes                                         |
|------------------------|-------------------------|-----------------------------------------------|
| `sharpe`               | `sharpe_ratio`          | annualization differs (240 vs 252) — documented |
| `max_drawdown_pct`     | `max_ddpercent`         | vnpy returns NEGATIVE percent; OK, matches our sign convention |
| `trade_count`          | `total_trade_count`     | cast to int                                   |
| `win_rate`             | — (no direct key)       | compute from trades: wins / trade_count \* 100. See note below |
| `max_daily_loss_pct`   | — (no direct key)       | compute from `df['return'].min() * 100` (or reconstruct) |
| `total_return_pct`     | `total_return`          | already in percent                            |
| `final_equity`         | `end_balance`           | float                                         |

**Win rate computation:** vnpy has no notion of "winning trade." Legacy
`BacktestRunner` defines `won` as "sell price > avg cost basis before the
sell." Reproduce by iterating `engine.get_all_trades()` — for each SELL trade
with a matching BUY prior, compare `trade.price` to running average cost.

**Max daily loss:** cheapest path is `df['return'].min() * 100` after
`calculate_statistics` has populated the `return` column; alternatively
recompute via `min((r.total_pnl + r.net_pnl)/(running_balance-r.net_pnl))` over
daily_results. The `df['return']` route is stable and documented.

### daily_records[] ← get_all_daily_results + strategy-tracked cash

```python
running = initial_capital
daily_records = []
for r in engine.get_all_daily_results():
    running += r.net_pnl
    daily_records.append({
        'date': r.date.isoformat(),
        'equity': running,
        'cash': strategy._cash_snapshot.get(r.date, running),  # see note
        'pnl_pct': (r.net_pnl / (running - r.net_pnl) * 100.0)
                   if (running - r.net_pnl) else 0.0,
        'trade_count': r.trade_count,
        'won': 0,   # computed from trade-zip pass below; or set per-day
    })
```

Cash snapshot: strategy must snapshot `self._cash` at `on_bars` end each day
into a `dict[date, float]`. vnpy has no cash accounting of its own.

`won` per-day: derive from the win-pass that iterates trades globally.

### trades[] ← get_all_trades

```python
for t in engine.get_all_trades():
    code = vt_to_biyingtong(t.symbol, t.exchange.value)
    action = 'buy' if t.direction == Direction.LONG else 'sell'
    # vnpy does NOT store per-trade fee on TradeData; it's aggregated in
    # ContractDailyResult.commission. Approximate per-fill fee:
    fee = t.volume * t.price * rates[t.vt_symbol]
    trades.append({
        'date': t.datetime.date().isoformat(),
        'code': code,
        'action': action,
        'shares': int(t.volume),
        'price': float(t.price),
        'fee': fee,
    })
```

### thinking[] ← strategy.daily_decisions + strategy._runner_last_thinking_per_day

Legacy runner builds `per_day_thinking` during the loop by snapshotting
`runner.last_thinking` **right after** each `run_day`. Because vnpy invokes
`on_bars` multiple times during the engine run, the strategy must snapshot
`self._runner.last_thinking` per day into a `dict[date_str, dict]` and merge
into `thinking` at result-build time:

```python
thinking = []
for date_str, decisions in strategy.daily_decisions:
    snap = strategy._thinking_by_date.get(date_str, {
        'reasoning': '', 'tool_calls': [], 'decisions': decisions,
    })
    thinking.append({'date': date_str, **snap})
```

### zone_stats ← hybrid helper

See Section 7. `_zone_stats_from_daily_results(daily_records, cutoff,
initial_capital)` → delegates to existing `backtest.stats.aggregate` returning
`overall, zones` — we discard `overall` (we already use engine stats for that)
and keep `zones`.

### Remaining BacktestResult fields

- `id` — `str(uuid.uuid4())`
- `session_id, agent_id, persona_id, model_id, start_date, end_date,
  initial_capital` — passed through from caller (same as legacy).
- `quality_gate_label, quality_gate_criteria` — same `evaluate_quality_gate`
  call on synthesized `gate_input` dict; unchanged from legacy.
- `final_equity` — `stats['end_balance']` or fallback to last `daily_records[-1].equity`.
- `kind` — `'agent'` (same as legacy).

---

## 9. Open questions / risks

| # | Risk                                                                 | Mitigation                                                                 |
|---|----------------------------------------------------------------------|----------------------------------------------------------------------------|
| 1 | vnpy caches strategy state between bars; slow LLM calls inside `on_bars` could look like a stuck engine (no pre-hook warning) | No mitigation needed — `run_backtesting` is synchronous and single-threaded. LLM latency = backtest latency. Document in README. |
| 2 | How to inject MockLLM for tests without real API                     | `setting={'llm': MockLLM(...), ...}` — the setting dict is passed to `LLMPortfolioStrategy.__init__`, which forwards to `AgentRunner(llm=...)`. Verified. |
| 3 | vnpy on missing-bar days (weekends/holidays)                         | `load_data` fetches only dates present in DB. `run_backtesting` iterates `self.dts`. Non-trading dates never enter the loop. Fill-forward for specific symbols-missing-one-day is handled by `new_bars` via `self.bars[vt_symbol]` previous-bar replay. |
| 4 | `calculate_result` returns `None` when no trades filled              | Guard: `df = engine.calculate_result(); if df is None: stats = _empty_stats()` path — return empty `BacktestResult` with zeroed `BacktestStats(final_equity=initial_capital)`. |
| 5 | `calculate_statistics` collapses to zeros on negative balance        | Detect `stats.get('end_balance', 0) == 0 and initial_capital > 0` after call → log warning + use daily_records tail for `final_equity`. |
| 6 | Legacy runner's `per_day_thinking` uses only `runner.last_thinking`; we need per-day snapshot in strategy | Confirmed above — strategy must snapshot. Unit-test this explicitly in Task 2. |
| 7 | Sharpe divergence: vnpy uses annual_days=240, ours 252               | Document in parity test; acceptable. Could `set_parameters(..., annual_days=252)` but that would also change `annual_return`. |
| 8 | `win_rate` reconstruction requires stateful pass over trades         | Helper `_compute_wins_per_day(trades) -> dict[date, (trade_count, wins)]` using running avg-cost per vt_symbol. Test fixture with known buy→sell→buy→sell sequences. |
| 9 | `BacktestingEngine.output` prints Chinese log lines to stdout        | `engine.output` is overridable; patch to `lambda *a, **kw: None` on BacktestingEngine instance to silence tests. |
| 10| Multi-agent parallel runner not yet adapted                          | Out of scope for Batch B (per plan §"不在本批范围"). Old `multi_agent_runner` stays on legacy `BacktestRunner`. |
| 11| Legacy runner applies `storage.audit().log` for unknown model        | Reproduce the same audit call in `VnpyBacktestRunner` before returning result. Don't skip — ecosystem depends on it. |
| 12| `strategy._positions` / `strategy._cash` mirrors drift if we only update from decisions | Better: override `update_trade(self, trade)` to mirror `vnpy` fills authoritatively into `self._positions` + adjust `self._cash`. Guarantees the LLM sees the real state next day. |

---

## 10. Parity test spec — `tests/test_runner_parity.py`

### Fixture

- Universe: 2 stocks from HS300 with coverage in the DB (e.g. `600519.SH`,
  `000858.SZ`).
- Window: `2025-06-01` → `2025-08-31` (well inside kline coverage).
- Initial capital: 1,000,000.
- LLM: `MockLLM` scripted with 2 buys, 1 sell, 1 hold across the window — the
  same script feeds both runners.
- Agent: a persona stub with a known `training_cutoff` inside the window so
  zones are non-trivial.

### Assertions

```python
def test_runners_agree_on_trade_count(legacy_result, vnpy_result):
    """Both runners must translate the SAME decisions into the SAME number
    of fills. Decisions are deterministic from MockLLM; trade_count MUST match exactly."""
    assert legacy_result.stats.trade_count == vnpy_result.stats.trade_count


def test_runners_agree_on_total_return_within_tolerance(legacy_result, vnpy_result):
    """vnpy fills at next-bar open, legacy at today's close → 1-bar price shift.
    Tolerance: 0.5 percentage points absolute."""
    assert abs(legacy_result.stats.total_return_pct
               - vnpy_result.stats.total_return_pct) < 0.5


def test_runners_agree_on_final_equity_within_tolerance(legacy_result, vnpy_result):
    """1% tolerance accommodates the fill-price-offset + Sharpe annualization differences."""
    ratio = vnpy_result.final_equity / legacy_result.final_equity
    assert 0.99 < ratio < 1.01


def test_runners_agree_on_first_trade_decision(legacy_result, vnpy_result):
    """Decisions are LLM-deterministic; both runners must see trade #0 on the
    same code + action even if fill price differs."""
    assert legacy_result.trades[0]['code'] == vnpy_result.trades[0]['code']
    assert legacy_result.trades[0]['action'] == vnpy_result.trades[0]['action']


def test_runners_agree_on_daily_record_count(legacy_result, vnpy_result):
    """Same trading calendar → same number of daily_records."""
    assert len(legacy_result.daily_records) == len(vnpy_result.daily_records)
```

### Acceptance criteria for Task 4 implementer

1. All five assertions pass under the default fixture.
2. If tolerance needs widening, document the reason in the test docstring
   (not the assertion message — docstring is the public contract).
3. Do NOT tighten tolerances below 0.3% (trade_count) / 0.5% (pct) / 0.99-1.01
   ratio without a principled justification, because the 1-bar-offset divergence
   floor is intrinsic to the design choice in Section 6.

---

## Appendix — Showstoppers checked, none found

- [x] vnpy_sqlite reads the same DB our storage writes (Section 4)
- [x] vt_symbol format is `{bare}.SSE` / `{bare}.SZSE` and matches storage (Section 3)
- [x] `BacktestingEngine` API is synchronous + deterministic (Section 2)
- [x] `setting` dict forwards LLM instance to `LLMPortfolioStrategy` (risk #2)
- [x] `calculate_statistics` returns enough keys to populate `BacktestStats`
      (Section 8 — only `win_rate` and `max_daily_loss_pct` need manual compute,
      both tractable)
- [x] Zone stats can be post-processed (Section 7)
- [x] T+1 can be enforced in-strategy without engine modification (Section 5)

**No showstoppers.** Batch B tasks 2–8 can proceed.
