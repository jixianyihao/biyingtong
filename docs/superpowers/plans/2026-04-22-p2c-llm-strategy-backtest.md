# P2c: LLM Strategy + E2E Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the LLM agent pipeline to vnpy backtest. Given `(agent_id, date_range)`, the system runs an LLM-driven portfolio strategy, validates each decision through P2b's `ValidationEngine`, tags bars with cross-cutoff zones, and persists a `BacktestResult` with a quality-gate label. Same inputs replay from cache — no double-charged API calls.

**Architecture:**
- **LLM decision cache** keyed by `(agent_id, date, portfolio_hash, prompt_hash)` stored in SQLite. First run hits the API; subsequent runs read cache and skip tool loop entirely.
- **AgentRunner** owns the tool loop: build prompt → LLM call → iterate tool_use → on `place_decision` call `ValidationEngine.validate()` → execute validated (possibly modified) decision. Modifications execute silently; audit trail captures full history.
- **LLMPortfolioStrategy** subclasses `vnpy_portfoliostrategy.StrategyTemplate`. On each bar, delegates to `AgentRunner` and translates returned decisions into vnpy orders.
- **Cross-cutoff zone classifier** tags every bar as `pollution` (before cutoff), `buffer` (cutoff to cutoff+60d), or `clean` (≥60d post-cutoff). Stats aggregated per zone to detect divergence.
- **BacktestRunner** orchestrates: load agent → configure vnpy engine → feed bars from `storage.kline()` → collect daily P&L → compute `BacktestStats` per zone → evaluate quality gate → persist `BacktestResult`.
- **Multi-persona** comparison: run N agents sequentially on the same window, producing N separate result rows that share `backtest_session_id`. Post-processing (baselines, rating) deferred to P2d.

**Tech stack:** Python 3.10+, vnpy 4.x / vnpy_portfoliostrategy 1.2, sqlite3, existing P1 `llm/` + `tools/` + P2b `validation/`.

---

## File Structure

### New files
- `data_schema/backtest_state.py` — DDL for `backtest_results` + `llm_decision_cache` + `backtest_sessions`
- `backtest/__init__.py`
- `backtest/base.py` — `BacktestStats`, `ZoneStats`, `BacktestResult`, `CachedDecision` dataclasses
- `backtest/cutoff.py` — `classify_date` + `zone_windows`
- `backtest/portfolio_adapter.py` — vnpy engine state → portfolio dict
- `backtest/stats.py` — daily P&L list → per-zone `BacktestStats`
- `backtest/strategy.py` — `LLMPortfolioStrategy` (vnpy subclass)
- `backtest/runner.py` — `BacktestRunner.run()` orchestrator
- `agents/__init__.py`
- `agents/prompt_builder.py` — user_message builder for LLM call
- `agents/runner.py` — `AgentRunner` tool loop
- `storage/sqlite_backtests.py` — `SQLiteBacktestResultStore`
- `storage/sqlite_llm_cache.py` — `SQLiteLLMDecisionCache`
- Tests per module — one `test_*.py` per file above plus E2E and multi-persona fixtures

### Modified files
- `storage/base.py` — append `BacktestResultStore`, `LLMDecisionCacheStore` Protocols + `BacktestResult` dataclass
- `storage/__init__.py` — add `backtests()` / `llm_cache()` factories + setters + reset
- `validation/handlers/position_max_pct.py` — floor `modification['shares']` to multiple of 100 (A-share lot rule, P2b leftover)

---

## Task 1: Schemas

**Files:**
- Create: `data_schema/backtest_state.py`
- Test: `tests/test_backtest_schemas.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_backtest_schemas.py
"""DDL sanity checks for P2c backtest tables."""
import sqlite3


def test_schemas_create_expected_tables(tmp_path):
    from data_schema.backtest_state import (
        SCHEMA_BACKTEST_SESSIONS, SCHEMA_BACKTEST_RESULTS,
        SCHEMA_LLM_DECISION_CACHE,
    )
    db = tmp_path / 'x.db'
    con = sqlite3.connect(db)
    try:
        con.executescript(SCHEMA_BACKTEST_SESSIONS)
        con.executescript(SCHEMA_BACKTEST_RESULTS)
        con.executescript(SCHEMA_LLM_DECISION_CACHE)
        names = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    finally:
        con.close()
    assert {'backtest_sessions', 'backtest_results',
            'llm_decision_cache'} <= names


def test_backtest_results_has_session_fk_column():
    from data_schema.backtest_state import SCHEMA_BACKTEST_RESULTS
    assert 'session_id' in SCHEMA_BACKTEST_RESULTS


def test_llm_cache_uses_composite_key():
    from data_schema.backtest_state import SCHEMA_LLM_DECISION_CACHE
    assert 'PRIMARY KEY' in SCHEMA_LLM_DECISION_CACHE
    assert 'cache_key' in SCHEMA_LLM_DECISION_CACHE


def test_indexes_present():
    from data_schema.backtest_state import SCHEMA_BACKTEST_RESULTS
    assert 'results_by_session' in SCHEMA_BACKTEST_RESULTS
    assert 'results_by_agent' in SCHEMA_BACKTEST_RESULTS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backtest_schemas.py -v`
Expected: `ModuleNotFoundError: data_schema.backtest_state`

- [ ] **Step 3: Create `data_schema/backtest_state.py`**

```python
"""DDL for P2c backtest + LLM decision cache tables."""

SCHEMA_BACKTEST_SESSIONS = '''
CREATE TABLE IF NOT EXISTS backtest_sessions (
    id           TEXT PRIMARY KEY,
    start_date   TEXT NOT NULL,
    end_date     TEXT NOT NULL,
    agent_ids    TEXT NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes        TEXT
);
'''

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
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS results_by_session ON backtest_results(session_id);
CREATE INDEX IF NOT EXISTS results_by_agent   ON backtest_results(agent_id, created_at DESC);
'''

SCHEMA_LLM_DECISION_CACHE = '''
CREATE TABLE IF NOT EXISTS llm_decision_cache (
    cache_key        TEXT PRIMARY KEY,
    agent_id         TEXT NOT NULL,
    date             TEXT NOT NULL,
    response_json    TEXT NOT NULL,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS cache_by_agent_date
    ON llm_decision_cache(agent_id, date);
'''
```

- [ ] **Step 4: Verify tests pass**

Run: `python -m pytest tests/test_backtest_schemas.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add data_schema/backtest_state.py tests/test_backtest_schemas.py
git commit -m "feat(p2c): schemas for backtest_sessions + results + llm cache"
```

---

## Task 2: Backtest dataclasses

**Files:**
- Create: `backtest/__init__.py`, `backtest/base.py`
- Test: `tests/test_backtest_base.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_backtest_base.py
"""Backtest core dataclasses."""


def test_backtest_stats_fields():
    from backtest.base import BacktestStats
    s = BacktestStats(
        sharpe=1.2, max_drawdown_pct=-12.0, trade_count=30,
        win_rate=55.0, max_daily_loss_pct=-2.0,
        total_return_pct=18.0, final_equity=1_180_000.0,
    )
    assert s.sharpe == 1.2
    assert s.final_equity == 1_180_000.0


def test_zone_stats_default_zone_labels():
    from backtest.base import ZoneStats
    z = ZoneStats(zone='pollution', days=100, stats={})
    assert z.zone == 'pollution'
    assert z.days == 100


def test_backtest_result_fields():
    from backtest.base import BacktestResult, BacktestStats
    stats = BacktestStats(sharpe=0.5, max_drawdown_pct=-5,
                          trade_count=10, win_rate=60,
                          max_daily_loss_pct=-1,
                          total_return_pct=5, final_equity=105)
    r = BacktestResult(
        id='r1', session_id='s1', agent_id='a1',
        persona_id='linyuan', model_id='claude-opus-4-7',
        start_date='2024-01-01', end_date='2024-02-01',
        initial_capital=100.0, stats=stats, zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
    )
    assert r.quality_gate_label == 'pass'
    assert r.stats.sharpe == 0.5


def test_cached_decision_roundtrip_to_dict():
    from backtest.base import CachedDecision
    d = CachedDecision(
        agent_id='a1', date='2024-01-15',
        portfolio_hash='abc', prompt_hash='xyz',
        decisions=[{'action': 'buy', 'code': 'X', 'shares': 100, 'price': 10.0}],
    )
    assert d.decisions[0]['action'] == 'buy'
    assert d.cache_key == CachedDecision.build_key(
        'a1', '2024-01-15', 'abc', 'xyz',
    )
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_backtest_base.py -v`
Expected: `ModuleNotFoundError: backtest`

- [ ] **Step 3: Implement**

```python
# backtest/__init__.py
"""Backtest engine — LLM-driven vnpy PortfolioStrategy (P2c)."""
```

```python
# backtest/base.py
"""Core dataclasses for the P2c backtest pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BacktestStats:
    """Aggregate stats over a window — feeds quality_gate."""
    sharpe: float
    max_drawdown_pct: float      # negative (e.g. -12.0 means -12%)
    trade_count: int
    win_rate: float              # 0-100
    max_daily_loss_pct: float    # negative
    total_return_pct: float
    final_equity: float


@dataclass(frozen=True)
class ZoneStats:
    """Stats restricted to one cross-cutoff zone."""
    zone: str                    # 'pollution' | 'buffer' | 'clean'
    days: int
    stats: dict                  # serialized BacktestStats or {} if days < 2


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


@dataclass
class CachedDecision:
    """Replay entry for one decision-day."""
    agent_id: str
    date: str
    portfolio_hash: str
    prompt_hash: str
    decisions: list              # list[dict] of (possibly modified) decisions

    @property
    def cache_key(self) -> str:
        return self.build_key(self.agent_id, self.date,
                              self.portfolio_hash, self.prompt_hash)

    @staticmethod
    def build_key(agent_id: str, date: str,
                  portfolio_hash: str, prompt_hash: str) -> str:
        return f'{agent_id}|{date}|{portfolio_hash}|{prompt_hash}'
```

- [ ] **Step 4: Verify tests pass**

Run: `python -m pytest tests/test_backtest_base.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add backtest/ tests/test_backtest_base.py
git commit -m "feat(p2c): BacktestStats + ZoneStats + BacktestResult + CachedDecision"
```

---

## Task 3: Storage Protocols for backtests + llm_cache

**Files:**
- Modify: `storage/base.py` (append)
- Test: `tests/test_storage_base.py` (append)

- [ ] **Step 1: Append failing tests**

```python
def test_backtest_result_store_protocol_exists():
    from storage.base import BacktestResultStore
    for m in ('init_schema', 'insert', 'get', 'list_for_agent',
              'list_for_session'):
        assert hasattr(BacktestResultStore, m), f'missing {m}'


def test_llm_decision_cache_store_protocol_exists():
    from storage.base import LLMDecisionCacheStore
    for m in ('init_schema', 'get', 'put', 'has'):
        assert hasattr(LLMDecisionCacheStore, m), f'missing {m}'
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_storage_base.py -v`
Expected: 2 new fails (ImportError)

- [ ] **Step 3: Append to `storage/base.py`**

```python
# --- Added in P2c ---


@runtime_checkable
class BacktestResultStore(Protocol):
    """backtest_sessions + backtest_results tables."""
    def init_schema(self) -> None: ...
    def insert(self, result) -> None:
        """Persist a BacktestResult. Idempotent by id."""
        ...
    def get(self, result_id: str):
        """Returns a BacktestResult or None."""
        ...
    def list_for_agent(self, agent_id: str, limit: int = 50) -> list:
        """Most recent first."""
        ...
    def list_for_session(self, session_id: str) -> list:
        """All results under one session, agent_id ASC."""
        ...
    def create_session(self, session_id: str, start_date: str,
                       end_date: str, agent_ids: list[str],
                       notes: str | None = None) -> None:
        """Idempotent by id."""
        ...


@runtime_checkable
class LLMDecisionCacheStore(Protocol):
    """Per-(agent, date, state) decision replay cache."""
    def init_schema(self) -> None: ...
    def has(self, cache_key: str) -> bool: ...
    def get(self, cache_key: str):
        """Returns CachedDecision or None."""
        ...
    def put(self, entry) -> None:
        """Upsert a CachedDecision."""
        ...
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_storage_base.py -v`
Expected: all previous + 2 new PASSED

- [ ] **Step 5: Commit**

```bash
git add storage/base.py tests/test_storage_base.py
git commit -m "feat(p2c): BacktestResultStore + LLMDecisionCacheStore Protocols"
```

---

## Task 4: SQLiteBacktestResultStore

**Files:**
- Create: `storage/sqlite_backtests.py`
- Test: `tests/test_storage_backtests.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_storage_backtests.py
"""SQLiteBacktestResultStore — sessions + results persistence."""


def _result(id='r1', session_id='s1', agent_id='a1',
            label='pass', **kw):
    from backtest.base import BacktestStats, BacktestResult
    stats = BacktestStats(
        sharpe=1.0, max_drawdown_pct=-10.0, trade_count=20,
        win_rate=50.0, max_daily_loss_pct=-3.0,
        total_return_pct=15.0, final_equity=1_150_000.0,
    )
    return BacktestResult(
        id=id, session_id=session_id, agent_id=agent_id,
        persona_id=kw.get('persona_id', 'linyuan'),
        model_id=kw.get('model_id', 'claude-opus-4-7'),
        start_date='2024-01-01', end_date='2024-03-01',
        initial_capital=1_000_000.0, stats=stats, zone_stats=[],
        quality_gate_label=label, quality_gate_criteria={},
        final_equity=1_150_000.0,
    )


def test_create_session_idempotent(tmp_path):
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.create_session('s1', '2024-01-01', '2024-03-01', ['a1', 'a2'])
    s.create_session('s1', '2024-01-01', '2024-03-01', ['a1', 'a2'])  # idempotent
    # No exception — single row


def test_insert_then_get(tmp_path):
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.create_session('s1', '2024-01-01', '2024-03-01', ['a1'])
    s.insert(_result())
    got = s.get('r1')
    assert got is not None
    assert got.agent_id == 'a1'
    assert got.quality_gate_label == 'pass'
    assert got.stats.sharpe == 1.0


def test_list_for_session_groups_results(tmp_path):
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.create_session('s1', '2024-01-01', '2024-03-01', ['a1', 'a2'])
    s.insert(_result(id='r1', session_id='s1', agent_id='a2'))
    s.insert(_result(id='r2', session_id='s1', agent_id='a1'))
    s.insert(_result(id='r3', session_id='s2', agent_id='a1'))
    results = s.list_for_session('s1')
    assert {r.id for r in results} == {'r1', 'r2'}


def test_list_for_agent_recent_first(tmp_path):
    import time
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.create_session('s1', '2024-01-01', '2024-03-01', ['a1'])
    s.insert(_result(id='r1', agent_id='a1'))
    time.sleep(0.02)
    s.insert(_result(id='r2', agent_id='a1'))
    lst = s.list_for_agent('a1')
    assert [r.id for r in lst] == ['r2', 'r1']


def test_zone_stats_roundtrips(tmp_path):
    from backtest.base import ZoneStats
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.create_session('s1', '2024-01-01', '2024-03-01', ['a1'])
    r = _result()
    r.zone_stats = [ZoneStats(zone='pollution', days=60, stats={'sharpe': 1.0}),
                    ZoneStats(zone='clean', days=30, stats={'sharpe': 0.5})]
    s.insert(r)
    got = s.get(r.id)
    assert len(got.zone_stats) == 2
    assert got.zone_stats[0].zone == 'pollution'
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_storage_backtests.py -v`
Expected: 5 FAIL

- [ ] **Step 3: Implement**

```python
# storage/sqlite_backtests.py
"""SQLiteBacktestResultStore — sessions + results."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from data_schema.backtest_state import (
    SCHEMA_BACKTEST_SESSIONS, SCHEMA_BACKTEST_RESULTS,
)

from .base import BacktestResultStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _row_to_result(row):
    from backtest.base import BacktestResult, BacktestStats, ZoneStats
    stats_d = json.loads(row[9])
    stats = BacktestStats(**stats_d)
    zone_raw = json.loads(row[10])
    zones = [ZoneStats(**z) for z in zone_raw]
    return BacktestResult(
        id=row[0], session_id=row[1], agent_id=row[2],
        persona_id=row[3], model_id=row[4],
        start_date=row[5], end_date=row[6],
        initial_capital=row[7], final_equity=row[8],
        stats=stats, zone_stats=zones,
        quality_gate_label=row[11],
        quality_gate_criteria=json.loads(row[12]),
    )


class SQLiteBacktestResultStore(BacktestResultStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_BACKTEST_SESSIONS)
            con.executescript(SCHEMA_BACKTEST_RESULTS)
            con.commit()
        finally:
            con.close()

    def create_session(self, session_id, start_date, end_date,
                       agent_ids, notes=None):
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_BACKTEST_SESSIONS)
            con.execute(
                '''INSERT OR IGNORE INTO backtest_sessions
                   (id, start_date, end_date, agent_ids, notes)
                   VALUES (?,?,?,?,?)''',
                (session_id, start_date, end_date,
                 json.dumps(agent_ids, ensure_ascii=False), notes),
            )
            con.commit()
        finally:
            con.close()

    def insert(self, result) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_BACKTEST_RESULTS)
            zone_serial = json.dumps(
                [asdict(z) for z in result.zone_stats], ensure_ascii=False,
            )
            con.execute(
                '''INSERT OR REPLACE INTO backtest_results
                   (id, session_id, agent_id, persona_id, model_id,
                    start_date, end_date, initial_capital, final_equity,
                    stats_json, zone_stats_json,
                    quality_gate_label, quality_gate_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (result.id, result.session_id, result.agent_id,
                 result.persona_id, result.model_id,
                 result.start_date, result.end_date,
                 result.initial_capital, result.final_equity,
                 json.dumps(asdict(result.stats), ensure_ascii=False),
                 zone_serial,
                 result.quality_gate_label,
                 json.dumps(result.quality_gate_criteria, ensure_ascii=False)),
            )
            con.commit()
        finally:
            con.close()

    def _select_cols(self):
        return ('id, session_id, agent_id, persona_id, model_id, '
                'start_date, end_date, initial_capital, final_equity, '
                'stats_json, zone_stats_json, quality_gate_label, '
                'quality_gate_json')

    def get(self, result_id: str):
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                f'SELECT {self._select_cols()} '
                f'FROM backtest_results WHERE id = ?',
                (result_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return _row_to_result(row) if row else None

    def list_for_agent(self, agent_id: str, limit: int = 50):
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                f'SELECT {self._select_cols()} '
                f'FROM backtest_results WHERE agent_id = ? '
                f'ORDER BY created_at DESC, rowid DESC LIMIT ?',
                (agent_id, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_result(r) for r in rows]

    def list_for_session(self, session_id: str):
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                f'SELECT {self._select_cols()} '
                f'FROM backtest_results WHERE session_id = ? '
                f'ORDER BY agent_id ASC',
                (session_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_result(r) for r in rows]
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_storage_backtests.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add storage/sqlite_backtests.py tests/test_storage_backtests.py
git commit -m "feat(p2c): SQLiteBacktestResultStore with sessions + zone stats"
```

---

## Task 5: SQLiteLLMDecisionCache

**Files:**
- Create: `storage/sqlite_llm_cache.py`
- Test: `tests/test_storage_llm_cache.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_storage_llm_cache.py
"""SQLiteLLMDecisionCache — per-decision-day replay."""


def _entry(key_suffix=''):
    from backtest.base import CachedDecision
    return CachedDecision(
        agent_id='a1', date='2024-01-15',
        portfolio_hash='ph' + key_suffix,
        prompt_hash='rh' + key_suffix,
        decisions=[{'action': 'buy', 'code': 'X.SH',
                    'shares': 100, 'price': 10.0,
                    'reason': 'good value and growth prospects',
                    'thinking': 'full thinking trace'}],
    )


def test_has_empty(tmp_path):
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    c = SQLiteLLMDecisionCache(tmp_path=tmp_path)
    c.init_schema()
    assert c.has('nope') is False
    assert c.get('nope') is None


def test_put_then_get(tmp_path):
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    c = SQLiteLLMDecisionCache(tmp_path=tmp_path)
    c.init_schema()
    e = _entry()
    c.put(e)
    assert c.has(e.cache_key) is True
    got = c.get(e.cache_key)
    assert got is not None
    assert got.decisions[0]['code'] == 'X.SH'


def test_put_is_idempotent(tmp_path):
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    c = SQLiteLLMDecisionCache(tmp_path=tmp_path)
    c.init_schema()
    c.put(_entry())
    c.put(_entry())  # same key
    assert c.has(_entry().cache_key) is True


def test_distinct_keys_separate(tmp_path):
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    c = SQLiteLLMDecisionCache(tmp_path=tmp_path)
    c.init_schema()
    c.put(_entry(key_suffix='A'))
    c.put(_entry(key_suffix='B'))
    assert c.has(_entry(key_suffix='A').cache_key)
    assert c.has(_entry(key_suffix='B').cache_key)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_storage_llm_cache.py -v`
Expected: 4 FAIL

- [ ] **Step 3: Implement**

```python
# storage/sqlite_llm_cache.py
"""SQLiteLLMDecisionCache — (agent,date,portfolio,prompt) → decisions replay."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from data_schema.backtest_state import SCHEMA_LLM_DECISION_CACHE

from .base import LLMDecisionCacheStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


class SQLiteLLMDecisionCache(LLMDecisionCacheStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_LLM_DECISION_CACHE)
            con.commit()
        finally:
            con.close()

    def has(self, cache_key: str) -> bool:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                'SELECT 1 FROM llm_decision_cache WHERE cache_key = ?',
                (cache_key,),
            ).fetchone()
        except sqlite3.OperationalError:
            return False
        finally:
            con.close()
        return row is not None

    def get(self, cache_key: str):
        from backtest.base import CachedDecision
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                '''SELECT agent_id, date, response_json
                   FROM llm_decision_cache WHERE cache_key = ?''',
                (cache_key,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        if row is None:
            return None
        payload = json.loads(row[2])
        return CachedDecision(
            agent_id=row[0], date=row[1],
            portfolio_hash=payload['portfolio_hash'],
            prompt_hash=payload['prompt_hash'],
            decisions=payload['decisions'],
        )

    def put(self, entry) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_LLM_DECISION_CACHE)
            payload = json.dumps({
                'portfolio_hash': entry.portfolio_hash,
                'prompt_hash': entry.prompt_hash,
                'decisions': entry.decisions,
            }, ensure_ascii=False)
            con.execute(
                '''INSERT OR REPLACE INTO llm_decision_cache
                   (cache_key, agent_id, date, response_json)
                   VALUES (?,?,?,?)''',
                (entry.cache_key, entry.agent_id, entry.date, payload),
            )
            con.commit()
        finally:
            con.close()
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_storage_llm_cache.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add storage/sqlite_llm_cache.py tests/test_storage_llm_cache.py
git commit -m "feat(p2c): SQLiteLLMDecisionCache with has/get/put replay semantics"
```

---

## Task 6: Storage factories for backtests + llm_cache

**Files:**
- Modify: `storage/__init__.py`
- Test: `tests/test_storage_factories_p2c.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_storage_factories_p2c.py
"""Factory + set_* + reset coverage for P2c stores."""


def test_backtests_factory_singleton():
    import storage
    storage.reset()
    a = storage.backtests()
    assert storage.backtests() is a


def test_llm_cache_factory_singleton():
    import storage
    storage.reset()
    a = storage.llm_cache()
    assert storage.llm_cache() is a


def test_set_backtests_overrides(tmp_path):
    import storage
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    storage.set_backtests(s)
    assert storage.backtests() is s


def test_set_llm_cache_overrides(tmp_path):
    import storage
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    s = SQLiteLLMDecisionCache(tmp_path=tmp_path)
    storage.set_llm_cache(s)
    assert storage.llm_cache() is s


def test_reset_clears_p2c_stores(tmp_path):
    import storage
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    storage.set_backtests(SQLiteBacktestResultStore(tmp_path=tmp_path))
    storage.reset()
    # Fresh factory call constructs new instance (not the one set above)
    import storage as s2
    assert isinstance(s2.backtests(), SQLiteBacktestResultStore)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_storage_factories_p2c.py -v`
Expected: 5 FAIL

- [ ] **Step 3: Extend `storage/__init__.py`**

1. Extend base imports to include `BacktestResultStore, LLMDecisionCacheStore`:

```python
from .base import (
    Agent, AgentStore, AuditStore, BacktestResultStore, CalendarStore,
    FinancialStore, KlineStore, LLMDecisionCacheStore, ModelInfo, ModelStore,
    Persona, PersonaStore, PromptVersion, PromptVersionStore, RedLineStore,
    StockStatusStore,
)
```

2. After existing globals, append:

```python
_backtests: BacktestResultStore | None = None
_llm_cache: LLMDecisionCacheStore | None = None
```

3. Add factory functions:

```python
def backtests() -> BacktestResultStore:
    global _backtests
    if _backtests is None:
        from .sqlite_backtests import SQLiteBacktestResultStore
        _backtests = SQLiteBacktestResultStore()
    return _backtests


def llm_cache() -> LLMDecisionCacheStore:
    global _llm_cache
    if _llm_cache is None:
        from .sqlite_llm_cache import SQLiteLLMDecisionCache
        _llm_cache = SQLiteLLMDecisionCache()
    return _llm_cache
```

4. Add setters:

```python
def set_backtests(impl: BacktestResultStore) -> None:
    global _backtests
    _backtests = impl


def set_llm_cache(impl: LLMDecisionCacheStore) -> None:
    global _llm_cache
    _llm_cache = impl
```

5. Update `reset()`:

```python
def reset() -> None:
    global _kline, _financial, _models, _calendar
    global _personas, _agents, _prompt_versions
    global _redline, _stock_status, _audit
    global _backtests, _llm_cache
    _kline = None
    _financial = None
    _models = None
    _calendar = None
    _personas = None
    _agents = None
    _prompt_versions = None
    _redline = None
    _stock_status = None
    _audit = None
    _backtests = None
    _llm_cache = None
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_storage_factories_p2c.py -v`
Expected: 5 PASSED

Full suite: `python -m pytest -q` — all green.

- [ ] **Step 5: Commit**

```bash
git add storage/__init__.py tests/test_storage_factories_p2c.py
git commit -m "feat(p2c): storage factories backtests() + llm_cache()"
```

---

## Task 7: Cross-cutoff zone classifier

**Files:**
- Create: `backtest/cutoff.py`
- Test: `tests/test_backtest_cutoff.py`

**Semantics:** given a model's training_cutoff (ISO date string) and a trading date,
return zone label `'pollution'` / `'buffer'` / `'clean'` where:
- `date < cutoff` → `'pollution'`
- `cutoff ≤ date < cutoff + 60 days` → `'buffer'`
- `date ≥ cutoff + 60 days` → `'clean'`

60-day buffer comes from `DEFAULT_QUALITY_GATE['min_clean_zone_days']` = 60.

- [ ] **Step 1: Write failing test**

```python
# tests/test_backtest_cutoff.py
"""Cross-cutoff zone classification."""
from datetime import date


def test_pollution_before_cutoff():
    from backtest.cutoff import classify_date
    assert classify_date(date(2024, 5, 1), cutoff='2024-06-01') == 'pollution'


def test_buffer_at_cutoff():
    from backtest.cutoff import classify_date
    assert classify_date(date(2024, 6, 1), cutoff='2024-06-01') == 'buffer'


def test_buffer_within_60_days():
    from backtest.cutoff import classify_date
    assert classify_date(date(2024, 7, 20), cutoff='2024-06-01') == 'buffer'


def test_clean_after_60_days():
    from backtest.cutoff import classify_date
    assert classify_date(date(2024, 8, 1), cutoff='2024-06-01') == 'clean'


def test_zone_windows_groups_days():
    from backtest.cutoff import zone_windows
    days = [date(2024, 5, 15), date(2024, 6, 1), date(2024, 7, 15),
            date(2024, 8, 10)]
    groups = zone_windows(days, cutoff='2024-06-01')
    assert groups['pollution'] == [date(2024, 5, 15)]
    assert groups['buffer'] == [date(2024, 6, 1), date(2024, 7, 15)]
    assert groups['clean'] == [date(2024, 8, 10)]


def test_zone_windows_all_one_zone():
    from backtest.cutoff import zone_windows
    groups = zone_windows([date(2024, 1, 1), date(2024, 2, 1)],
                          cutoff='2024-06-01')
    assert groups['pollution'] == [date(2024, 1, 1), date(2024, 2, 1)]
    assert groups['buffer'] == []
    assert groups['clean'] == []


def test_custom_buffer_days():
    from backtest.cutoff import classify_date
    assert classify_date(date(2024, 7, 1), cutoff='2024-06-01',
                         buffer_days=30) == 'clean'
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_backtest_cutoff.py -v`
Expected: 7 FAIL

- [ ] **Step 3: Implement**

```python
# backtest/cutoff.py
"""Cross-cutoff zone classification.

A model's training_cutoff splits backtest time into three zones:
  pollution — date < cutoff: model may have memorized outcomes
  buffer    — [cutoff, cutoff + buffer_days): partial leakage possible
  clean     — date >= cutoff + buffer_days: genuinely out-of-sample

Default buffer = 60 days (DEFAULT_QUALITY_GATE['min_clean_zone_days']).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta


_DEFAULT_BUFFER_DAYS = 60


def _parse_cutoff(cutoff: str | date) -> date:
    if isinstance(cutoff, date) and not isinstance(cutoff, datetime):
        return cutoff
    if isinstance(cutoff, datetime):
        return cutoff.date()
    return datetime.strptime(cutoff, '%Y-%m-%d').date()


def classify_date(d: date, cutoff: str | date,
                  buffer_days: int = _DEFAULT_BUFFER_DAYS) -> str:
    c = _parse_cutoff(cutoff)
    clean_start = c + timedelta(days=buffer_days)
    if d < c:
        return 'pollution'
    if d < clean_start:
        return 'buffer'
    return 'clean'


def zone_windows(days: list, cutoff: str | date,
                 buffer_days: int = _DEFAULT_BUFFER_DAYS) -> dict:
    out = {'pollution': [], 'buffer': [], 'clean': []}
    for d in days:
        out[classify_date(d, cutoff, buffer_days)].append(d)
    return out
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_backtest_cutoff.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add backtest/cutoff.py tests/test_backtest_cutoff.py
git commit -m "feat(p2c): cross-cutoff zone classifier (pollution/buffer/clean)"
```

---

## Task 8: Daily P&L → BacktestStats aggregator (with zones)

**Files:**
- Create: `backtest/stats.py`
- Test: `tests/test_backtest_stats.py`

**Input:** list of `{'date': date, 'pnl_pct': float, 'equity': float, 'trade_count': int, 'won': int}` daily records, cutoff. Output: overall `BacktestStats` + per-zone `ZoneStats` list.

- [ ] **Step 1: Write failing test**

```python
# tests/test_backtest_stats.py
"""Daily P&L list → BacktestStats + ZoneStats."""
from datetime import date


def _day(d, pnl=0.1, equity=100.0, trades=0, won=0):
    return {'date': d, 'pnl_pct': pnl, 'equity': equity,
            'trade_count': trades, 'won': won}


def test_empty_returns_zero_stats():
    from backtest.stats import aggregate
    stats, zones = aggregate([], cutoff='2024-06-01',
                             initial_capital=1_000_000.0)
    assert stats.trade_count == 0
    assert stats.final_equity == 1_000_000.0


def test_monotonic_positive_gives_positive_return():
    from backtest.stats import aggregate
    days = [_day(date(2024, 1, i), pnl=1.0, equity=100 + i)
            for i in range(1, 11)]
    stats, _ = aggregate(days, cutoff='2024-06-01',
                         initial_capital=100.0)
    assert stats.total_return_pct > 0
    assert stats.max_drawdown_pct <= 0
    assert stats.max_daily_loss_pct >= -1.0  # no single-day loss


def test_drawdown_computed():
    from backtest.stats import aggregate
    # equity: 100 → 110 → 90 → 95 (peak 110, trough 90, dd = (90-110)/110 = -18.18%)
    days = [
        _day(date(2024, 1, 1), pnl=10.0, equity=110),
        _day(date(2024, 1, 2), pnl=-18.18, equity=90),
        _day(date(2024, 1, 3), pnl=5.56, equity=95),
    ]
    stats, _ = aggregate(days, cutoff='2024-06-01', initial_capital=100.0)
    assert round(stats.max_drawdown_pct, 1) == -18.2


def test_win_rate():
    from backtest.stats import aggregate
    # 5 trades total, 3 won → 60%
    days = [
        _day(date(2024, 1, 1), trades=2, won=1),
        _day(date(2024, 1, 2), trades=3, won=2),
    ]
    stats, _ = aggregate(days, cutoff='2024-06-01',
                         initial_capital=100.0)
    assert stats.trade_count == 5
    assert round(stats.win_rate, 1) == 60.0


def test_zones_split_correctly():
    from backtest.stats import aggregate
    days = [
        _day(date(2024, 5, 15), pnl=1.0, equity=101),  # pollution
        _day(date(2024, 6, 15), pnl=0.5, equity=101.5),  # buffer
        _day(date(2024, 9, 1), pnl=0.5, equity=102),   # clean
    ]
    stats, zones = aggregate(days, cutoff='2024-06-01',
                             initial_capital=100.0)
    z_by_zone = {z.zone: z for z in zones}
    assert z_by_zone['pollution'].days == 1
    assert z_by_zone['buffer'].days == 1
    assert z_by_zone['clean'].days == 1


def test_single_day_zone_has_empty_stats():
    """A single day can't produce Sharpe — zone.stats should be {} when days<2."""
    from backtest.stats import aggregate
    days = [_day(date(2024, 9, 1), pnl=1.0, equity=101)]
    stats, zones = aggregate(days, cutoff='2024-06-01',
                             initial_capital=100.0)
    clean = [z for z in zones if z.zone == 'clean'][0]
    assert clean.stats == {}
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_backtest_stats.py -v`
Expected: 6 FAIL

- [ ] **Step 3: Implement**

```python
# backtest/stats.py
"""Daily record list → BacktestStats + per-zone ZoneStats."""
from __future__ import annotations

import math
from collections import defaultdict

from .base import BacktestStats, ZoneStats
from .cutoff import classify_date


def _sharpe(pnls: list[float]) -> float:
    if len(pnls) < 2:
        return 0.0
    mean = sum(pnls) / len(pnls)
    var = sum((x - mean) ** 2 for x in pnls) / (len(pnls) - 1)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    # Annualize assuming 252 trading days (daily PnL in %)
    return (mean / std) * math.sqrt(252)


def _max_drawdown_pct(equities: list[float]) -> float:
    if not equities:
        return 0.0
    peak = equities[0]
    max_dd = 0.0
    for e in equities:
        if e > peak:
            peak = e
        dd = (e - peak) / peak * 100.0 if peak else 0.0
        if dd < max_dd:
            max_dd = dd
    return max_dd


def _stats_from_days(days: list, initial_capital: float) -> BacktestStats:
    if not days:
        return BacktestStats(
            sharpe=0.0, max_drawdown_pct=0.0, trade_count=0,
            win_rate=0.0, max_daily_loss_pct=0.0,
            total_return_pct=0.0, final_equity=initial_capital,
        )
    pnls = [d['pnl_pct'] for d in days]
    equities = [d['equity'] for d in days]
    trade_count = sum(d.get('trade_count', 0) for d in days)
    won = sum(d.get('won', 0) for d in days)
    final_equity = equities[-1]
    total_return_pct = (final_equity - initial_capital) / initial_capital * 100.0

    return BacktestStats(
        sharpe=_sharpe(pnls),
        max_drawdown_pct=_max_drawdown_pct(equities),
        trade_count=trade_count,
        win_rate=(won / trade_count * 100.0) if trade_count else 0.0,
        max_daily_loss_pct=min(pnls) if pnls else 0.0,
        total_return_pct=total_return_pct,
        final_equity=final_equity,
    )


def aggregate(days: list, cutoff: str, initial_capital: float):
    """Return (overall_stats, [ZoneStats, ...])."""
    overall = _stats_from_days(days, initial_capital)

    by_zone = defaultdict(list)
    for d in days:
        zone = classify_date(d['date'], cutoff)
        by_zone[zone].append(d)

    zones = []
    for name in ('pollution', 'buffer', 'clean'):
        zd = by_zone.get(name, [])
        if len(zd) < 2:
            zones.append(ZoneStats(zone=name, days=len(zd), stats={}))
            continue
        zone_stats = _stats_from_days(zd, initial_capital)
        zones.append(ZoneStats(
            zone=name, days=len(zd),
            stats={
                'sharpe': zone_stats.sharpe,
                'max_drawdown_pct': zone_stats.max_drawdown_pct,
                'trade_count': zone_stats.trade_count,
                'win_rate': zone_stats.win_rate,
                'max_daily_loss_pct': zone_stats.max_daily_loss_pct,
                'total_return_pct': zone_stats.total_return_pct,
                'final_equity': zone_stats.final_equity,
            },
        ))
    return overall, zones
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_backtest_stats.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add backtest/stats.py tests/test_backtest_stats.py
git commit -m "feat(p2c): backtest stats aggregator with per-zone breakdown"
```

---

## Task 9: 100-share lot rounding (P2b leftover)

**Files:**
- Modify: `validation/handlers/position_max_pct.py`
- Test: `tests/test_handler_position_max_pct.py` (append one test)

**Why:** A-share brokers reject buy orders not in multiples of 100. When
`position_max_pct` handler auto-shrinks shares, it must round down to the
nearest 100. If resulting shares < 100, switch to reject (can't buy fewer
than 100 shares of A-shares).

- [ ] **Step 1: Append failing tests**

```python
def test_shrink_rounds_down_to_lot_100():
    """Auto-shrink must produce a multiple of 100."""
    from validation.handlers.position_max_pct import Handler
    from validation.base import ValidationRequest
    # 1M equity * 15% cap = 150k. price=237 → allowed_additional = 632 (before rounding)
    # After lot rounding → 600 shares
    req = ValidationRequest(
        agent_id='a1',
        decision={'action': 'buy', 'code': 'X.SH', 'shares': 1000,
                  'price': 237.0},
        portfolio={'equity': 1_000_000.0, 'positions': {}},
        market_context={},
        rules={'position_max_pct': 15.0},
    )
    v = Handler().check(req)
    assert v is not None
    assert v.severity == 'modify'
    assert v.modification == {'shares': 600}


def test_shrink_below_one_lot_rejects():
    """If the allowed quantity would be < 100, reject instead."""
    from validation.handlers.position_max_pct import Handler
    from validation.base import ValidationRequest
    # 100k equity * 0.05% cap = 50. price=1000 → allowed_additional = 0
    req = ValidationRequest(
        agent_id='a1',
        decision={'action': 'buy', 'code': 'X.SH', 'shares': 100,
                  'price': 1000.0},
        portfolio={'equity': 100_000.0, 'positions': {}},
        market_context={},
        rules={'position_max_pct': 0.05},
    )
    v = Handler().check(req)
    assert v is not None
    assert v.severity == 'reject'
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_handler_position_max_pct.py -v`
Expected: 2 new fails

- [ ] **Step 3: Modify `validation/handlers/position_max_pct.py`**

Find the modify-branch (where `allowed_additional = int(math.floor(...))` is computed) and replace with:

```python
        allowed_additional = int(math.floor((max_value - held_value) / price))
        # A-share lot: must be multiple of 100
        allowed_additional = (allowed_additional // 100) * 100
        if allowed_additional < 100:
            return Violation(
                rule_id=RULE_ID, severity='reject',
                reason=(f'cap allows only {allowed_additional} shares; '
                        f'below A-share minimum lot of 100'),
            )
        if allowed_additional < shares_req:
            return Violation(
                rule_id=RULE_ID, severity='modify',
                reason=(f'post-trade value > cap {max_value:.0f}; '
                        f'shrink to {allowed_additional} shares '
                        f'(rounded to lot of 100)'),
                modification={'shares': allowed_additional},
            )
        return None
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_handler_position_max_pct.py -v`
Expected: all PASSED including the 2 new tests

- [ ] **Step 5: Commit**

```bash
git add validation/handlers/position_max_pct.py tests/test_handler_position_max_pct.py
git commit -m "fix(p2c): position_max_pct rounds auto-shrink to A-share lot (100)"
```

---

## Task 10: Portfolio adapter

**Files:**
- Create: `backtest/portfolio_adapter.py`
- Test: `tests/test_portfolio_adapter.py`

**Responsibility:** Given a lightweight "engine state" dict (holding cash + positions keyed by code → shares + avg_price) plus current market prices, build the `portfolio` dict shape expected by `ValidationEngine`.

This decouples from vnpy specifics — real integration with `vnpy_portfoliostrategy` happens in Task 12 via calling this adapter.

- [ ] **Step 1: Write failing test**

```python
# tests/test_portfolio_adapter.py
"""vnpy-independent portfolio dict builder for the validation engine."""


def test_empty_positions_equity_equals_cash():
    from backtest.portfolio_adapter import build_portfolio
    p = build_portfolio(cash=1_000_000.0, positions={}, mark_prices={})
    assert p['equity'] == 1_000_000.0
    assert p['cash'] == 1_000_000.0
    assert p['positions'] == {}


def test_equity_includes_position_mark_to_market():
    from backtest.portfolio_adapter import build_portfolio
    # 500 shares at mark 200 = 100k; cash 900k → equity 1M
    p = build_portfolio(
        cash=900_000.0,
        positions={'X.SH': {'shares': 500, 'avg_price': 180.0}},
        mark_prices={'X.SH': 200.0},
    )
    assert p['cash'] == 900_000.0
    assert p['equity'] == 1_000_000.0
    assert p['positions']['X.SH']['shares'] == 500
    assert p['positions']['X.SH']['avg_price'] == 180.0


def test_missing_mark_price_falls_back_to_avg():
    """If we have no bar today, use avg_price as a stale-safe approximation."""
    from backtest.portfolio_adapter import build_portfolio
    p = build_portfolio(
        cash=100_000.0,
        positions={'X.SH': {'shares': 100, 'avg_price': 10.0}},
        mark_prices={},
    )
    assert p['equity'] == 100_000.0 + 100 * 10.0


def test_zero_share_position_is_excluded():
    from backtest.portfolio_adapter import build_portfolio
    p = build_portfolio(
        cash=100_000.0,
        positions={'X.SH': {'shares': 0, 'avg_price': 10.0},
                   'Y.SZ': {'shares': 100, 'avg_price': 20.0}},
        mark_prices={'Y.SZ': 22.0},
    )
    assert 'X.SH' not in p['positions']
    assert p['positions']['Y.SZ']['shares'] == 100
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_portfolio_adapter.py -v`
Expected: 4 FAIL

- [ ] **Step 3: Implement**

```python
# backtest/portfolio_adapter.py
"""Build the ValidationEngine portfolio dict from engine state + mark prices."""
from __future__ import annotations


def build_portfolio(cash: float, positions: dict,
                    mark_prices: dict) -> dict:
    """Return {equity, cash, positions} suitable for ValidationEngine."""
    clean_positions: dict[str, dict] = {}
    equity = float(cash)
    for code, info in (positions or {}).items():
        shares = int(info.get('shares', 0) or 0)
        if shares <= 0:
            continue
        avg_price = float(info.get('avg_price', 0.0))
        mark = float(mark_prices.get(code, avg_price))
        equity += shares * mark
        clean_positions[code] = {
            'shares': shares,
            'avg_price': avg_price,
        }
    return {
        'cash': float(cash),
        'equity': equity,
        'positions': clean_positions,
    }
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_portfolio_adapter.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add backtest/portfolio_adapter.py tests/test_portfolio_adapter.py
git commit -m "feat(p2c): portfolio adapter for ValidationEngine"
```

---

## Task 11: Prompt builder

**Files:**
- Create: `agents/__init__.py`, `agents/prompt_builder.py`
- Test: `tests/test_prompt_builder.py`

**Responsibility:** Given agent metadata, current date, portfolio snapshot, and market context, build the list of Messages to send to LLM. The system prompt comes from the agent's current PromptVersion.

- [ ] **Step 1: Write failing test**

```python
# tests/test_prompt_builder.py
"""Prompt builder for agent LLM calls."""


def test_system_prompt_from_version():
    from agents.prompt_builder import build_messages
    msgs = build_messages(
        system_prompt='你是一位价值投资者。',
        date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000,
                   'positions': {}},
        market_context={},
        default_pool=['600519.SH'],
    )
    assert msgs[0].role == 'system'
    assert msgs[0].content == '你是一位价值投资者。'


def test_user_message_contains_date_and_pool():
    from agents.prompt_builder import build_messages
    msgs = build_messages(
        system_prompt='X',
        date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={},
        default_pool=['600519.SH', '000858.SZ'],
    )
    user = msgs[1].content
    assert '2024-03-15' in user
    assert '600519.SH' in user
    assert '000858.SZ' in user


def test_user_message_shows_positions():
    from agents.prompt_builder import build_messages
    msgs = build_messages(
        system_prompt='X', date='2024-03-15',
        portfolio={'cash': 500_000, 'equity': 1_000_000,
                   'positions': {'600519.SH': {'shares': 300,
                                               'avg_price': 1600.0}}},
        market_context={},
        default_pool=['600519.SH'],
    )
    user = msgs[1].content
    assert '600519.SH' in user
    assert '300' in user


def test_prompt_hash_stable_for_same_inputs():
    from agents.prompt_builder import build_messages, prompt_hash
    args = dict(
        system_prompt='X', date='2024-03-15',
        portfolio={'cash': 1, 'equity': 1, 'positions': {}},
        market_context={}, default_pool=['X.SH'],
    )
    h1 = prompt_hash(build_messages(**args))
    h2 = prompt_hash(build_messages(**args))
    assert h1 == h2


def test_prompt_hash_differs_for_different_dates():
    from agents.prompt_builder import build_messages, prompt_hash
    base = dict(
        system_prompt='X',
        portfolio={'cash': 1, 'equity': 1, 'positions': {}},
        market_context={}, default_pool=['X.SH'],
    )
    h1 = prompt_hash(build_messages(date='2024-03-15', **base))
    h2 = prompt_hash(build_messages(date='2024-03-16', **base))
    assert h1 != h2
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_prompt_builder.py -v`
Expected: 5 FAIL

- [ ] **Step 3: Implement**

```python
# agents/__init__.py
"""Agent execution — prompt assembly + tool loop runner (P2c)."""
```

```python
# agents/prompt_builder.py
"""Assemble LLM messages for an agent decision point + hash utility."""
from __future__ import annotations

import hashlib
import json

from llm.base import Message


def build_messages(
    *,
    system_prompt: str,
    date: str,
    portfolio: dict,
    market_context: dict,
    default_pool: list[str],
) -> list[Message]:
    """Return [system Message, user Message]."""
    cash = portfolio.get('cash', 0)
    equity = portfolio.get('equity', 0)
    positions = portfolio.get('positions', {})

    lines = [f'决策日期：{date}']
    lines.append(f'组合：现金 {cash:.0f}，总资产 {equity:.0f}')
    if positions:
        lines.append('当前持仓：')
        for code, info in positions.items():
            lines.append(
                f'  - {code} × {info.get("shares", 0)} 股（均价 '
                f'{info.get("avg_price", 0):.2f}）'
            )
    else:
        lines.append('当前无持仓。')
    lines.append(f'备选池：{", ".join(default_pool)}')
    if market_context:
        lines.append('市场快照：')
        for k, v in market_context.items():
            lines.append(f'  - {k}: {v}')
    lines.append('')
    lines.append(
        '使用工具调研后调用 place_decision 给出当日决策（'
        'buy / sell / hold 三选一，含理由与完整思考）。'
    )
    user_msg = '\n'.join(lines)
    return [
        Message(role='system', content=system_prompt),
        Message(role='user', content=user_msg),
    ]


def prompt_hash(messages: list[Message]) -> str:
    payload = json.dumps(
        [{'role': m.role, 'content': m.content} for m in messages],
        ensure_ascii=False, sort_keys=True,
    ).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()[:16]
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_prompt_builder.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add agents/ tests/test_prompt_builder.py
git commit -m "feat(p2c): prompt builder + stable prompt_hash for cache keying"
```

---

## Task 12: AgentRunner — tool loop + cache + validation

**Files:**
- Create: `agents/runner.py`
- Test: `tests/test_agent_runner.py`

**Responsibility:** Given an `agent_id` + `date` + `portfolio` + `market_context`, run the LLM tool loop:
1. Build cache_key from (agent_id, date, portfolio_hash, prompt_hash)
2. If cached → return cached decisions
3. Else: call LLM → iterate tool_use (non-terminator tools: execute via `tools/`) → on `place_decision`: call `ValidationEngine.validate(...)` → collect outcome → loop until all tool calls processed or max_iterations
4. Cache final decision list → return

`portfolio_hash` = stable hash of `{cash, equity, positions_sorted}`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_agent_runner.py
"""AgentRunner tool loop + cache + validation integration."""
import pytest


@pytest.fixture
def wired(tmp_path):
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.sqlite_audit import SQLiteAuditStore
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    from storage.sqlite_personas import SQLitePersonaStore
    from storage.sqlite_agents import SQLiteAgentStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    from storage.sqlite_models import SQLiteModelStore
    from validation.base import DEFAULT_REDLINES

    for store_cls, setter in [
        (SQLiteRedLineStore, 'set_redline'),
        (SQLiteStockStatusStore, 'set_stock_status'),
        (SQLiteAuditStore, 'set_audit'),
        (SQLiteLLMDecisionCache, 'set_llm_cache'),
        (SQLitePersonaStore, 'set_personas'),
        (SQLiteAgentStore, 'set_agents'),
        (SQLitePromptVersionStore, 'set_prompt_versions'),
        (SQLiteModelStore, 'set_models'),
    ]:
        inst = store_cls(tmp_path=tmp_path)
        inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()

    from validation import rules
    rules.reset()
    import validation.handlers  # noqa: F401

    storage.redline().set({**DEFAULT_REDLINES, 'position_max_pct': 15.0})
    return storage


@pytest.fixture
def seeded_agent(wired):
    from personas import seed as seed_personas
    seed_personas()
    agent = wired.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='TestAgent',
    )
    return agent


def _mock_llm_with_decision(code='600519.SH', shares=100, price=1600.0):
    from llm.mock import MockLLM
    return MockLLM([{
        'tool_calls': [{
            'id': 'call_1', 'name': 'place_decision',
            'input': {
                'action': 'buy', 'code': code, 'qty': shares,
                'reason': 'fundamentals strong, valuation reasonable today',
                'thinking': 'analysis details',
            },
        }],
        'stop_reason': 'tool_use',
    }])


def test_first_run_calls_llm_and_caches(wired, seeded_agent):
    from agents.runner import AgentRunner
    from llm.base import Message  # noqa: F401
    llm = _mock_llm_with_decision()
    runner = AgentRunner(llm=llm)
    out = runner.run_day(
        agent_id=seeded_agent.id,
        date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={},
        mark_prices={'600519.SH': 1600.0},
    )
    assert len(llm.calls) == 1
    assert len(out) == 1
    assert out[0]['action'] == 'buy'
    assert out[0]['code'] == '600519.SH'


def test_rerun_uses_cache_no_new_llm_call(wired, seeded_agent):
    from agents.runner import AgentRunner
    llm = _mock_llm_with_decision()
    runner = AgentRunner(llm=llm)
    common_args = dict(
        agent_id=seeded_agent.id, date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 1600.0},
    )
    runner.run_day(**common_args)
    assert len(llm.calls) == 1
    runner.run_day(**common_args)
    assert len(llm.calls) == 1  # no new call, cache hit


def test_rejected_decision_is_not_in_output(wired, seeded_agent):
    """ValidationEngine rejects; runner returns empty list + audit row exists."""
    from storage.base import StockStatusRow
    import storage
    from agents.runner import AgentRunner
    storage.stock_status().upsert(StockStatusRow(
        code='ST.SH', name='*ST X', is_st=True,
        is_suspended=False, is_delisted=False,
    ))
    llm = _mock_llm_with_decision(code='ST.SH', shares=100, price=10.0)
    runner = AgentRunner(llm=llm)
    out = runner.run_day(
        agent_id=seeded_agent.id, date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'ST.SH': 10.0},
    )
    assert out == []
    rows = storage.audit().query_by_agent(seeded_agent.id)
    assert len(rows) >= 1
    assert rows[0]['details']['outcome'] == 'rejected'


def test_modified_decision_reflects_shrunk_shares(wired, seeded_agent):
    """Buy 1000 shares that exceeds 15% cap → shrunk to 600 (rounded to lot)."""
    from agents.runner import AgentRunner
    # 1000 shares × 237 = 237k > 150k cap → shrink to 632 → lot-round to 600
    llm = _mock_llm_with_decision(code='600519.SH', shares=1000, price=237.0)
    runner = AgentRunner(llm=llm)
    out = runner.run_day(
        agent_id=seeded_agent.id, date='2024-03-15',
        portfolio={'cash': 1_000_000, 'equity': 1_000_000, 'positions': {}},
        market_context={}, mark_prices={'600519.SH': 237.0},
    )
    assert len(out) == 1
    assert out[0]['shares'] == 600
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_agent_runner.py -v`
Expected: 4 FAIL

- [ ] **Step 3: Implement**

```python
# agents/runner.py
"""AgentRunner — daily LLM decision loop with cache + validation."""
from __future__ import annotations

import hashlib
import json

from backtest.base import CachedDecision
from llm.base import Message
from validation.engine import ValidationEngine

from .prompt_builder import build_messages, prompt_hash


_MAX_TOOL_ITERATIONS = 8


def _portfolio_hash(portfolio: dict) -> str:
    """Stable hash of portfolio state for cache keying."""
    positions = portfolio.get('positions', {})
    sorted_positions = sorted(
        (code, info.get('shares', 0), info.get('avg_price', 0))
        for code, info in positions.items()
    )
    payload = json.dumps({
        'cash': round(portfolio.get('cash', 0), 2),
        'equity': round(portfolio.get('equity', 0), 2),
        'positions': sorted_positions,
    }, sort_keys=True).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()[:16]


class AgentRunner:
    def __init__(self, llm, engine: ValidationEngine | None = None,
                 max_iterations: int = _MAX_TOOL_ITERATIONS):
        self._llm = llm
        self._engine = engine or ValidationEngine()
        self._max_iterations = max_iterations

    def run_day(
        self,
        *,
        agent_id: str,
        date: str,
        portfolio: dict,
        market_context: dict,
        mark_prices: dict,
    ) -> list[dict]:
        """Return list of executed (validated/modified) decisions."""
        import storage

        agent = storage.agents().get(agent_id)
        if agent is None:
            raise ValueError(f'unknown agent_id={agent_id}')
        persona = storage.personas().get(agent.persona_id)
        pv = storage.prompt_versions().get_latest(agent_id)
        if pv is None:
            raise RuntimeError(f'agent {agent_id} has no prompt version')
        system_prompt = pv.system_prompt

        messages = build_messages(
            system_prompt=system_prompt,
            date=date,
            portfolio=portfolio,
            market_context=market_context,
            default_pool=persona.default_pool if persona else [],
        )
        p_hash = prompt_hash(messages)
        port_hash = _portfolio_hash(portfolio)
        cache_key = CachedDecision.build_key(agent_id, date, port_hash, p_hash)

        cache = storage.llm_cache()
        cached = cache.get(cache_key)
        if cached is not None:
            return list(cached.decisions)

        # Live LLM tool loop
        from tools import filter_allowed
        allowed = filter_allowed(persona.allowed_tools if persona else [])
        # filter_allowed returns dict[name, (SPEC, call)]; extract specs for LLM
        tool_specs = [spec for spec, _ in allowed.values()]

        decisions_executed: list[dict] = []
        convo = list(messages)

        for _ in range(self._max_iterations):
            resp = self._llm.chat(messages=convo, tools=tool_specs)
            if not resp.tool_calls:
                break

            # Append assistant turn so next LLM call sees its own prior output
            # (MockLLM ignores this, but real providers require it.)
            convo.extend(resp.messages)

            tool_results: list[Message] = []
            terminated = False
            for call in resp.tool_calls:
                if call.name == 'place_decision':
                    decision = dict(call.input)
                    # Normalize shape for ValidationEngine
                    decision.setdefault('shares', decision.get('qty', 0))
                    decision.setdefault('price',
                                        mark_prices.get(decision.get('code'),
                                                        0.0))
                    result = self._engine.validate(
                        agent_id=agent_id,
                        decision=decision,
                        portfolio=portfolio,
                        market_context=market_context,
                        persona_id=agent.persona_id,
                        model_id=agent.model_id,
                    )
                    if result.outcome != 'rejected' and result.decision_out:
                        decisions_executed.append(result.decision_out)
                    terminated = True
                    break
                # Non-terminator tool: just acknowledge (P1 tools return data;
                # MVP runner keeps loop simple — skip real tool exec in backtest)
                tool_results.append(Message(
                    role='tool', content=json.dumps({'ack': True}),
                    tool_call_id=call.id,
                ))
            if terminated:
                break
            convo.extend(tool_results)

        cache.put(CachedDecision(
            agent_id=agent_id, date=date,
            portfolio_hash=port_hash, prompt_hash=p_hash,
            decisions=decisions_executed,
        ))
        return decisions_executed
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_agent_runner.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add agents/runner.py tests/test_agent_runner.py
git commit -m "feat(p2c): AgentRunner — cache-first LLM tool loop + ValidationEngine"
```

---

## Task 13: LLMPortfolioStrategy (vnpy subclass)

**Files:**
- Create: `backtest/strategy.py`
- Test: `tests/test_backtest_strategy.py`

**Responsibility:** Subclass `vnpy_portfoliostrategy.StrategyTemplate`. On each bar batch (`on_bars`), delegate to `AgentRunner` and translate its decisions into vnpy orders.

**Note:** vnpy strategies run inside an engine. For unit testing we isolate the `_process_bars` method and test that it emits the correct orders given mocked `AgentRunner`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_backtest_strategy.py
"""LLMPortfolioStrategy bar→decision→order translation."""
from datetime import datetime


class _StubBar:
    def __init__(self, symbol, close, exchange='SSE',
                 dt=datetime(2024, 3, 15)):
        self.symbol = symbol
        self.close_price = close
        self.datetime = dt
        class _Exch:
            value = exchange
        self.exchange = _Exch()


def test_process_bars_calls_runner_with_mark_prices():
    from backtest.strategy import LLMPortfolioStrategy

    class FakeRunner:
        def __init__(self):
            self.calls = []

        def run_day(self, **kwargs):
            self.calls.append(kwargs)
            return []

    runner = FakeRunner()
    s = LLMPortfolioStrategy.__new__(LLMPortfolioStrategy)
    s._runner = runner
    s._agent_id = 'a1'
    s._cash = 1_000_000.0
    s._positions = {}
    s.vt_symbols = ['600519.SSE']

    bars = {'600519.SSE': _StubBar('600519', 1600.0)}
    decisions = s._process_bars(bars)
    assert decisions == []
    assert len(runner.calls) == 1
    call = runner.calls[0]
    assert call['date'] == '2024-03-15'
    assert call['mark_prices']['600519.SH'] == 1600.0


def test_process_bars_converts_decisions_to_orders():
    from backtest.strategy import LLMPortfolioStrategy

    class FakeRunner:
        def run_day(self, **kwargs):
            return [{'action': 'buy', 'code': '600519.SH',
                     'shares': 100, 'price': 1600.0,
                     'reason': 'solid fundamentals and good value',
                     'thinking': 'analysis'}]

    s = LLMPortfolioStrategy.__new__(LLMPortfolioStrategy)
    s._runner = FakeRunner()
    s._agent_id = 'a1'
    s._cash = 1_000_000.0
    s._positions = {}
    s.vt_symbols = ['600519.SSE']

    bars = {'600519.SSE': _StubBar('600519', 1600.0)}
    decisions = s._process_bars(bars)
    assert len(decisions) == 1
    assert decisions[0]['action'] == 'buy'


def test_vt_to_biyingtong_code_mapping():
    from backtest.strategy import vt_to_biyingtong
    assert vt_to_biyingtong('600519', 'SSE') == '600519.SH'
    assert vt_to_biyingtong('000858', 'SZSE') == '000858.SZ'
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_backtest_strategy.py -v`
Expected: 3 FAIL

- [ ] **Step 3: Implement**

```python
# backtest/strategy.py
"""LLMPortfolioStrategy — vnpy_portfoliostrategy subclass driven by AgentRunner.

The integration with vnpy's engine (order submission, position tracking) is
delegated to the parent StrategyTemplate; this class only bridges bars →
AgentRunner → decisions → vnpy orders.
"""
from __future__ import annotations


_EXCHANGE_TO_BIYINGTONG = {
    'SSE': 'SH',
    'SZSE': 'SZ',
}


def vt_to_biyingtong(symbol: str, exchange: str) -> str:
    """'600519' + 'SSE' → '600519.SH'."""
    suffix = _EXCHANGE_TO_BIYINGTONG.get(exchange, exchange)
    return f'{symbol}.{suffix}'


try:
    from vnpy_portfoliostrategy import StrategyTemplate as _BaseStrategy
except Exception:  # vnpy not importable in isolated test contexts
    class _BaseStrategy:  # type: ignore
        pass


class LLMPortfolioStrategy(_BaseStrategy):
    """vnpy_portfoliostrategy template driven by AgentRunner."""

    # These are typed as class attributes so vnpy sees them in setting_map;
    # set_params can overwrite.
    agent_id: str = ''

    def __init__(self, strategy_engine, strategy_name, vt_symbols, setting):
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        from agents.runner import AgentRunner
        self._runner = AgentRunner(llm=setting.get('llm'))
        self._agent_id = setting.get('agent_id') or self.agent_id
        self._cash = float(setting.get('initial_capital', 1_000_000.0))
        self._positions: dict = {}
        # Returned by backtest runner to inspect per-day decisions.
        self.daily_decisions: list[tuple] = []

    def on_init(self):
        pass

    def on_start(self):
        pass

    def on_bars(self, bars: dict):  # vnpy hook
        day_decisions = self._process_bars(bars)
        self.daily_decisions.append((self._extract_date(bars), day_decisions))
        # Translating decisions into vnpy orders is done by the backtest runner
        # after on_bars returns; this class tracks them for inspection.

    def _extract_date(self, bars: dict) -> str:
        for bar in bars.values():
            return bar.datetime.strftime('%Y-%m-%d')
        return ''

    def _process_bars(self, bars: dict) -> list[dict]:
        date = self._extract_date(bars)
        mark_prices = {}
        for vt_symbol, bar in bars.items():
            # vt_symbol like '600519.SSE'
            symbol, _, exchange = vt_symbol.partition('.')
            # Sometimes vnpy bar.symbol is the code, exchange is an Enum-like
            exch_val = getattr(bar.exchange, 'value', exchange)
            code = vt_to_biyingtong(bar.symbol, exch_val)
            mark_prices[code] = float(bar.close_price)

        from backtest.portfolio_adapter import build_portfolio
        portfolio = build_portfolio(
            cash=self._cash, positions=self._positions,
            mark_prices=mark_prices,
        )
        return self._runner.run_day(
            agent_id=self._agent_id,
            date=date,
            portfolio=portfolio,
            market_context={},
            mark_prices=mark_prices,
        )
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_backtest_strategy.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add backtest/strategy.py tests/test_backtest_strategy.py
git commit -m "feat(p2c): LLMPortfolioStrategy — vnpy bridge driven by AgentRunner"
```

---

## Task 14: BacktestRunner orchestrator

**Files:**
- Create: `backtest/runner.py`
- Test: `tests/test_backtest_runner.py`

**Responsibility:** Given (session_id, agent_id, start_date, end_date), iterate trading days from `storage.calendar()`, pull bars from `storage.kline()`, step the strategy per day, apply decisions to a simple in-process book (buy/sell against cash+positions), collect daily P&L, aggregate → stats → evaluate_quality_gate → persist BacktestResult.

**MVP simplification:** Skip vnpy's BarManager — use a plain Python loop over daily bars. The strategy class from T13 is used for its bar→decision adaptor; order execution is done by the runner at the next day's open price (or current close for simplicity).

- [ ] **Step 1: Write failing test**

```python
# tests/test_backtest_runner.py
"""BacktestRunner E2E driver."""
from datetime import date, timedelta
import pytest


@pytest.fixture
def wired_full(tmp_path):
    """Bring up every store P2c needs, seed personas + models."""
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
        (SQLiteCalendarStore,       'set_calendar'),
    ]:
        inst = cls(tmp_path=tmp_path)
        inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()

    from validation import rules
    rules.reset()
    import validation.handlers  # noqa

    storage.redline().set({**DEFAULT_REDLINES, 'position_max_pct': 15.0})
    from personas import seed as seed_personas
    seed_personas()
    return storage


def _fake_bar_series(code='600519.SH', days=10, start_price=1600.0):
    """Daily close sequence mildly up-trending, returns list of (date, close)."""
    return [(date(2024, 3, 1) + timedelta(days=i),
             start_price * (1 + 0.002 * i))
            for i in range(days)]


def test_run_produces_backtest_result(wired_full, monkeypatch):
    """Smoke: runner completes and writes one BacktestResult row."""
    from backtest.runner import BacktestRunner

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='Test',
    )

    # Stub the bar fetcher + calendar
    import backtest.runner as mod
    bars = _fake_bar_series()
    monkeypatch.setattr(mod, '_load_daily_closes',
                        lambda code, start, end: bars)
    monkeypatch.setattr(mod, '_trading_days',
                        lambda start, end: [d for d, _ in bars])

    from llm.mock import MockLLM
    llm = MockLLM([{
        'tool_calls': [{
            'id': 'c1', 'name': 'place_decision',
            'input': {'action': 'hold',
                      'reason': 'staying put, nothing compelling today',
                      'thinking': 'analysis'},
        }], 'stop_reason': 'tool_use',
    }] * 10)

    runner = BacktestRunner(llm=llm)
    result = runner.run(
        session_id='s1', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-10',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )
    assert result.id is not None
    assert result.session_id == 's1'
    assert result.quality_gate_label in ('pass', 'warn', 'fail')
    stored = wired_full.backtests().get(result.id)
    assert stored is not None


def test_buy_decision_reduces_cash(wired_full, monkeypatch):
    """A buy that passes validation must spend cash."""
    from backtest.runner import BacktestRunner

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='Test',
    )

    import backtest.runner as mod
    bars = _fake_bar_series(days=3)
    monkeypatch.setattr(mod, '_load_daily_closes',
                        lambda c, s, e: bars)
    monkeypatch.setattr(mod, '_trading_days',
                        lambda s, e: [d for d, _ in bars])

    from llm.mock import MockLLM
    # Day 1: buy 100 @ ~1600 = ~160k (10% of 1M, under 15% cap)
    # Day 2+: hold
    llm = MockLLM([
        {'tool_calls': [{'id': 'c1', 'name': 'place_decision',
                         'input': {'action': 'buy', 'code': '600519.SH',
                                   'qty': 100,
                                   'reason': 'buying quality at reasonable valuation',
                                   'thinking': 't'}}],
         'stop_reason': 'tool_use'},
        {'tool_calls': [{'id': 'c2', 'name': 'place_decision',
                         'input': {'action': 'hold',
                                   'reason': 'holding position, waiting for further confirmation',
                                   'thinking': 't'}}],
         'stop_reason': 'tool_use'},
        {'tool_calls': [{'id': 'c3', 'name': 'place_decision',
                         'input': {'action': 'hold',
                                   'reason': 'holding, thesis still intact',
                                   'thinking': 't'}}],
         'stop_reason': 'tool_use'},
    ])

    runner = BacktestRunner(llm=llm)
    result = runner.run(
        session_id='s2', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-03',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )
    # Equity should be roughly 1M (slightly up due to 0.2%/day price trend
    # applied to held shares). Confirm it's not exactly initial.
    assert result.final_equity is not None
    assert result.final_equity != 1_000_000.0
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_backtest_runner.py -v`
Expected: 2 FAIL

- [ ] **Step 3: Implement**

```python
# backtest/runner.py
"""BacktestRunner — orchestrates agent decisions over a date range."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from agents.runner import AgentRunner
from validation.quality_gate import evaluate_quality_gate

from .base import BacktestResult
from .portfolio_adapter import build_portfolio
from .stats import aggregate


def _load_daily_closes(code: str, start: date, end: date) -> list:
    """Returns [(date, close), ...] ascending for one stock."""
    import storage
    from datetime import datetime as _dt
    bars = storage.kline().load_range(
        code, '1d',
        _dt(start.year, start.month, start.day),
        _dt(end.year, end.month, end.day),
    )
    # vnpy BarData: bar.datetime is datetime, bar.close_price is float
    return [(b.datetime.date(), float(b.close_price)) for b in bars]


def _trading_days(start: str, end: str) -> list:
    import storage
    return storage.calendar().get_trading_days(
        _parse(start), _parse(end),
    )


def _parse(s: str) -> date:
    return datetime.strptime(s, '%Y-%m-%d').date()


class BacktestRunner:
    def __init__(self, llm, initial_capital: float = 1_000_000.0):
        self._llm = llm
        self._default_capital = initial_capital

    def run(self, *, session_id: str, agent_id: str,
            start_date: str, end_date: str,
            initial_capital: float | None = None,
            universe: list[str],
            notes: str | None = None) -> BacktestResult:
        import storage

        cap = float(initial_capital or self._default_capital)
        storage.backtests().create_session(
            session_id, start_date, end_date, [agent_id], notes=notes,
        )

        # Load price series per symbol once; use forward-fill for missing days
        start = _parse(start_date)
        end = _parse(end_date)
        price_series: dict[str, dict] = {}
        for code in universe:
            price_series[code] = dict(_load_daily_closes(code, start, end))

        days = _trading_days(start_date, end_date)
        agent = storage.agents().get(agent_id)
        persona_id = agent.persona_id if agent else None
        model_id = agent.model_id if agent else None

        runner = AgentRunner(llm=self._llm)
        cash = cap
        positions: dict[str, dict] = {}
        daily_records: list[dict] = []
        prev_equity = cap

        for d in days:
            mark_prices = {code: price_series[code].get(d) for code in universe
                           if price_series[code].get(d) is not None}
            # Fallback: use last seen close if today missing
            for code in universe:
                if code not in mark_prices:
                    past = [p for dt, p in price_series[code].items() if dt <= d]
                    if past:
                        mark_prices[code] = past[-1]
            if not mark_prices:
                continue  # no data for this trading day, skip

            portfolio = build_portfolio(
                cash=cash, positions=positions, mark_prices=mark_prices,
            )
            decisions = runner.run_day(
                agent_id=agent_id, date=d.strftime('%Y-%m-%d'),
                portfolio=portfolio, market_context={},
                mark_prices=mark_prices,
            )

            # Apply decisions to the book at today's close (simplest fill model)
            trade_count_today = 0
            wins_today = 0
            for dec in decisions:
                action = dec.get('action')
                code = dec.get('code')
                shares = int(dec.get('shares') or dec.get('qty') or 0)
                px = mark_prices.get(code, float(dec.get('price', 0.0)))
                if action == 'buy' and shares > 0 and px > 0 and cash >= shares * px:
                    cost = shares * px
                    pos = positions.setdefault(
                        code, {'shares': 0, 'avg_price': 0.0})
                    prev_shares = pos['shares']
                    new_shares = prev_shares + shares
                    pos['avg_price'] = (
                        (pos['avg_price'] * prev_shares + cost) / new_shares
                        if new_shares else 0.0
                    )
                    pos['shares'] = new_shares
                    cash -= cost
                    trade_count_today += 1
                elif action == 'sell' and shares > 0 and code in positions:
                    pos = positions[code]
                    sell_n = min(shares, pos['shares'])
                    if sell_n > 0:
                        proceeds = sell_n * px
                        cash += proceeds
                        win = px > pos['avg_price']
                        pos['shares'] -= sell_n
                        trade_count_today += 1
                        if win:
                            wins_today += 1

            # Mark-to-market equity
            equity = cash + sum(pos['shares'] * mark_prices.get(code, pos['avg_price'])
                                for code, pos in positions.items()
                                if pos['shares'] > 0)
            pnl_pct = ((equity - prev_equity) / prev_equity * 100.0
                       if prev_equity > 0 else 0.0)
            prev_equity = equity

            daily_records.append({
                'date': d, 'pnl_pct': pnl_pct, 'equity': equity,
                'trade_count': trade_count_today, 'won': wins_today,
            })

        # Aggregate + quality gate
        cutoff = '2099-12-31'  # default for models with unknown cutoff
        model = storage.models().get(model_id) if model_id else None
        if model is not None:
            cutoff = model.training_cutoff

        overall, zones = aggregate(daily_records, cutoff=cutoff,
                                   initial_capital=cap)
        gate_input = {
            'sharpe': overall.sharpe,
            'max_drawdown_pct': overall.max_drawdown_pct,
            'trade_count': overall.trade_count,
            'win_rate': overall.win_rate,
            'max_daily_loss_pct': overall.max_daily_loss_pct,
            'clean_zone_days': next(
                (z.days for z in zones if z.zone == 'clean'), 0),
            'divergence_flag': False,
        }
        gate = evaluate_quality_gate(gate_input)

        result = BacktestResult(
            id=str(uuid.uuid4()),
            session_id=session_id, agent_id=agent_id,
            persona_id=persona_id, model_id=model_id,
            start_date=start_date, end_date=end_date,
            initial_capital=cap, stats=overall, zone_stats=zones,
            quality_gate_label=gate.label,
            quality_gate_criteria=gate.criteria,
            final_equity=prev_equity,
        )
        storage.backtests().insert(result)
        return result
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_backtest_runner.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backtest/runner.py tests/test_backtest_runner.py
git commit -m "feat(p2c): BacktestRunner — orchestrate agent over window with zones+gate"
```

---

## Task 15: E2E smoke test (MockLLM, one persona, short window)

**Files:**
- Create: `tests/test_p2c_e2e.py`

**Responsibility:** Full end-to-end with MockLLM on a 5-day window. Assert:
1. One `backtest_results` row inserted
2. Audit log has `kind='validation'` entries (one per decision day, at minimum)
3. Quality gate label returned is one of pass/warn/fail
4. Stats are non-zero (strategy actually ran)
5. Rerunning the exact same inputs reads from cache, no new LLM calls

- [ ] **Step 1: Write failing test**

```python
# tests/test_p2c_e2e.py
"""P2c E2E — full pipeline smoke test with MockLLM."""
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
        (SQLiteCalendarStore,       'set_calendar'),
    ]:
        inst = cls(tmp_path=tmp_path)
        inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()

    from validation import rules
    rules.reset()
    import validation.handlers  # noqa

    storage.redline().set({**DEFAULT_REDLINES, 'position_max_pct': 15.0})
    from personas import seed as seed_personas
    seed_personas()
    return storage


def test_e2e_full_pipeline(wired_full, monkeypatch):
    from backtest.runner import BacktestRunner
    import backtest.runner as mod
    from llm.mock import MockLLM

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='E2E',
    )

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    prices = [(d, 1600.0 * (1 + 0.003 * i))
              for i, d in enumerate(days)]
    monkeypatch.setattr(mod, '_load_daily_closes',
                        lambda code, s, e: prices)
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)

    # Scripted: buy day 1, hold for 4 days
    buy = {
        'tool_calls': [{'id': 'c1', 'name': 'place_decision',
                        'input': {'action': 'buy', 'code': '600519.SH',
                                  'qty': 100,
                                  'reason': 'value opportunity with solid fundamentals',
                                  'thinking': 'full thinking'}}],
        'stop_reason': 'tool_use',
    }
    hold = {
        'tool_calls': [{'id': 'c', 'name': 'place_decision',
                        'input': {'action': 'hold',
                                  'reason': 'thesis intact, prices reasonable',
                                  'thinking': 't'}}],
        'stop_reason': 'tool_use',
    }
    llm = MockLLM([buy, hold, hold, hold, hold])

    runner = BacktestRunner(llm=llm)
    result = runner.run(
        session_id='e2e-1', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )

    # Assert 1: stored in backtest_results
    import storage
    stored = storage.backtests().get(result.id)
    assert stored is not None
    assert stored.agent_id == agent.id

    # Assert 2: audit log has decision entries
    rows = storage.audit().query_by_agent(agent.id)
    assert len(rows) >= 1
    assert any(r['kind'] == 'validation' for r in rows)

    # Assert 3: quality gate label set
    assert result.quality_gate_label in ('pass', 'warn', 'fail')

    # Assert 4: stats moved off zero
    assert result.stats.trade_count >= 1  # at least the day-1 buy
    assert result.final_equity is not None


def test_e2e_rerun_uses_cache(wired_full, monkeypatch):
    from backtest.runner import BacktestRunner
    import backtest.runner as mod
    from llm.mock import MockLLM

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='E2E-cache',
    )
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(3)]
    prices = [(d, 1600.0) for d in days]
    monkeypatch.setattr(mod, '_load_daily_closes',
                        lambda c, s, e: prices)
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)

    hold = {
        'tool_calls': [{'id': 'c', 'name': 'place_decision',
                        'input': {'action': 'hold',
                                  'reason': 'no reason to trade at this valuation',
                                  'thinking': 't'}}],
        'stop_reason': 'tool_use',
    }
    llm_1 = MockLLM([hold, hold, hold])

    BacktestRunner(llm=llm_1).run(
        session_id='cache-a', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-03',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )
    assert len(llm_1.calls) == 3

    # Second run with a FRESH (empty) MockLLM — must not call it.
    llm_2 = MockLLM([])  # no scripted responses; will crash if called
    BacktestRunner(llm=llm_2).run(
        session_id='cache-b', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-03',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )
    assert len(llm_2.calls) == 0  # all 3 days came from cache
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_p2c_e2e.py -v`
Expected: both FAIL until Task 14 runner is wired

- [ ] **Step 3: No implementation — runner from Task 14 should satisfy both.**

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_p2c_e2e.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_p2c_e2e.py
git commit -m "test(p2c): E2E smoke — full pipeline + cache-replay assertion"
```

---

## Task 16: Zone stats assertions (divergence detection seed)

**Files:**
- Modify: `tests/test_p2c_e2e.py` (append)

**Responsibility:** Add an assertion that backtest result exposes zone_stats with pollution/buffer/clean breakdown when the window crosses a model's training_cutoff.

- [ ] **Step 1: Write failing test**

```python
def test_zone_stats_split_across_cutoff(wired_full, monkeypatch):
    """Window straddling a model's training_cutoff must produce zone_stats."""
    from backtest.runner import BacktestRunner
    import backtest.runner as mod
    from llm.mock import MockLLM
    from datetime import date, timedelta
    import storage

    # Override the model's cutoff mid-window.
    class _M:
        training_cutoff = '2024-03-10'
    monkeypatch.setattr(storage.models(), 'get', lambda _id: _M())

    agent = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='Zones',
    )

    # 30 days straddling 2024-03-10 with 60-day buffer → all days are
    # pollution (day<cutoff) or buffer (<cutoff+60d). None are clean.
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(30)]
    prices = [(d, 1600.0) for d in days]
    monkeypatch.setattr(mod, '_load_daily_closes', lambda c, s, e: prices)
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)

    hold = {
        'tool_calls': [{'id': 'c', 'name': 'place_decision',
                        'input': {'action': 'hold',
                                  'reason': 'nothing to do, markets are stable today',
                                  'thinking': 't'}}],
        'stop_reason': 'tool_use',
    }
    llm = MockLLM([hold] * 30)
    result = BacktestRunner(llm=llm).run(
        session_id='zones', agent_id=agent.id,
        start_date='2024-03-01', end_date='2024-03-30',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )

    by_zone = {z.zone: z for z in result.zone_stats}
    assert by_zone['pollution'].days == 9   # 2024-03-01..2024-03-09
    assert by_zone['buffer'].days == 21     # 2024-03-10..2024-03-30
    assert by_zone['clean'].days == 0
```

- [ ] **Step 2: Verify**

Run: `python -m pytest tests/test_p2c_e2e.py::test_zone_stats_split_across_cutoff -v`
Expected: PASSED (no new implementation needed — runner already computes zones)

- [ ] **Step 3: Commit**

```bash
git add tests/test_p2c_e2e.py
git commit -m "test(p2c): assert zone_stats split when window crosses cutoff"
```

---

## Task 17: Multi-persona comparison

**Files:**
- Create: `tests/test_p2c_multi_persona.py`

**Responsibility:** Run two personas (e.g., linyuan and buffet) on the same window, using the same LLM backend. Produce two separate `BacktestResult` rows sharing one `session_id`. Assert list_for_session returns both; their stats may differ.

- [ ] **Step 1: Write failing test**

```python
# tests/test_p2c_multi_persona.py
"""Run two personas on the same window; compare results via session_id."""
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
        (SQLiteCalendarStore,       'set_calendar'),
    ]:
        inst = cls(tmp_path=tmp_path)
        inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()

    from validation import rules
    rules.reset()
    import validation.handlers  # noqa

    storage.redline().set({**DEFAULT_REDLINES, 'position_max_pct': 15.0})
    from personas import seed as seed_personas
    seed_personas()
    return storage


def _run_one(agent_id, session_id, llm_script, days, prices, monkeypatch):
    from backtest.runner import BacktestRunner
    import backtest.runner as mod
    from llm.mock import MockLLM
    monkeypatch.setattr(mod, '_load_daily_closes', lambda c, s, e: prices)
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    return BacktestRunner(llm=MockLLM(llm_script)).run(
        session_id=session_id, agent_id=agent_id,
        start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0, universe=['600519.SH'],
    )


def test_two_personas_same_session(wired_full, monkeypatch):
    """Two agents → two result rows with same session_id."""
    import storage
    agent_a = wired_full.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='林园 · Claude',
    )
    agent_b = wired_full.agents().create_from_persona(
        persona_id='buffet', model_id='claude-opus-4-7',
        display_name='Buffet · Claude',
    )

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    prices = [(d, 1600.0 + 2.0 * i) for i, d in enumerate(days)]

    buy = {'tool_calls': [{'id': 'c', 'name': 'place_decision',
           'input': {'action': 'buy', 'code': '600519.SH', 'qty': 100,
                     'reason': 'fundamental value with reasonable entry',
                     'thinking': 't'}}],
           'stop_reason': 'tool_use'}
    hold = {'tool_calls': [{'id': 'c', 'name': 'place_decision',
            'input': {'action': 'hold',
                      'reason': 'positioned correctly, staying put',
                      'thinking': 't'}}],
            'stop_reason': 'tool_use'}

    _run_one(agent_a.id, 'multi-1', [buy] + [hold] * 4, days, prices, monkeypatch)
    _run_one(agent_b.id, 'multi-1', [hold] * 5, days, prices, monkeypatch)

    rows = storage.backtests().list_for_session('multi-1')
    assert len(rows) == 2
    agents = {r.agent_id for r in rows}
    assert agents == {agent_a.id, agent_b.id}

    # Linyuan bought at day 1, Buffet never traded — their final_equity differs.
    by_agent = {r.agent_id: r for r in rows}
    assert by_agent[agent_a.id].stats.trade_count == 1
    assert by_agent[agent_b.id].stats.trade_count == 0
    assert by_agent[agent_a.id].final_equity != by_agent[agent_b.id].final_equity
```

- [ ] **Step 2: Verify failure then passing**

Run: `python -m pytest tests/test_p2c_multi_persona.py -v`
Expected: PASSED (runner already supports this — the test just exercises the API)

- [ ] **Step 3: Commit**

```bash
git add tests/test_p2c_multi_persona.py
git commit -m "test(p2c): multi-persona comparison via session_id"
```

---

## Task 18: Full suite verification

**Files:**
- No new code.

- [ ] **Step 1: Run full suite**

Run: `python -m pytest -q`
Expected: all green. Total count ≈ 236 (P2b) + ~60 new = ~296 tests.

- [ ] **Step 2: Review test counts per module**

Run: `python -m pytest --collect-only -q 2>&1 | tail -5`
Confirm module counts look sensible.

- [ ] **Step 3: Sanity-check git log**

Run: `git log --oneline main..HEAD`
Expected: ~18 `feat(p2c):` / `test(p2c):` / `fix(p2c):` commits, plus the plan commit.

## Post-plan verification

Key integration points to sanity-check by eye:
- `AgentRunner.run_day` correctly serializes the LLM-returned `qty` field into both `shares` (for ValidationEngine) and passes `price` from mark_prices
- `BacktestRunner.run` applies validated decisions atomically to its in-memory book; buys reduce cash, sells increase cash + mark winners
- `evaluate_quality_gate` receives `clean_zone_days` from the computed `zone_stats`
- Cache replay returns identical decision list even after ValidationEngine modifications (we cache the OUTPUT of validation, not the raw LLM response)

**Not in P2c scope** (future sub-plans):
- **P2d:** Baselines (buy-and-hold, equal-weight, random), agent rating/health scoring, divergence flag computation from zone stats
- **P2e:** `/api/backtest/run` REST endpoint, SSE progress stream, RiskMonitor & BacktestResult frontend panels, real TDX order placement in live mode
- **Deferred optimizations:** Subprocess pool for parallel agent runs, intraday 5m bars for the `intraday_t0` persona, real P1 tool execution inside the tool loop (currently stubs as `{'ack': true}`)

## Execution handoff

After writing this plan:

> Plan complete at `docs/superpowers/plans/2026-04-22-p2c-llm-strategy-backtest.md`.
>
> Two execution options:
> 1. Subagent-Driven (recommended) — fresh subagent per task with two-stage review
> 2. Inline execution — batch with manual checkpoints
>
> Which approach?
