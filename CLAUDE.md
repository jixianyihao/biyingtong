# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

必赢通 (BiYingTong) — a quantitative trading terminal built on top of 通达信 (TongDaXin/TDX), a Chinese stock trading platform. The app combines live TDX market data, a dual-engine backtest runner (legacy + vnpy `BacktestingEngine`), LLM-driven trading agents with configurable personas and a validation rule engine, and subprocess-based live deployment with UI-gated proposal approval. Real-money order execution is intentionally gated behind an explicit sign-off and is currently deferred.

## Running the App

```bash
pip install -r requirements.txt
python app.py
# Opens at http://127.0.0.1:5000
```

Prerequisites: TDX installed with SDK at `C:\new_tdx_mock\PYPlugins\sys`. Trading features require TDX client logged in (F12).

No build step, no tests, no Docker.

## Architecture

```
Browser (two frontends co-exist)
  ├─ static/   legacy React 18 SPA, CDN-loaded, Babel standalone JSX  (served by Flask)
  └─ frontend/ Vite + React + TypeScript + Tailwind (ES modules, proper build)
   │  REST /api/*  +  Socket.IO WebSocket  +  SSE fine-grained events
   ▼
Flask (app.py)
   │
   ├──► TDXService (tdx_service.py)  ◄──►  TDX SDK (tqcenter)
   │        thread-safe singleton; tq.subscribe_hq push replaces 3-sec polling
   │
   ├──► LLM adapter layer (llm/)  — Claude / OpenAI / Gemini / Mock via factory
   │
   ├──► Backtest runners (backtest/)
   │        ├─ runner.py        legacy path
   │        └─ vnpy_runner.py   parallel path (?engine=vnpy)
   │                            reuses vnpy_portfoliostrategy.BacktestingEngine
   │                            + LLMPortfolioStrategy + calculate_statistics
   │
   ├──► Validation engine (validation/)  — 4 rule handlers + audit log
   │
   ├──► SQLite stores (storage/)  — agents, personas, backtests, proposals,
   │        audit, kline, financial, calendar, llm_cache, prompt_versions,
   │        redline, stock_status, baselines, deployed_agents, models
   │
   └──► Live deployment (runner/agent_process.py)
            subprocess per deployed agent + in-memory HTTP control channel;
            proposals emitted to UI for human approval (Phase 1 — no real-money exec)
```

**Backend**: Flask + Flask-SocketIO. `app.py` serves the legacy static frontend, exposes REST API routes, pushes live quotes via WebSocket (now backed by `tq.subscribe_hq` push), and streams backtest progress via SSE. `tdx_service.py` is a thread-safe singleton wrapping the `tqcenter` SDK for market data and trading.

**Frontend**: Two frontends co-exist. The active one served by Flask is `static/` (CDN React 18 + Babel standalone, `.jsx` files loaded as `<script type="text/babel">`, components are global functions, `api.js` exposes `window.BYT`). The `frontend/` directory is a separate Vite + React + TS + Tailwind app (built artifacts in `frontend/dist`).

**Color convention**: Chinese stock market — red = up, green = down. Theme uses `oklch` color tokens in `static/styles/tokens.css`.

## Key Files

- `app.py` — Flask entry point, all REST + WebSocket + SSE endpoints
- `tdx_service.py` — TDX SDK wrapper singleton (market data, trading, account management)
- `backtest/runner.py` — legacy backtest runner
- `backtest/vnpy_runner.py` — vnpy-based backtest runner (parallel path)
- `backtest/strategy.py` — `LLMPortfolioStrategy` bridging LLM decisions into vnpy
- `llm/factory.py` — LLM adapter factory (Claude / OpenAI / Gemini / Mock)
- `personas/` — 6 built-in personas (linyuan / fuyou / buffet / soros / quant_neutral / intraday_t0)
- `tools/` — tool implementations exposed to agents (10+ in `ALL_TOOLS`)
- `storage/` — SQLite protocol interfaces and implementations
- `runner/agent_process.py` — subprocess-based live agent deployment
- `validation/` — rule engine with 4 handlers + audit log
- `static/index.html` — legacy SPA entry, loads all CDN deps and JSX modules via script tags
- `static/src/api.js` — `window.BYT` API client (REST + WebSocket helpers)
- `static/src/shell.jsx` — App shell (Sidebar, TopBar, StatusBar, navigation state)
- `static/styles/tokens.css` — Design tokens, dark/light themes, oklch colors
- `frontend/` — Vite + React + TS + Tailwind app (parallel / newer frontend)

## Status

Authoritative roadmap: `docs/superpowers/plans/2026-04-23-status-and-roadmap.md`.

Delivered so far:

- **P2a–f**: personas × agents × rules engine; LLM adapters; LLM backtest runner with baselines; validation engine (4 rule handlers + audit log); strategy rating (5 sub-scores); prompt versioning with rollback; zone-bifurcated stats against cutoff for anti-leakage; health + trust rating.
- **P3-A**: backtest observability — NAV / trades / thinking endpoints + NavChart + TradesTable + ThinkingDrawer + QualityGatePanel + StrategyRatingPanel.
- **P3-B**: agent + persona CRUD + prompt rollback.
- **P3-C**: rule-mode backtests — 3 built-in strategies (MA / RSI / MACD) head-to-head vs agents + baselines.
- **P3-D**: SSE fine-grained events (7 spec event types).
- **P3-E**: in-prompt disclaimer with training cutoff + global backtest list + `RedLineBar` widget.
- **P3-F Phase 1**: deploy / stop / proposal architecture (subprocess + in-memory HTTP). **No real-money execution.**
- **Framework-first audit remediation** (2026-04-24; 3 serial batches all done):
  - Batch A: `get_technical` → talib 0.6.8; `load_financial` auto-loaded on startup (background thread).
  - Batch B: `VnpyBacktestRunner` as a parallel path (`?engine=vnpy` toggle); parity test vs legacy runner.
  - Batch C: `tq.subscribe_hq` push replaces 3-sec polling; `get_stock_list` + `get_capital_flow` tools; 5m bar storage support (fallback to `MINUTE` since local vnpy lacks `MINUTE_5`).

Current totals (approx): ~685 pytest passing; 11+ tools in `ALL_TOOLS`; 6 built-in personas; 4 LLM adapters; dual-engine backtest runners; subprocess-based agent deployment with UI-gated approval flow; `execution/` abstraction for dry-run + live TDX order submission.

**Phase 2** (real TDX order execution on proposal approval) is delivered behind `BIYINGTONG_EXECUTION_MODE` env var (default `dry_run` → `MockExecutionAdapter`; set to `live` → `TDXExecutionAdapter`). In live mode the UI additionally requires typing `确认下单` in a confirmation modal before each order is submitted. See `execution/` package and `docs/superpowers/plans/2026-04-24-p3f-phase2-execution.md`.

## Development Discipline — Real-User First

**Every change must leave the platform basically usable, not demo-grade.** Treat development as if you were the user landing on the page for the first time:

- **No mock data in shipped UI.** If a backend isn't ready, show an honest empty state ("等待后端数据" / "Phase X pending") — never fake numbers, fake stocks, or fake equity curves.
- **End-to-end smoke before claiming done.** For UI/feature work, actually click through the new path in the browser (`mcp__plugin_playwright_playwright__*` if running headless, or start dev servers and load the URL). Tests + tsc both green ≠ feature works.
- **Verify with real data when possible.** If local kline cache or test fixtures cover the path, run the real flow against them; only fall back to mocks when the data genuinely doesn't exist.
- **History / audit trails must be readable by a human.** Show display_name + persona + model — not raw `<persona>_<8hex>` ids. The user will never remember which `linyuan_3780f689` ran when.
- **Forms validate against reality.** Date pickers, code inputs, etc. should warn pre-submit when the request will produce a useless result (e.g., date window outside data coverage). Don't let the user submit and stare at "0%, 0 trades" without explanation.
- **Names of buttons / chips / labels must match what they actually do.** No "Phase 3" / "TODO" / "WIP" wording on production UI.

If a change fails the real-user test (you wouldn't ship it as a paying customer), it's not done — fix the gap in the same commit, or open a follow-up before merging.
