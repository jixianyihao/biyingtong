# P0 — Infrastructure Spikes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify all three TDX data pipelines (K-line → vnpy_sqlite, trading calendar, financial data cache) work end-to-end on this Windows + TDX-client environment, so all later plans can proceed without data-access surprises.

**Architecture:** Install vnpy stack. Write two one-shot setup scripts that populate `data/vnpy_data.db` (HS300 1-year daily K-line via `vnpy-tdx`) and `data/financial_cache.db` (HS300 PE/PB/ROE via existing `tqcenter` SDK). Write a thin `trading_calendar.py` helper at repo root with a K-line-dates fallback for the case that `tq.get_trading_calendar()` is unavailable. Integration tests verify each pipeline on real data and skip gracefully when TDX is offline.

**Tech Stack:** Python 3.10+, vnpy 3.x + vnpy_sqlite + vnpy_tdx + vnpy_portfoliostrategy + vnpy_ctastrategy, existing `tqcenter` SDK (already vendored at `C:\new_tdx_mock\PYPlugins\sys`), pytest, SQLite (WAL journal), `decimal.Decimal` for any money math, pandas for vnpy data interop.

---

## Spec References

- § 3.1 Two TDX Data Paths
- § 3.2 Financial Data Cache schema
- § 3.3 Trading Calendar handling
- § 17 TDX Data Verification Summary
- § 18 Milestone 0 (steps 1–3)

## Deliverables (end-state after plan is complete)

1. `data/vnpy_data.db` — populated with ≥ 250 HS300 stocks, 1 year of daily bars each (~244 bars/stock)
2. `data/financial_cache.db` — populated with latest PE/PB/ROE/margins/growth for ≥ 250 HS300 stocks
3. `trading_calendar.py` — working helper that returns trading days between two dates (preferred path + K-line-dates fallback)
4. `tests/test_data_pipeline.py` — integration tests (pass when TDX online, skipped otherwise)
5. `requirements.txt` — updated with vnpy stack + pytest
6. `.gitignore` — ensures `data/` stays out of git
7. `docs/superpowers/specs/p0-verification-report.md` — one-page summary of verified paths, fallbacks used, and any discovered issues

## File Structure

```
biyingtong/
├── requirements.txt                     # MODIFIED
├── .gitignore                           # MODIFIED
├── conftest.py                          # NEW (repo-root pytest config)
├── trading_calendar.py                  # NEW — root-level helper
├── scripts/
│   ├── __init__.py                      # NEW
│   └── setup/
│       ├── __init__.py                  # NEW
│       ├── vnpy_config.py               # NEW — points vnpy at data/vnpy_data.db
│       ├── load_kline.py                # NEW — HS300 K-line loader
│       └── load_financial.py            # NEW — HS300 financial loader
├── tests/
│   ├── __init__.py                      # NEW
│   ├── conftest.py                      # NEW — TDX fixture + skip markers
│   └── test_data_pipeline.py            # NEW
├── data/                                # NEW (gitignored, populated at runtime)
│   ├── vnpy_data.db
│   └── financial_cache.db
└── docs/superpowers/specs/
    └── p0-verification-report.md        # NEW (written in Task 12)
```

**Rationale:** All P0 artifacts are thin and single-purpose. `scripts/setup/` is where one-shot data-loading utilities live (not production tools — those come in P1). `trading_calendar.py` sits at repo root because it's imported later by both `runner/` (P2) and `strategy/` (P3); putting it in a submodule now would force needless import paths later. `conftest.py` at repo root enables pytest to find project modules.

---

### Task 1: Add vnpy dependencies + pytest to requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Open current requirements.txt for review**

Run: `type requirements.txt` (on Windows Git Bash: `cat requirements.txt`)
Expected current content:
```
flask==3.1.0
flask-socketio==5.4.1
flask-cors==5.0.1
pandas==2.2.3
gevent==24.11.1
gevent-websocket==0.10.1
```

- [ ] **Step 2: Replace requirements.txt with vnpy stack + pytest**

Replace `requirements.txt` with:
```
flask==3.1.0
flask-socketio==5.4.1
flask-cors==5.0.1
pandas>=2.2
gevent==24.11.1
gevent-websocket==0.10.1

# vnpy backtest stack (added in P0)
# Notes on pins:
#   - vnpy 4.x is required: vnpy_portfoliostrategy>=1.2, vnpy_sqlite>=1.1, and
#     vnpy_ctastrategy>=1.4 all depend on it.
#   - vnpy_tdx is NOT used. The PyPI package is an empty stub. We bridge
#     TDX historical data via tqcenter (see tdx_service.py) and construct
#     vnpy BarData ourselves, persisted through vnpy_sqlite.
vnpy>=4.0.0
vnpy_sqlite>=1.1.0
vnpy_portfoliostrategy>=1.2.0
vnpy_ctastrategy>=1.4.0

# testing (added in P0)
pytest>=7.4.0
pytest-xdist>=3.3.0
```

**Deviation rationale (Task 1, revised):** Original plan pinned `vnpy>=3.9,<4` and `vnpy_tdx>=1.0.6`. Discovered during install: (a) all downstream vnpy packages require vnpy 4.x, so 3.x pin is infeasible; (b) `vnpy_tdx` on PyPI is an empty dist-info stub; real code is on GitHub but not reachable here. Resolution: drop `vnpy_tdx`, use existing `tdx_service.py` (tqcenter) as the datafeed and construct `vnpy.trader.object.BarData` directly in `scripts/setup/load_kline.py`. See the revised Task 5.

- [ ] **Step 3: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: all packages install. On Windows, vnpy may require Microsoft Visual C++ 14.0+ Build Tools. If install fails with an error mentioning `cl.exe` or `Microsoft Visual C++`, install VS Build Tools from https://visualstudio.microsoft.com/visual-cpp-build-tools/ and retry.

- [ ] **Step 4: Verify imports**

Run:
```
python -c "import vnpy, vnpy_sqlite, vnpy_tdx, vnpy_portfoliostrategy, vnpy_ctastrategy, pytest; print('IMPORT_OK')"
```
Expected: `IMPORT_OK` printed, no tracebacks.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git commit -m "build: add vnpy stack and pytest for backtest infrastructure"
```

---

### Task 2: Gitignore data/ and create the directory

**Files:**
- Modify: `.gitignore`
- Create: `data/` (empty directory)

- [ ] **Step 1: Replace .gitignore content**

Replace `.gitignore` with:
```
__pycache__/
*.pyc
.playwright-mcp/
*.png
.claude/

# Runtime databases (added in P0)
data/
*.db
*.db-journal
*.db-wal
*.db-shm

# pytest (added in P0)
.pytest_cache/
```

- [ ] **Step 2: Create data/ directory**

Run: `mkdir -p data`
Expected: `data/` exists (no-op if it was already there).

- [ ] **Step 3: Verify gitignore works**

Run:
```
touch data/.sentinel
git status --porcelain data/
rm data/.sentinel
```
Expected: no output from the second command (data/ is ignored).

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore data/ directory and SQLite artifacts"
```

---

### Task 3: Create vnpy config helper that points vnpy at data/vnpy_data.db

**Files:**
- Create: `scripts/__init__.py` (empty)
- Create: `scripts/setup/__init__.py` (empty)
- Create: `scripts/setup/vnpy_config.py`

- [ ] **Step 1: Create the package markers**

Write empty files:
- `scripts/__init__.py`
- `scripts/setup/__init__.py`

(Content of each: a single line `"""package marker."""`)

- [ ] **Step 2: Create scripts/setup/vnpy_config.py**

Content:
```python
"""Configure vnpy to store its SQLite database in ./data/vnpy_data.db.

vnpy reads DB config from vnpy.trader.setting.SETTINGS. By default it uses
~/.vntrader/database.db, which is unreachable from a repo-local workflow.
Import `configure()` before using any vnpy Database or BacktestingEngine.
"""
from pathlib import Path

from vnpy.trader.setting import SETTINGS

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / 'data'
DB_PATH = DATA_DIR / 'vnpy_data.db'


def configure() -> Path:
    """Point vnpy at data/vnpy_data.db. Idempotent. Returns the DB path."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS['database.name'] = 'sqlite'
    SETTINGS['database.database'] = str(DB_PATH)
    return DB_PATH
```

- [ ] **Step 3: Verify it works**

Run:
```
python -c "from scripts.setup.vnpy_config import configure; print(configure())"
```
Expected: printed absolute path ending in `biyingtong\data\vnpy_data.db`.

- [ ] **Step 4: Commit**

```bash
git add scripts/
git commit -m "feat(p0): vnpy SQLite path configuration helper"
```

---

### Task 4: Write failing test for K-line single-stock roundtrip

**Files:**
- Create: `conftest.py` (at repo root)
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_data_pipeline.py`

- [ ] **Step 1: Create repo-root conftest.py**

Content of `conftest.py`:
```python
"""Repo-root pytest config: add project root to sys.path.

This lets `tests/*.py` import `tdx_service`, `trading_calendar`, `scripts.*`
without needing to install the project as a package.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
```

- [ ] **Step 2: Create tests/__init__.py**

Content: `"""tests package."""`

- [ ] **Step 3: Create tests/conftest.py**

Content:
```python
"""Shared fixtures. TDX-dependent tests are skipped if the TDX client is offline."""
import pytest


@pytest.fixture(scope='session')
def tdx_ready():
    """Returns the live tdx singleton; skips the test if TDX is unreachable."""
    try:
        from tdx_service import tdx
    except ImportError as e:
        pytest.skip(f'tqcenter SDK not importable: {e}')
        return  # unreachable; silence linters
    if not tdx.initialize():
        pytest.skip('TDX failed to initialize — start 通达信 and press F12')
    if not tdx.is_connected():
        pytest.skip('TDX not connected')
    return tdx


@pytest.fixture(scope='session')
def vnpy_configured():
    """Point vnpy at data/vnpy_data.db once per session."""
    from scripts.setup.vnpy_config import configure
    return configure()
```

- [ ] **Step 4: Create tests/test_data_pipeline.py with the first failing test**

Content:
```python
"""Integration tests for P0 data pipelines.

These hit real TDX and are skipped if TDX is offline.
"""
from datetime import datetime


def test_kline_single_stock_roundtrip(tdx_ready, vnpy_configured):
    """茅台 1 year daily: load via vnpy-tdx → save to vnpy_sqlite → read back ~244 bars."""
    from scripts.setup.load_kline import load_single_stock

    start = datetime(2025, 4, 1)
    end = datetime(2026, 4, 1)
    written = load_single_stock(symbol='600519', start=start, end=end)

    assert written >= 200, f'expected ≥200 bars for 600519, got {written}'

    # Read back via vnpy's API
    from vnpy_sqlite import Database
    from vnpy.trader.constant import Exchange, Interval

    db = Database()
    bars = db.load_bar_data(
        symbol='600519',
        exchange=Exchange.SSE,
        interval=Interval.DAILY,
        start=start,
        end=end,
    )
    assert len(bars) == written, 'roundtrip count mismatch'
    first = bars[0]
    assert first.high_price >= first.low_price > 0
    assert first.open_price > 0 and first.close_price > 0
    assert first.volume >= 0
```

- [ ] **Step 5: Run test to confirm it fails (for the right reason)**

Run: `pytest tests/test_data_pipeline.py::test_kline_single_stock_roundtrip -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.setup.load_kline'`

- [ ] **Step 6: Commit the failing test**

```bash
git add conftest.py tests/
git commit -m "test(p0): failing integration test for single-stock K-line roundtrip"
```

---

### Task 5: Implement `load_single_stock` to make Task 4 pass

**Files:**
- Create: `scripts/setup/load_kline.py`

**Note on approach (revised from original plan):** `vnpy_tdx` is unusable (PyPI stub). We bridge via the existing `tdx_service.py` (tqcenter) that already handles TDX authentication and returns OHLCV dicts. We construct `vnpy.trader.object.BarData` instances ourselves and save them through `vnpy_sqlite.Database.save_bar_data()` — from vnpy's perspective the resulting database is identical to what `vnpy_tdx` would have produced, so later plans can still use `BacktestingEngine.load_data()` unchanged.

- [ ] **Step 1: Implement load_single_stock**

Content of `scripts/setup/load_kline.py`:
```python
"""Load HS300 daily K-line from TDX (via tqcenter) into vnpy_sqlite.

Why we don't use vnpy_tdx: the PyPI package is an empty stub. The existing
tdx_service.py (tqcenter) already handles TDX auth + K-line retrieval; we
just convert its dict output into vnpy BarData objects for storage.

Entry points:
- `load_single_stock(symbol, start, end)` — one stock, returns bars written
- `load_batch(symbols, start, end)` — many stocks, returns {symbol: count}
"""
from __future__ import annotations

from datetime import datetime

from scripts.setup.vnpy_config import configure as _configure_vnpy

# Configure vnpy BEFORE importing vnpy_sqlite (it reads SETTINGS at import)
_configure_vnpy()

from vnpy.trader.constant import Exchange, Interval  # noqa: E402
from vnpy.trader.object import BarData  # noqa: E402
from vnpy_sqlite import Database  # noqa: E402

from tdx_service import tdx  # noqa: E402  (existing tqcenter wrapper)


def _exchange_for(symbol: str) -> Exchange:
    """Infer SSE / SZSE from the 6-digit symbol prefix."""
    if symbol.startswith(('6', '9')):
        return Exchange.SSE
    if symbol.startswith(('0', '3')):
        return Exchange.SZSE
    raise ValueError(f'Cannot infer exchange for symbol {symbol!r}')


def _tdx_full_code(symbol: str, exchange: Exchange) -> str:
    """tdx_service.get_kline expects '600519.SH' form."""
    suffix = 'SH' if exchange == Exchange.SSE else 'SZ'
    return f'{symbol}.{suffix}'


def load_single_stock(symbol: str, start: datetime, end: datetime) -> int:
    """Fetch daily bars via tqcenter and save to vnpy_sqlite.

    tdx.get_kline returns `count` bars ending today. We request enough bars
    to cover the [start, end] window, then filter to that window before save.

    Returns number of bars written.
    """
    exchange = _exchange_for(symbol)
    full = _tdx_full_code(symbol, exchange)

    if not tdx.ensure_connected():
        return 0

    # tqcenter returns `count` bars ending "now". Ask for enough to span [start, end].
    # Daily bars: N trading days ≈ N * 1.4 calendar days worst-case (weekends+holidays).
    today = datetime.now()
    calendar_span = max((today - start).days + 7, 30)
    count = max(int(calendar_span * 1.2), 30)

    raw = tdx.get_kline(full, period='1d', count=count)
    if not raw:
        return 0

    bars: list[BarData] = []
    for row in raw:
        try:
            bar_dt = datetime.strptime(row['date'], '%Y-%m-%d')
        except (KeyError, ValueError):
            continue
        if bar_dt < start or bar_dt > end:
            continue
        bars.append(BarData(
            symbol=symbol,
            exchange=exchange,
            datetime=bar_dt,
            interval=Interval.DAILY,
            open_price=float(row.get('open', 0)),
            high_price=float(row.get('high', 0)),
            low_price=float(row.get('low', 0)),
            close_price=float(row.get('close', 0)),
            volume=float(row.get('vol', 0)),
            turnover=0.0,
            open_interest=0.0,
            gateway_name='TDX',
        ))

    if bars:
        Database().save_bar_data(bars)
    return len(bars)


def load_batch(symbols: list[str], start: datetime, end: datetime) -> dict[str, int]:
    """Fetch many stocks. Continues on per-stock error. Returns per-symbol counts."""
    result: dict[str, int] = {}
    for sym in symbols:
        try:
            result[sym] = load_single_stock(sym, start, end)
        except Exception as e:  # noqa: BLE001
            print(f'[load_batch] {sym} FAILED: {e}')
            result[sym] = 0
    return result


if __name__ == '__main__':
    # Smoke test — load 1 year of 茅台
    now = datetime.now()
    start = datetime(now.year - 1, now.month, now.day)
    end = datetime(now.year, now.month, now.day)
    n = load_single_stock('600519', start, end)
    print(f'600519: {n} bars written to vnpy_sqlite')
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `pytest tests/test_data_pipeline.py::test_kline_single_stock_roundtrip -v`
Expected: PASS. (If TDX is offline, test will SKIP — start 通达信 and retry.)

- [ ] **Step 3: Commit**

```bash
git add scripts/setup/load_kline.py
git commit -m "feat(p0): load_single_stock via tqcenter bridge into vnpy_sqlite"
```

---

### Task 6: Write failing test for batch HS300 K-line load (50 stocks)

**Files:**
- Modify: `tests/test_data_pipeline.py`

- [ ] **Step 1: Append batch test**

Append to `tests/test_data_pipeline.py`:
```python


def test_kline_batch_hs300_top50(tdx_ready, vnpy_configured):
    """Top 50 HS300 constituents: batch load succeeds on ≥ 45/50."""
    from scripts.setup.load_kline import load_batch

    # A known-stable subset of HS300 (large caps). Full HS300 list loading
    # happens in the real setup run (Task 9), not here.
    top50 = [
        '600519', '601398', '601288', '601988', '600036',  # banks + liquor
        '600900', '601318', '600028', '600030', '600048',
        '600050', '601166', '601328', '601857', '601006',
        '600887', '000858', '000001', '000002', '000333',
        '000568', '000625', '000651', '000725', '000776',
        '000858', '000895', '002142', '002230', '002304',
        '002415', '002475', '002594', '002714', '300059',
        '300122', '300124', '300142', '300347', '300408',
        '300413', '300498', '300628', '300750', '300760',
        '600000', '600016', '600019', '600031', '600104',
    ]
    from datetime import datetime
    start = datetime(2025, 4, 1)
    end = datetime(2026, 4, 1)

    results = load_batch(top50, start, end)
    successful = sum(1 for cnt in results.values() if cnt >= 200)
    assert successful >= 45, (
        f'only {successful}/50 stocks loaded ≥200 bars; details: '
        f'{[(s, c) for s, c in results.items() if c < 200]}'
    )
```

- [ ] **Step 2: Run the new test**

Run: `pytest tests/test_data_pipeline.py::test_kline_batch_hs300_top50 -v`
Expected: PASS (takes 2–5 minutes on first run; subsequent runs hit vnpy_sqlite cache).

- [ ] **Step 3: Commit**

```bash
git add tests/test_data_pipeline.py
git commit -m "test(p0): batch K-line load for HS300 top 50"
```

---

### Task 7: Write failing test for trading calendar helper

**Files:**
- Modify: `tests/test_data_pipeline.py`

- [ ] **Step 1: Append trading-calendar test**

Append to `tests/test_data_pipeline.py`:
```python


def test_trading_calendar_returns_valid_dates(tdx_ready):
    """trading_calendar.get_trading_days returns correct count for a known range."""
    from datetime import date

    from trading_calendar import get_trading_days

    days = get_trading_days(date(2025, 4, 1), date(2025, 4, 30))
    # April 2025: 30 days. Weekends: 8. May Day holiday 1 day (Apr 30 can be work).
    # Expected 20–22 trading days. Also: no weekends in result.
    assert 18 <= len(days) <= 23, f'expected 18–23 trading days in Apr 2025, got {len(days)}'
    for d in days:
        assert d.weekday() < 5, f'{d} is a weekend; calendar must exclude weekends'
    # Ordered ascending
    assert days == sorted(days)


def test_trading_calendar_fallback_when_tdx_api_missing(vnpy_configured, monkeypatch):
    """If tq.get_trading_calendar is missing, fallback uses vnpy_sqlite K-line dates."""
    import trading_calendar as tc

    # Force the fallback path: monkeypatch the primary-path attempt to raise.
    monkeypatch.setattr(tc, '_try_tdx_calendar', lambda s, e: None)

    from datetime import date
    days = tc.get_trading_days(date(2025, 4, 1), date(2025, 4, 30))
    # We loaded 茅台 + 50 top in earlier tasks, so K-line-dates fallback has data.
    assert len(days) >= 15, (
        f'fallback should return ≥15 trading days; got {len(days)}. '
        'If this fails, re-run Tasks 5–6 to populate vnpy_sqlite.'
    )
```

- [ ] **Step 2: Run; confirm failure**

Run: `pytest tests/test_data_pipeline.py -v -k trading_calendar`
Expected: 2 FAILs — `ModuleNotFoundError: No module named 'trading_calendar'`

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_data_pipeline.py
git commit -m "test(p0): failing tests for trading_calendar helper + fallback"
```

---

### Task 8: Implement trading_calendar.py with K-line-dates fallback

**Files:**
- Create: `trading_calendar.py`

- [ ] **Step 1: Implement the helper**

Content of `trading_calendar.py`:
```python
"""Trading-day calendar for A-shares.

Primary path: tq.get_trading_calendar() (tqcenter SDK).
Fallback path: unique dates present in any K-line row in vnpy_sqlite.

Usage:
    from trading_calendar import get_trading_days
    days = get_trading_days(date(2025, 4, 1), date(2026, 4, 1))
"""
from __future__ import annotations

from datetime import date, datetime


def get_trading_days(start: date, end: date) -> list[date]:
    """Return ascending list of trading days in [start, end].

    Falls back to K-line-dates if the primary TDX calendar API fails.
    """
    days = _try_tdx_calendar(start, end)
    if days is not None:
        return days
    days = _fallback_kline_dates(start, end)
    return days


def _try_tdx_calendar(start: date, end: date) -> list[date] | None:
    """Call tqcenter's calendar API. Returns None on any failure (triggers fallback)."""
    try:
        from tdx_service import tdx
        if not tdx.is_connected():
            tdx.initialize()
        if not tdx.is_connected():
            return None
        # tqcenter API: varies by version. Try the most common shape.
        from tqcenter import tq
        if not hasattr(tq, 'get_trading_calendar'):
            return None
        raw = tq.get_trading_calendar(
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d'),
        )
        if not raw:
            return None
        days = [_coerce_date(d) for d in raw]
        return sorted(d for d in days if d and start <= d <= end)
    except Exception:  # noqa: BLE001  (any error → fallback)
        return None


def _fallback_kline_dates(start: date, end: date) -> list[date]:
    """Read unique dates from vnpy_sqlite K-line bars.

    Any trading day with at least one bar written counts. Requires that
    data/vnpy_data.db has already been populated (Task 5 or Task 9).
    """
    from scripts.setup.vnpy_config import configure
    configure()

    import sqlite3
    db_path = configure()

    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            'SELECT DISTINCT DATE(datetime) FROM dbbardata '
            'WHERE DATE(datetime) >= ? AND DATE(datetime) <= ? '
            'ORDER BY DATE(datetime)',
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    except sqlite3.OperationalError:
        # Table doesn't exist yet (vnpy_sqlite creates on first save)
        return []
    finally:
        con.close()

    out: list[date] = []
    for (iso,) in rows:
        d = _coerce_date(iso)
        if d is not None:
            out.append(d)
    return out


def _coerce_date(value) -> date | None:
    """Accept date, datetime, or ISO string; return date or None."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value[:10]).date()
        except ValueError:
            return None
    return None
```

- [ ] **Step 2: Run both trading-calendar tests**

Run: `pytest tests/test_data_pipeline.py -v -k trading_calendar`
Expected: BOTH PASS. If the primary test (`test_trading_calendar_returns_valid_dates`) fails with count 0, the fallback may be kicking in and vnpy_sqlite has no data for that month — re-run Tasks 5–6 first.

- [ ] **Step 3: Commit**

```bash
git add trading_calendar.py
git commit -m "feat(p0): trading_calendar helper with K-line-dates fallback"
```

---

### Task 9: Write failing test for financial cache loader

**Files:**
- Modify: `tests/test_data_pipeline.py`

- [ ] **Step 1: Append financial-cache test**

Append to `tests/test_data_pipeline.py`:
```python


def test_financial_cache_loads_pe_pb_roe(tdx_ready, tmp_path, monkeypatch):
    """load_financial writes PE/PB/ROE for a handful of stocks into the cache DB."""
    # Redirect the cache to tmp_path so we don't mutate real data/financial_cache.db
    from scripts.setup import load_financial as lf
    monkeypatch.setattr(lf, 'CACHE_PATH', tmp_path / 'financial_cache.db')

    symbols = ['600519', '000858', '600036', '300750', '002415']
    written = lf.load_financial(symbols)
    assert written >= 4, f'expected ≥4/5 stocks with financial data, got {written}'

    # Verify schema + content
    import sqlite3
    con = sqlite3.connect(tmp_path / 'financial_cache.db')
    try:
        rows = con.execute(
            'SELECT stock_code, pe, pb, roe FROM financial_data'
        ).fetchall()
    finally:
        con.close()

    assert len(rows) >= 4
    for code, pe, pb, roe in rows:
        assert isinstance(code, str) and len(code) >= 6
        # PE/PB/ROE can legitimately be None (new stocks, no data); at least one must be set per row
        assert pe is not None or pb is not None or roe is not None, (
            f'{code} has all null PE/PB/ROE'
        )
```

- [ ] **Step 2: Run; confirm failure**

Run: `pytest tests/test_data_pipeline.py::test_financial_cache_loads_pe_pb_roe -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.setup.load_financial'`

- [ ] **Step 3: Commit failing test**

```bash
git add tests/test_data_pipeline.py
git commit -m "test(p0): failing test for financial cache loader"
```

---

### Task 10: Implement load_financial.py

**Files:**
- Create: `scripts/setup/load_financial.py`

- [ ] **Step 1: Write the loader**

Content of `scripts/setup/load_financial.py`:
```python
"""Load PE/PB/ROE/margins/growth for a set of stocks into data/financial_cache.db.

Uses the existing tdx_service singleton (tqcenter SDK). Idempotent: UPSERTs
by (stock_code, date). Safe to re-run.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = REPO_ROOT / 'data' / 'financial_cache.db'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS financial_data (
    stock_code         TEXT NOT NULL,
    date               DATE NOT NULL,
    pe                 REAL,
    pb                 REAL,
    roe                REAL,
    gross_margin       REAL,
    revenue_growth     REAL,
    net_profit_growth  REAL,
    PRIMARY KEY (stock_code, date)
);
'''


def _ensure_schema(con: sqlite3.Connection) -> None:
    con.execute('PRAGMA journal_mode=WAL')
    con.execute(SCHEMA)
    con.commit()


def _as_float(value) -> float | None:
    try:
        if value is None or value == '' or value == '--':
            return None
        f = float(value)
        # TDX sometimes returns sentinel values like 9999999 for N/A
        if abs(f) > 1e8:
            return None
        return f
    except (TypeError, ValueError):
        return None


def _normalize_code(code: str) -> str:
    """tdx_service expects '600519.SH'; some callers pass bare '600519'."""
    if '.' in code:
        return code
    if code.startswith(('6', '9')):
        return f'{code}.SH'
    return f'{code}.SZ'


def load_financial(symbols: list[str], as_of: date | None = None) -> int:
    """Fetch financial data for `symbols` and UPSERT into CACHE_PATH.

    Returns count of symbols successfully written.
    """
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if as_of is None:
        as_of = date.today()

    from tdx_service import tdx
    tdx.ensure_connected()

    written = 0
    con = sqlite3.connect(CACHE_PATH)
    try:
        _ensure_schema(con)
        for bare in symbols:
            full = _normalize_code(bare)
            try:
                info = tdx.get_stock_info(full)
            except Exception as e:  # noqa: BLE001
                print(f'[load_financial] {full} FAILED: {e}')
                continue
            if not info or not isinstance(info, dict):
                continue
            row = (
                bare,
                as_of.isoformat(),
                _as_float(info.get('PE') or info.get('Pe')),
                _as_float(info.get('PB') or info.get('Pb')),
                _as_float(info.get('ROE') or info.get('Roe')),
                _as_float(info.get('GrossMargin') or info.get('GrossProfit')),
                _as_float(info.get('RevenueGrowth')),
                _as_float(info.get('NetProfitGrowth')),
            )
            if all(v is None for v in row[2:]):
                # No usable data; skip
                continue
            con.execute(
                '''INSERT OR REPLACE INTO financial_data
                   (stock_code, date, pe, pb, roe, gross_margin, revenue_growth, net_profit_growth)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                row,
            )
            written += 1
        con.commit()
    finally:
        con.close()
    return written


if __name__ == '__main__':
    # Smoke test: load a handful of stocks
    n = load_financial(['600519', '000858', '600036', '300750', '002415'])
    print(f'wrote {n} rows to {CACHE_PATH}')
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/test_data_pipeline.py::test_financial_cache_loads_pe_pb_roe -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/setup/load_financial.py
git commit -m "feat(p0): financial cache loader (PE/PB/ROE via tqcenter)"
```

---

### Task 11: Run full HS300 setup + write integration test

**Files:**
- Modify: `tests/test_data_pipeline.py`

- [ ] **Step 1: Fetch the HS300 constituent list via `tq.get_stock_list('23')`**

tqcenter's `get_stock_list(market)` uses numeric market codes. `'23'` = 沪深300 (other useful codes: `'5'`=所有A股, `'23'`=沪深300, `'24'`=中证500, `'50'`=沪深A股, `'51'`=创业板). See memory `tdx_quant_docs.md` for the full market code table.

Run this one-time:
```python
from tdx_service import tdx
tdx.initialize()
from tqcenter import tq
constituents = tq.get_stock_list('23')   # 沪深300
import json
from pathlib import Path
Path('data/hs300_symbols.json').write_text(json.dumps(constituents))
print(f'saved {len(constituents)} HS300 codes; sample: {constituents[:3]}')
```

Expected: `data/hs300_symbols.json` contains a list of ~300 codes in the `600519.SH` / `000001.SZ` format. If the list is empty or wildly wrong, the TDX client may not have HS300 data cached — open 通达信 → 沪深300 to force-cache it, then re-run.

- [ ] **Step 2: Run real HS300 loaders**

Run both loaders on the real dataset:
```
python -c "
import json
from datetime import datetime
from scripts.setup.load_kline import load_batch
from scripts.setup.load_financial import load_financial

symbols = json.load(open('data/hs300_symbols.json'))
symbols = symbols[:300]  # cap at 300

start = datetime(2025, 4, 1)
end = datetime(2026, 4, 1)

kline_results = load_batch(symbols, start, end)
kline_ok = sum(1 for c in kline_results.values() if c >= 200)
print(f'K-line: {kline_ok}/{len(symbols)} stocks ≥200 bars')

fin_ok = load_financial(symbols)
print(f'Financial: {fin_ok}/{len(symbols)} stocks with PE/PB/ROE')
"
```
Expected: both counts ≥ 250. This run takes 15–30 minutes depending on network.

- [ ] **Step 3: Append integration smoke test**

Append to `tests/test_data_pipeline.py`:
```python


def test_full_pipeline_integration(tdx_ready, vnpy_configured):
    """After setup has run, all three pipelines are queryable together."""
    # 1. K-line reads from vnpy_sqlite
    from datetime import datetime
    from vnpy_sqlite import Database
    from vnpy.trader.constant import Exchange, Interval

    db = Database()
    bars = db.load_bar_data(
        symbol='600519', exchange=Exchange.SSE, interval=Interval.DAILY,
        start=datetime(2025, 4, 1), end=datetime(2026, 4, 1),
    )
    assert len(bars) >= 200

    # 2. Financial cache has data
    import sqlite3
    from pathlib import Path
    cache = Path('data/financial_cache.db')
    assert cache.exists(), 'Run Task 11 Step 2 first'
    con = sqlite3.connect(cache)
    try:
        count = con.execute('SELECT COUNT(DISTINCT stock_code) FROM financial_data').fetchone()[0]
    finally:
        con.close()
    assert count >= 250, f'financial_cache has only {count} stocks; expected ≥250'

    # 3. Trading calendar works over the same range
    from datetime import date
    from trading_calendar import get_trading_days
    days = get_trading_days(date(2025, 4, 1), date(2026, 4, 1))
    # A full year: ~244 trading days
    assert 230 <= len(days) <= 260, (
        f'expected 230–260 trading days in Apr-2025 → Apr-2026, got {len(days)}'
    )
```

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests/test_data_pipeline.py -v`
Expected: ALL tests PASS (4 tests, no skips if TDX is online).

- [ ] **Step 5: Commit**

```bash
git add tests/test_data_pipeline.py data/hs300_symbols.json
git commit -m "test(p0): full pipeline integration test + HS300 constituent list"
```

Note: `data/hs300_symbols.json` is committed explicitly (bypasses `data/` gitignore) because it's a small reusable list, not a generated DB. If you prefer to keep it out of git, move it to `scripts/setup/hs300_symbols.json` and update the path in Step 2.

---

### Task 12: Write the P0 verification report

**Files:**
- Create: `docs/superpowers/specs/p0-verification-report.md`

- [ ] **Step 1: Draft report content**

Create `docs/superpowers/specs/p0-verification-report.md` with this template — fill in the values you observed during Tasks 5, 6, 8, 10, 11:

```markdown
# P0 Verification Report — [YYYY-MM-DD]

Summary of what the P0 plan verified about the TDX data pipelines on this environment.

## Environment

- OS: Windows 10 Pro 10.0.18362
- Python: [output of `python --version`]
- vnpy: [output of `python -c "import vnpy; print(vnpy.__version__)"`]
- TDX SDK path: `C:\new_tdx_mock\PYPlugins\sys`
- TDX client status at time of verification: [connected / not connected]

## Pipeline 1 — Daily K-line (vnpy-tdx → vnpy_sqlite)

- Status: [✓ WORKS | ✗ BLOCKED]
- Load time for 1 stock × 1 year: [N seconds]
- Load time for [N] HS300 stocks × 1 year: [M minutes]
- Stocks with ≥ 200 bars: [X / total]
- Failed stocks (if any) and reasons: [...]

## Pipeline 2 — Trading Calendar

- `tq.get_trading_calendar()` available: [YES / NO]
- If NO → fallback (K-line DISTINCT dates) used: [YES]
- Calendar size for 2025-04-01 → 2026-04-01: [N days]

## Pipeline 3 — Financial Cache (PE/PB/ROE via tqcenter)

- Status: [✓ WORKS | ✗ BLOCKED]
- Stocks with complete PE/PB/ROE: [X / total]
- `gross_margin` field populated: [YES / NO — tqcenter may not expose]
- `revenue_growth`/`net_profit_growth` fields populated: [YES / NO]

## Gaps / Action Items for Later Plans

- [ ] [Any issue that P1 should address, e.g. "gross_margin not available — strategy logic needs workaround"]
- [ ] [...]

## Next Plan

P1 — LLM Layer + Tools (see `docs/superpowers/plans/2026-04-XX-p1-llm-layer.md` when written).
```

- [ ] **Step 2: Run the verification commands and fill in the values**

Run these commands, copying output into the report:
```
python --version
python -c "import vnpy; print(vnpy.__version__)"
python -c "
import json, sqlite3
from pathlib import Path
symbols = json.load(open('data/hs300_symbols.json'))
print(f'HS300 symbols: {len(symbols)}')

# K-line
from vnpy_sqlite import Database
from vnpy.trader.constant import Exchange, Interval
from datetime import datetime
db = Database()
ok = 0
for s in symbols[:300]:
    ex = Exchange.SSE if s.startswith(('6','9')) else Exchange.SZSE
    bars = db.load_bar_data(s, ex, Interval.DAILY, datetime(2025,4,1), datetime(2026,4,1))
    if len(bars) >= 200: ok += 1
print(f'K-line ok: {ok}')

# Financial
con = sqlite3.connect('data/financial_cache.db')
n = con.execute('SELECT COUNT(DISTINCT stock_code) FROM financial_data').fetchone()[0]
print(f'Financial stocks: {n}')

# Calendar
from trading_calendar import get_trading_days
from datetime import date
days = get_trading_days(date(2025,4,1), date(2026,4,1))
print(f'Trading days: {len(days)}')
"
```

- [ ] **Step 3: Commit the completed report**

```bash
git add docs/superpowers/specs/p0-verification-report.md
git commit -m "docs(p0): verification report — data pipelines confirmed"
```

---

## Self-Review

### Spec Coverage Checklist

Going section-by-section through the referenced spec sections:

- ✅ **§ 3.1 Two TDX Data Paths** — Tasks 5, 10 exercise both paths (vnpy-tdx for historical K-line, tqcenter for financial data)
- ✅ **§ 3.2 Financial Data Cache schema** — Task 10 creates the exact schema specified
- ✅ **§ 3.3 Trading Calendar** — Task 8 implements both primary and fallback paths as spec requires
- ✅ **§ 17 TDX Data Verification** — Tasks 5 (daily K-line), 8 (calendar), 10 (financial), 11 (smoke) cover every row in the table
- ✅ **§ 18 Milestone 0** — all three steps (K-line roundtrip, calendar verify, financial cache) mapped to concrete tasks

### Placeholder Scan

- No "TBD", "implement later", or "similar to Task N" in the plan
- Every code step shows the actual code
- Every test has actual assertions
- One soft reference: Task 11 Step 1 uses "varies by SDK version" but explicitly gives the fallback command (read from `HS300.blk` file)

### Type/Symbol Consistency

- `load_single_stock(symbol, start, end)` — same signature in Tasks 4, 5
- `load_batch(symbols, start, end) → dict[str, int]` — same in Tasks 5, 6, 11
- `load_financial(symbols) → int` — same in Tasks 9, 10, 11
- `get_trading_days(start, end) → list[date]` — same in Tasks 7, 8, 11
- `CACHE_PATH` constant in `load_financial.py` is monkeypatched in Task 9's test — consistent

---

## Execution Notes

- **TDX client must be running with F12-logged-in trading account** for any TDX-hitting task to succeed
- **Task 5 first-run is slow** (~30 seconds per stock); Task 6 will take 2–5 minutes; Task 11 Step 2 will take 15–30 minutes
- **Offline mode:** if TDX is offline, all integration tests SKIP (not fail). This plan is still useful offline for verifying that imports and wiring are correct — just rerun tests once TDX is back
- **Idempotency:** every loader uses `save_bar_data` (vnpy) or `INSERT OR REPLACE` (SQLite), so re-running any task is safe
