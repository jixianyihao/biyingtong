# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

必赢通 (BiYingTong) — a quantitative trading terminal built on top of 通达信 (TongDaXin/TDX), a Chinese stock trading platform. Current state: working prototype with live market data, simulated trading, and AI agent UI. A major expansion is planned (see design spec below).

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
Browser (React 18 SPA, CDN-loaded, Babel standalone JSX)
   │  REST /api/*  +  Socket.IO WebSocket
   ▼
Flask (app.py)  ◄──►  TDXService (tdx_service.py)  ◄──►  TDX SDK (tqcenter)
                         thread-safe singleton
```

**Backend**: Flask + Flask-SocketIO. `app.py` serves static frontend files, exposes REST API routes, and pushes live quotes via WebSocket every 3 seconds. `tdx_service.py` is a thread-safe singleton wrapping the `tqcenter` SDK for market data and trading.

**Frontend**: No bundler. React 18 + Babel standalone loaded from CDNs. All `.jsx` files are individual `<script type="text/babel">` tags in `index.html`. Components are global functions, not ES modules. `api.js` exposes `window.BYT` as the API client.

**Color convention**: Chinese stock market — red = up, green = down. Theme uses `oklch` color tokens in `static/styles/tokens.css`.

## Key Files

- `app.py` — Flask entry point, all REST + WebSocket endpoints
- `tdx_service.py` — TDX SDK wrapper singleton (market data, trading, account management)
- `static/index.html` — SPA entry, loads all CDN deps and JSX modules via script tags
- `static/src/api.js` — `window.BYT` API client (REST + WebSocket helpers)
- `static/src/shell.jsx` — App shell (Sidebar, TopBar, StatusBar, navigation state)
- `static/styles/tokens.css` — Design tokens, dark/light themes, oklch colors

## Planned Expansion

Design spec at `docs/superpowers/specs/2026-04-22-trading-agent-backtest-design.md` describes:
- **vnpy (VeighNa)** for backtesting engine and strategy templates
- **LLM-driven trading agents** (Claude/GPT/DeepSeek) with 5 pre-defined personas
- **Frontend migration** from CDN React to Vite + React with proper ES modules
- **SQLite** for K-line data caching via vnpy_sqlite
- **Subprocess + message queue** architecture for deployed agents with crash recovery
- **Configurable validation rule engine** for pre-trade checks and post-backtest quality gates
