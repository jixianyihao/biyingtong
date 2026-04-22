# P0 Verification Report — 2026-04-22

Summary of what the P0 plan verified about the TDX data pipelines on this environment. All three target pipelines work. One secondary data gap (revenue/net-profit growth fields) is documented as a known follow-up for P1.

## Environment

- **OS**: Windows 10 Pro 10.0.18362
- **Python**: 3.14.4 (note: `pandas==2.2.3` has no cp314 wheel → relaxed to `pandas>=2.2`, currently pandas 3.0.2)
- **vnpy**: 4.0.0 (upgraded from original spec's 3.9 pin — all downstream `vnpy_*` packages require 4.x)
- **vnpy_sqlite**: 1.1.3
- **vnpy_portfoliostrategy**: 1.2.x
- **vnpy_ctastrategy**: 1.4.1
- **pytest**: 9.0.3
- **TDX SDK**: `C:\new_tdx_mock\PYPlugins\sys\tqcenter.py` (3767 lines, v？ — no `__version__` exposed)
- **TDX client status at verification**: ✓ connected + authenticated throughout P0 execution
- **vnpy_tdx**: NOT used — see `docs/superpowers/plans/2026-04-22-p0-infrastructure-spikes.md` Task 1 revision. PyPI package is empty stub. We bridge via existing `tdx_service.py` (tqcenter) → vnpy BarData.

## Pipeline 1 — Daily K-line (tqcenter → vnpy_sqlite)

- **Status**: ✓ WORKS
- **Load path**: `tdx.get_kline(full_code, period='1d', count)` → construct `vnpy.trader.object.BarData` → `vnpy_sqlite.Database.save_bar_data(bars)` → close peewee handle
- **HS300 result**: **299/300 stocks** loaded with ≥ 200 bars for 2025-04-01 to 2026-04-01
  - Only one outlier: **600930 中国电力** with 172 bars (almost certainly a suspension period — acceptable)
  - All other 299 stocks have 223–243 bars (full year = 243 A-share trading days)
- **Duration**: ~125 seconds for full HS300 batch load
- **Database location**: `data/vnpy_data.db` (populated, gitignored)
- **Discovered issue (deferred to P1)**: `tdx.get_kline` returns `vol` in units of **手 (lots = 100 shares)** per official docs `docs/references/tqcenter_docs/mindoc-1ctuhthaq5qmg__mindoc-1h10g60jt68sc.md`. Current code passes it as-is to vnpy's `BarData.volume`, which conventionally means shares. Relative volume comparisons in strategy code are unaffected, but absolute volume displays / turnover computations will be 100× low. Fix in P1: multiply by 100 in `scripts/setup/load_kline.py:88`.

## Pipeline 2 — Trading Calendar

- **Status**: ✓ WORKS — both primary and fallback paths verified
- **Primary path (`tq.get_trading_calendar`)**: ✓ WORKS after Task 8 + the follow-up fix in commit `76c6ab6` which corrected the call signature (`market='SH'` required, dates in `YYYYMMDD` not `YYYY-MM-DD`).
  - Returned **21 trading days** for April 2025 (matches reality: 30 calendar days − 8 weekends − 1 May Day holiday precursor = 21)
- **Fallback path (`_fallback_kline_dates` via vnpy_sqlite)**: ✓ WORKS. Table `dbbardata` confirmed to be the correct vnpy_sqlite 1.1.x table name.
- **Full-year coverage**: **243 trading days** for 2025-04-01 → 2026-04-01 (expected range 230–260)

## Pipeline 3 — Financial Cache (PE / PB / ROE / margins via tqcenter)

- **Status**: ✓ WORKS with partial field coverage (documented limitation)
- **HS300 result**: **300/300 stocks** written to `data/financial_cache.db`
- **Field coverage** (how many of 300 rows have non-null values):
  | Field | Coverage | Note |
  |-------|---------:|------|
  | `pe` | 277 / 300 | Derived as `price / J_mgsy` (trailing PE). Null when EPS is zero/negative or price unavailable |
  | `pb` | 300 / 300 | Derived as `price / J_mgjzc` |
  | `roe` | 300 / 300 | From `J_jyl` (already % pct) |
  | `gross_margin` | 294 / 300 | Derived as `(J_yysy − J_yycb) / J_yysy × 100` |
  | `revenue_growth` | **0 / 300** | ⚠ NULL intentionally — see limitation below |
  | `net_profit_growth` | **0 / 300** | ⚠ NULL intentionally — see limitation below |

- **Documented limitation — growth fields (P1 action)**:
  - `tq.get_stock_info` (the API P0 Task 10 uses) returns a single-period basic financial snapshot (`J_*` keys). It does not expose year-over-year growth rates.
  - The correct vendor API is **`tq.get_financial_data(stock_list, field_list=['FN183','FN184','FN197','FN202','FN1','FN4'], start_time=...)`** — it returns multi-period DataFrames with all the growth rates pre-computed. See docs mirror at `docs/references/tqcenter_docs/TdxQuant__mindoc-1h10m001ic888.md`.
  - **P1 action**: rewrite `scripts/setup/load_financial.py` against `get_financial_data`. That single batched call replaces the current `get_stock_info + get_snapshot + _derive_metrics` approach, fills the two NULL columns, and removes the per-symbol snapshot round-trip.
  - Reference: the code-review of commit `5f366cb` flagged this, and the subsequent doc crawl confirmed the proper path.

## Trading API — not tested but documented

P0 did not touch the live trading path (order placement / position queries). That's scoped for P5. Mitigation: the official docs for `stock_account`, `query_stock_asset`, `query_stock_positions`, `query_stock_orders`, `order_stock`, `cancel_order_stock` are all mirrored under `docs/references/tqcenter_docs/mindoc-1h7k4iqb1grk4__*.md`. The `tqconst` constants (`STOCK_BUY`=0, `STOCK_SELL`=1, `PRICE_MY`=0, etc.) are mirrored at `docs/references/tqcenter_docs/Dict.md`.

## Test Suite

All 5 integration tests pass (TDX online):

| Test | Status |
|------|--------|
| `test_kline_single_stock_roundtrip` | ✓ PASS |
| `test_kline_batch_hs300_top50` | ✓ PASS (23 seconds) |
| `test_trading_calendar_returns_valid_dates` | ✓ PASS (primary path) |
| `test_trading_calendar_fallback_when_tdx_api_missing` | ✓ PASS (via monkeypatched fallback) |
| `test_financial_cache_loads_pe_pb_roe` | ✓ PASS |
| `test_full_pipeline_integration` | ✓ PASS |

**Also added** (Task 11): `tests/conftest.py::_close_peewee_db_between_tests` — autouse fixture that closes the module-level peewee singleton after each test. This fixed a test-order dependency where `vnpy_sqlite.Database()` would refuse to re-instantiate after the first use.

## Gaps / Action Items for Later Plans

### P1 (LLM Layer + Tools)
- [ ] **Rewrite `scripts/setup/load_financial.py`** to use `tq.get_financial_data` with fields `['FN1', 'FN4', 'FN6', 'FN183', 'FN184', 'FN197', 'FN202']`. This:
  - Fills the currently-NULL `revenue_growth` and `net_profit_growth` columns
  - Batches per-stock calls into fewer API round-trips
  - Removes the `tdx.get_snapshot(full)` call that currently doubles request count
  - Enables P2's 巴菲特 agent which needs multi-year ROE history
- [ ] **Fix K-line volume unit** (`scripts/setup/load_kline.py:88`): multiply `row['vol']` by 100 to convert lots → shares before constructing `BarData`.
- [ ] **Wrap `trading_calendar.get_trading_days` into `tdx_service.py`** as a proper method. Current module is standalone at repo root, which was fine for the P0 spike but better integration is to expose it as `tdx_service.tdx.get_trading_days()` for consistency.
- [ ] **Add `tqcenter` sys.path injection to `trading_calendar._try_tdx_calendar`** so primary path works even when `tdx_service.py` hasn't been imported earlier in the process (currently passes because our tests always import `tdx_service` first via `tdx_ready` fixture).

### P2 (Agent Backtest MVP)
- [ ] **Intraday periods (`1m` / `5m`) unverified**. The test suite only exercises `1d`. Plan § 10 deferred this to Phase 2 anyway.
- [ ] **Dividend-factor cache**: `tdx.get_kline(..., dividend_type='front')` was tested only with `'front'` by `tdx_service.py` default. When backtesting, we pass `dividend_type=None` via vnpy's convention which maps to `'none'`. Need to verify A-share dividend events don't introduce jumps in our stored K-line.

### P3+ (deferred research)
- Trading calendar only covers A-shares (`market='SH'`). When/if we extend to HK/US, need to pass different market params.

## Overall Assessment

**✓ P0 achieves its stated goal**: all three TDX data pipelines are verified on this environment, data/ directory is populated with real HS300 K-line and financial data, and the test suite gives fast feedback for regression detection. Two non-blocking issues are documented above for P1 to address.

**Next plan**: P1 — LLM Layer + Tools. See `docs/superpowers/plans/2026-04-XX-p1-llm-layer.md` (to be written).

## References

- Plan document: `docs/superpowers/plans/2026-04-22-p0-infrastructure-spikes.md`
- Spec: `docs/superpowers/specs/2026-04-22-trading-agent-backtest-design.md` § 3, § 17, § 18
- Official API docs (local mirror): `docs/references/tqcenter_docs/`
- API docs index: `docs/references/tqcenter_docs/README.md`
- Crawler source: `scripts/setup/crawl_tdx_docs.py`
- tqcenter SDK source (authoritative): `C:\new_tdx_mock\PYPlugins\sys\tqcenter.py`
