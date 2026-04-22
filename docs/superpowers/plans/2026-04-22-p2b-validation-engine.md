# P2b: Validation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pre-trade validation engine (RedLine + per-agent rules + 4 handlers) and post-backtest quality gate, with a full audit log. Every decision from every agent passes through this pipeline.

**Architecture:**
- Two-layer rule enforcement per spec § 7: immutable global **RedLine** (single-row table) + per-agent **rules_override** (already on `Agent`). Merge via `apply_override` where overrides can only *narrow*, never widen.
- **Rule handlers** are Python classes registered by `RULE_ID`. Persona/override supplies the scalar parameter, handler does the check. Adding a new rule type = write a handler class; tuning thresholds = JSON edit, no code change.
- **Violations** split into `reject` (structural — ST, RedLine breach) vs `modify` (quantitative — shrink share count). Approved / modified / rejected outcomes + full audit trail.
- **Post-backtest gate** emits soft labels (pass/warn/fail) with per-criterion breakdown. Does not block storage; downstream (P2c+P2e) decides what to do with the label.
- **Stock status** (ST / suspended / listing_date) is a separate local table refreshed daily from TDX snapshot. `ban_st` handler queries it. Decoupled from `redlines` config table.

**Tech Stack:** Python 3.10+, sqlite3 (direct, mirrors other P2 stores), `typing.Protocol`, pytest. No new third-party deps.

---

## File Structure

### New files
- `data_schema/validation_state.py` — DDL for `redlines`, `stock_status`, `audit_log`
- `validation/__init__.py` — re-exports
- `validation/base.py` — dataclasses + `apply_override` + `DEFAULT_REDLINES` + `DEFAULT_QUALITY_GATE`
- `validation/rules.py` — `RuleHandler` Protocol + registry (`register` / `get` / `list_all` / `reset`)
- `validation/handlers/__init__.py` — imports each handler module so registration side-effects run
- `validation/handlers/position_max_pct.py`
- `validation/handlers/ban_st.py`
- `validation/handlers/max_holdings.py`
- `validation/handlers/daily_loss_limit_pct.py`
- `validation/engine.py` — `ValidationEngine.validate()` orchestrator
- `validation/quality_gate.py` — `evaluate_quality_gate(stats, thresholds)` → `QualityGateResult`
- `storage/sqlite_redline.py` — `SQLiteRedLineStore`
- `storage/sqlite_stock_status.py` — `SQLiteStockStatusStore`
- `storage/sqlite_audit.py` — `SQLiteAuditStore`
- `scripts/setup/refresh_stock_status.py` — daily TDX snapshot → `stock_status`
- `tests/test_validation_base.py`
- `tests/test_validation_rules_registry.py`
- `tests/test_handler_position_max_pct.py`
- `tests/test_handler_ban_st.py`
- `tests/test_handler_max_holdings.py`
- `tests/test_handler_daily_loss_limit_pct.py`
- `tests/test_validation_engine.py`
- `tests/test_validation_quality_gate.py`
- `tests/test_storage_redline.py`
- `tests/test_storage_stock_status.py`
- `tests/test_storage_audit.py`

### Modified files
- `storage/base.py` — append `RedLineStore`, `StockStatusStore`, `AuditStore` Protocols + `AuditEntry` dataclass
- `storage/__init__.py` — add `redline()` / `stock_status()` / `audit()` factories + `set_*` + extend `reset()`
- `tests/conftest.py` — no change needed (the existing `_reset_storage_between_tests` already calls `storage.reset()` which the new factories will integrate with)

---

## Task 1: Schemas

**Files:**
- Create: `data_schema/validation_state.py`
- Test: `tests/test_validation_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validation_schemas.py
"""DDL sanity checks for P2b validation tables."""
import sqlite3


def test_schemas_create_expected_tables(tmp_path):
    from data_schema.validation_state import (
        SCHEMA_REDLINES, SCHEMA_STOCK_STATUS, SCHEMA_AUDIT_LOG,
    )
    db = tmp_path / 'x.db'
    con = sqlite3.connect(db)
    try:
        con.executescript(SCHEMA_REDLINES)
        con.executescript(SCHEMA_STOCK_STATUS)
        con.executescript(SCHEMA_AUDIT_LOG)
        names = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    finally:
        con.close()
    assert {'redlines', 'stock_status', 'audit_log'} <= names


def test_redlines_is_single_row():
    """redlines uses id=1 as the sole row — enforced by CHECK."""
    from data_schema.validation_state import SCHEMA_REDLINES
    assert 'CHECK' in SCHEMA_REDLINES
    assert 'id = 1' in SCHEMA_REDLINES or 'id=1' in SCHEMA_REDLINES


def test_audit_log_has_indexes():
    from data_schema.validation_state import SCHEMA_AUDIT_LOG
    assert 'audit_by_agent' in SCHEMA_AUDIT_LOG
    assert 'audit_by_kind' in SCHEMA_AUDIT_LOG
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validation_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: data_schema.validation_state`

- [ ] **Step 3: Write the module**

```python
# data_schema/validation_state.py
"""DDL for validation/audit tables (P2b)."""

SCHEMA_REDLINES = '''
CREATE TABLE IF NOT EXISTS redlines (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    values_json TEXT    NOT NULL,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
'''

SCHEMA_STOCK_STATUS = '''
CREATE TABLE IF NOT EXISTS stock_status (
    code         TEXT PRIMARY KEY,
    name         TEXT,
    is_st        INTEGER NOT NULL DEFAULT 0,
    is_suspended INTEGER NOT NULL DEFAULT 0,
    is_delisted  INTEGER NOT NULL DEFAULT 0,
    listing_date TEXT,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS stock_status_st ON stock_status(is_st);
'''

SCHEMA_AUDIT_LOG = '''
CREATE TABLE IF NOT EXISTS audit_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      DATETIME DEFAULT CURRENT_TIMESTAMP,
    kind           TEXT NOT NULL,
    agent_id       TEXT,
    persona_id     TEXT,
    model_id       TEXT,
    prompt_version INTEGER,
    details        TEXT
);
CREATE INDEX IF NOT EXISTS audit_by_agent ON audit_log(agent_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS audit_by_kind  ON audit_log(kind, timestamp DESC);
'''
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validation_schemas.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add data_schema/validation_state.py tests/test_validation_schemas.py
git commit -m "feat(p2b): schemas for redlines + stock_status + audit_log"
```

---

## Task 2: Validation dataclasses + `apply_override` + defaults

**Files:**
- Create: `validation/__init__.py`, `validation/base.py`
- Test: `tests/test_validation_base.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validation_base.py
"""Validation core dataclasses + apply_override semantics."""


def test_defaults_expose_expected_keys():
    from validation.base import DEFAULT_REDLINES, DEFAULT_QUALITY_GATE
    # Spec § 7.1
    assert 'position_max_pct' in DEFAULT_REDLINES
    assert 'ban_st' in DEFAULT_REDLINES
    assert 'daily_loss_max_pct' in DEFAULT_REDLINES
    # Spec § 7.4
    assert 'min_sharpe' in DEFAULT_QUALITY_GATE
    assert 'max_drawdown_pct' in DEFAULT_QUALITY_GATE


def test_apply_override_narrows_upper_bound():
    from validation.base import apply_override
    redline = {'position_max_pct': 15.0}
    # Agent wants stricter
    assert apply_override(redline, {'position_max_pct': 10.0}) \
        == {'position_max_pct': 10.0}


def test_apply_override_clamps_attempt_to_widen_upper_bound():
    from validation.base import apply_override
    redline = {'position_max_pct': 15.0}
    # Agent tries to widen — clamped back to RedLine
    assert apply_override(redline, {'position_max_pct': 40.0}) \
        == {'position_max_pct': 15.0}


def test_apply_override_raises_lower_bound_only():
    from validation.base import apply_override
    redline = {'cash_min_pct': 5.0}
    # Stricter override raises minimum
    assert apply_override(redline, {'cash_min_pct': 10.0}) \
        == {'cash_min_pct': 10.0}
    # Attempt to weaken is clamped
    assert apply_override(redline, {'cash_min_pct': 2.0}) \
        == {'cash_min_pct': 5.0}


def test_apply_override_ban_toggle_is_or_not_override():
    from validation.base import apply_override
    assert apply_override({'ban_st': True}, {'ban_st': False}) == {'ban_st': True}
    assert apply_override({'ban_st': False}, {'ban_st': True}) == {'ban_st': True}
    assert apply_override({'ban_st': False}, {'ban_st': False}) == {'ban_st': False}


def test_apply_override_passes_through_unknown_keys_from_override():
    """Persona-specific rules (e.g., max_holdings) not in RedLine flow through."""
    from validation.base import apply_override
    result = apply_override({'position_max_pct': 15.0}, {'max_holdings': 10})
    assert result == {'position_max_pct': 15.0, 'max_holdings': 10}


def test_violation_and_result_dataclasses_exist():
    from validation.base import Violation, ValidationRequest, ValidationResult
    v = Violation(
        rule_id='position_max_pct', severity='modify',
        reason='shrunk', modification={'shares': 300},
    )
    assert v.rule_id == 'position_max_pct'
    # Frozen: attribute assignment raises
    import dataclasses
    assert dataclasses.is_dataclass(ValidationRequest)
    assert dataclasses.is_dataclass(ValidationResult)


def test_audit_entry_fields():
    from validation.base import AuditEntry
    e = AuditEntry(
        kind='validation', agent_id='a1', details={'x': 1},
    )
    assert e.kind == 'validation'
    assert e.agent_id == 'a1'
    assert e.persona_id is None  # optional
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validation_base.py -v`
Expected: FAIL — `ModuleNotFoundError: validation`

- [ ] **Step 3: Implement validation/base.py**

```python
# validation/__init__.py
"""Validation engine — pre-trade + post-backtest checks (P2b)."""
```

```python
# validation/base.py
"""Core types for the validation engine.

Two layers per Spec § 7:
  Layer 1 — RedLine (single-row `redlines` table, immutable ceiling)
  Layer 2 — Agent rules_override (stricter-only, merged via apply_override)

Handlers consume the merged dict and each check a single rule.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_REDLINES: dict[str, Any] = {
    # hard upper-bound limits (override may only lower)
    'daily_loss_max_pct':    3.0,
    'position_max_pct':      15.0,
    'stock_concentration':   30.0,
    'order_max_value':       200_000,
    'turnover_max_daily':    300.0,
    'same_stock_cooldown_min': 5,
    # hard lower-bound limits (override may only raise)
    'cash_min_pct':          5.0,
    # behavioral toggles (override may only turn on)
    'ban_limit_up':          True,
    'ban_st':                True,
    'ban_limit_down':        True,
    'ban_ipo_30d':           True,
    'require_reason':        True,
    'prompt_injection_check': True,
    'auto_halt_var_2sigma':  True,
}


DEFAULT_QUALITY_GATE: dict[str, Any] = {
    'min_sharpe':            0.3,
    'max_drawdown_pct':     -25.0,
    'min_trade_count':       5,
    'min_win_rate':          30.0,
    'max_daily_loss_pct':   -5.0,
    'min_clean_zone_days':   60,
    'max_divergence_flag':   False,
}


# Keys that are lower-bounds (override may only *raise* them).
_LOWER_BOUND_KEYS = frozenset({'cash_min_pct'})


def apply_override(redline: dict, override: dict | None) -> dict:
    """Merge per-agent override onto RedLine, clamping to RedLine's direction.

    Upper-bound numeric keys      -> min(redline, override)
    Lower-bound numeric keys      -> max(redline, override)
    Boolean keys starting 'ban_'  -> redline OR override (only tighten)
    Unknown keys in override      -> pass through (persona-only rules)
    Keys only in redline          -> kept as-is
    """
    if not override:
        return dict(redline)
    result = dict(redline)
    for k, v in override.items():
        if k not in redline:
            result[k] = v
            continue
        rv = redline[k]
        if isinstance(rv, bool) and k.startswith('ban_'):
            result[k] = bool(rv) or bool(v)
        elif k in _LOWER_BOUND_KEYS:
            result[k] = max(rv, v)
        elif isinstance(rv, (int, float)) and not isinstance(rv, bool):
            result[k] = min(rv, v)
        else:
            # Non-numeric, non-toggle: keep redline
            result[k] = rv
    return result


@dataclass(frozen=True)
class ValidationRequest:
    """Snapshot of everything a handler needs to judge one decision."""
    agent_id: str
    decision: dict                 # place_decision tool call args (mutable copy ok)
    portfolio: dict                # positions, cash, equity at decision time
    market_context: dict           # e.g., {'index_pct_today': -1.2, 'pnl_today_pct': -0.8}
    rules: dict                    # merged RedLine ∪ override
    persona_id: str | None = None
    model_id: str | None = None


@dataclass(frozen=True)
class Violation:
    rule_id: str
    severity: str                  # 'reject' | 'modify' | 'warn'
    reason: str
    modification: dict | None = None  # keys to overwrite on decision; None for reject


@dataclass(frozen=True)
class ValidationResult:
    outcome: str                   # 'approved' | 'modified' | 'rejected'
    decision_out: dict | None      # None iff rejected
    violations: tuple = ()


@dataclass(frozen=True)
class QualityGateResult:
    label: str                     # 'pass' | 'warn' | 'fail'
    criteria: dict                 # {criterion: {'ok': bool, 'actual': Any, 'threshold': Any, 'reason': str}}


@dataclass
class AuditEntry:
    """One row for `audit_log` — `details` is serialized to JSON by the store."""
    kind: str                      # 'validation' | 'trade_executed' | 'trade_blocked' | ...
    agent_id: str | None = None
    persona_id: str | None = None
    model_id: str | None = None
    prompt_version: int | None = None
    details: dict = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validation_base.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add validation/ tests/test_validation_base.py
git commit -m "feat(p2b): validation dataclasses + apply_override merge + defaults"
```

---

## Task 3: Storage Protocols for RedLine / StockStatus / Audit

**Files:**
- Modify: `storage/base.py` (append)
- Test: `tests/test_storage_base.py` (append cases)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_storage_base.py`:

```python
def test_redline_store_protocol_exists():
    from storage.base import RedLineStore
    # Protocol classes must declare required methods
    assert hasattr(RedLineStore, 'init_schema')
    assert hasattr(RedLineStore, 'get')
    assert hasattr(RedLineStore, 'set')


def test_stock_status_store_protocol_exists():
    from storage.base import StockStatusStore
    for m in ('init_schema', 'upsert', 'get', 'is_st', 'is_suspended', 'bulk_upsert'):
        assert hasattr(StockStatusStore, m), f'missing {m}'


def test_audit_store_protocol_exists():
    from storage.base import AuditStore
    for m in ('init_schema', 'log', 'query_by_agent', 'query_by_kind'):
        assert hasattr(AuditStore, m), f'missing {m}'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage_base.py -v`
Expected: 3 new cases FAIL (`ImportError`)

- [ ] **Step 3: Append to storage/base.py**

```python
# --- Added in P2b ---


@dataclass
class StockStatusRow:
    """Per-stock tradability flags refreshed daily from TDX snapshot."""
    code: str
    name: str | None
    is_st: bool
    is_suspended: bool
    is_delisted: bool
    listing_date: str | None = None
    updated_at: str | None = None


@runtime_checkable
class RedLineStore(Protocol):
    """Single-row global RedLine config."""
    def init_schema(self) -> None: ...
    def get(self) -> dict:
        """Return current RedLine. Must return DEFAULT_REDLINES if table empty."""
        ...
    def set(self, values: dict) -> None:
        """Atomically replace the single row. Records a 'redline_changed'
        audit entry is the engine's responsibility, not this store's."""
        ...


@runtime_checkable
class StockStatusStore(Protocol):
    """Per-stock tradability flags (ST / suspended / delisted)."""
    def init_schema(self) -> None: ...
    def upsert(self, row: StockStatusRow) -> None: ...
    def bulk_upsert(self, rows: list[StockStatusRow]) -> int:
        """Returns count written."""
        ...
    def get(self, code: str) -> StockStatusRow | None: ...
    def is_st(self, code: str) -> bool:
        """Missing row -> False (trade allowed until proven otherwise)."""
        ...
    def is_suspended(self, code: str) -> bool: ...


@runtime_checkable
class AuditStore(Protocol):
    """Append-only audit log; never truncated in MVP."""
    def init_schema(self) -> None: ...
    def log(self, entry) -> int:
        """Insert an AuditEntry. Returns the new row id."""
        ...
    def query_by_agent(self, agent_id: str, limit: int = 100) -> list[dict]:
        """Most recent first."""
        ...
    def query_by_kind(self, kind: str, limit: int = 100) -> list[dict]: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage_base.py -v`
Expected: previous tests + 3 new PASSED

- [ ] **Step 5: Commit**

```bash
git add storage/base.py tests/test_storage_base.py
git commit -m "feat(p2b): RedLineStore + StockStatusStore + AuditStore Protocols"
```

---

## Task 4: SQLiteRedLineStore

**Files:**
- Create: `storage/sqlite_redline.py`
- Test: `tests/test_storage_redline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storage_redline.py
"""SQLiteRedLineStore — single-row config with defaults fallback."""


def test_get_on_empty_returns_defaults(tmp_path):
    from storage.sqlite_redline import SQLiteRedLineStore
    from validation.base import DEFAULT_REDLINES
    s = SQLiteRedLineStore(tmp_path=tmp_path)
    s.init_schema()
    assert s.get() == DEFAULT_REDLINES


def test_set_then_get_roundtrip(tmp_path):
    from storage.sqlite_redline import SQLiteRedLineStore
    from validation.base import DEFAULT_REDLINES
    s = SQLiteRedLineStore(tmp_path=tmp_path)
    s.init_schema()
    custom = {**DEFAULT_REDLINES, 'position_max_pct': 10.0}
    s.set(custom)
    assert s.get()['position_max_pct'] == 10.0


def test_set_is_single_row(tmp_path):
    """Calling set() twice must not grow the table."""
    import sqlite3
    from storage.sqlite_redline import SQLiteRedLineStore
    from validation.base import DEFAULT_REDLINES
    s = SQLiteRedLineStore(tmp_path=tmp_path)
    s.init_schema()
    s.set({**DEFAULT_REDLINES, 'position_max_pct': 12.0})
    s.set({**DEFAULT_REDLINES, 'position_max_pct': 8.0})
    con = sqlite3.connect(tmp_path / 'agent_state.db')
    try:
        n = con.execute('SELECT COUNT(*) FROM redlines').fetchone()[0]
    finally:
        con.close()
    assert n == 1
    assert s.get()['position_max_pct'] == 8.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage_redline.py -v`
Expected: FAIL (`ModuleNotFoundError: storage.sqlite_redline`)

- [ ] **Step 3: Implement**

```python
# storage/sqlite_redline.py
"""SQLiteRedLineStore — global RedLine, stored as a single JSON row."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from data_schema.validation_state import SCHEMA_REDLINES
from validation.base import DEFAULT_REDLINES

from .base import RedLineStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


class SQLiteRedLineStore(RedLineStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_REDLINES)
            con.commit()
        finally:
            con.close()

    def get(self) -> dict:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_REDLINES)
            row = con.execute(
                'SELECT values_json FROM redlines WHERE id = 1'
            ).fetchone()
        finally:
            con.close()
        if row is None:
            return dict(DEFAULT_REDLINES)
        return json.loads(row[0])

    def set(self, values: dict) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_REDLINES)
            con.execute(
                '''INSERT INTO redlines (id, values_json)
                   VALUES (1, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       values_json = excluded.values_json,
                       updated_at  = CURRENT_TIMESTAMP''',
                (json.dumps(values, ensure_ascii=False),),
            )
            con.commit()
        finally:
            con.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage_redline.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add storage/sqlite_redline.py tests/test_storage_redline.py
git commit -m "feat(p2b): SQLiteRedLineStore with single-row get/set + defaults"
```

---

## Task 5: SQLiteStockStatusStore

**Files:**
- Create: `storage/sqlite_stock_status.py`
- Test: `tests/test_storage_stock_status.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storage_stock_status.py
"""SQLiteStockStatusStore — per-code tradability flags."""


def test_missing_code_is_st_returns_false(tmp_path):
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    assert s.is_st('600519.SH') is False
    assert s.is_suspended('600519.SH') is False
    assert s.get('600519.SH') is None


def test_upsert_then_get(tmp_path):
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.base import StockStatusRow
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    s.upsert(StockStatusRow(
        code='000001.SZ', name='平安银行',
        is_st=False, is_suspended=False, is_delisted=False,
        listing_date='1991-04-03',
    ))
    row = s.get('000001.SZ')
    assert row is not None
    assert row.name == '平安银行'
    assert row.is_st is False


def test_upsert_replaces_existing(tmp_path):
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.base import StockStatusRow
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    s.upsert(StockStatusRow(code='X.SH', name='X', is_st=False,
                            is_suspended=False, is_delisted=False))
    s.upsert(StockStatusRow(code='X.SH', name='*ST X', is_st=True,
                            is_suspended=False, is_delisted=False))
    assert s.is_st('X.SH') is True
    assert s.get('X.SH').name == '*ST X'


def test_bulk_upsert_returns_count(tmp_path):
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.base import StockStatusRow
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    n = s.bulk_upsert([
        StockStatusRow(code=f'{i:06d}.SH', name=f'n{i}', is_st=False,
                       is_suspended=False, is_delisted=False)
        for i in range(10)
    ])
    assert n == 10


def test_suspended_flag(tmp_path):
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.base import StockStatusRow
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    s.upsert(StockStatusRow(code='Y.SZ', name='Y', is_st=False,
                            is_suspended=True, is_delisted=False))
    assert s.is_suspended('Y.SZ') is True
    assert s.is_st('Y.SZ') is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage_stock_status.py -v`
Expected: 5 FAIL

- [ ] **Step 3: Implement**

```python
# storage/sqlite_stock_status.py
"""SQLiteStockStatusStore — per-code ST/suspended flags."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from data_schema.validation_state import SCHEMA_STOCK_STATUS

from .base import StockStatusRow, StockStatusStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _row_to_obj(row) -> StockStatusRow:
    return StockStatusRow(
        code=row[0], name=row[1],
        is_st=bool(row[2]), is_suspended=bool(row[3]),
        is_delisted=bool(row[4]),
        listing_date=row[5], updated_at=row[6],
    )


class SQLiteStockStatusStore(StockStatusStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_STOCK_STATUS)
            con.commit()
        finally:
            con.close()

    def upsert(self, row: StockStatusRow) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_STOCK_STATUS)
            con.execute(
                '''INSERT OR REPLACE INTO stock_status
                   (code, name, is_st, is_suspended, is_delisted, listing_date)
                   VALUES (?,?,?,?,?,?)''',
                (row.code, row.name,
                 1 if row.is_st else 0,
                 1 if row.is_suspended else 0,
                 1 if row.is_delisted else 0,
                 row.listing_date),
            )
            con.commit()
        finally:
            con.close()

    def bulk_upsert(self, rows: list[StockStatusRow]) -> int:
        if not rows:
            return 0
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_STOCK_STATUS)
            con.executemany(
                '''INSERT OR REPLACE INTO stock_status
                   (code, name, is_st, is_suspended, is_delisted, listing_date)
                   VALUES (?,?,?,?,?,?)''',
                [(r.code, r.name,
                  1 if r.is_st else 0,
                  1 if r.is_suspended else 0,
                  1 if r.is_delisted else 0,
                  r.listing_date) for r in rows],
            )
            con.commit()
        finally:
            con.close()
        return len(rows)

    def get(self, code: str) -> StockStatusRow | None:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                '''SELECT code, name, is_st, is_suspended, is_delisted,
                          listing_date, updated_at
                   FROM stock_status WHERE code = ?''',
                (code,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return _row_to_obj(row) if row else None

    def is_st(self, code: str) -> bool:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                'SELECT is_st FROM stock_status WHERE code = ?', (code,)
            ).fetchone()
        except sqlite3.OperationalError:
            return False
        finally:
            con.close()
        return bool(row[0]) if row else False

    def is_suspended(self, code: str) -> bool:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                'SELECT is_suspended FROM stock_status WHERE code = ?', (code,)
            ).fetchone()
        except sqlite3.OperationalError:
            return False
        finally:
            con.close()
        return bool(row[0]) if row else False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage_stock_status.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add storage/sqlite_stock_status.py tests/test_storage_stock_status.py
git commit -m "feat(p2b): SQLiteStockStatusStore with is_st/is_suspended lookups"
```

---

## Task 6: SQLiteAuditStore

**Files:**
- Create: `storage/sqlite_audit.py`
- Test: `tests/test_storage_audit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storage_audit.py
"""SQLiteAuditStore — append-only log with indexed queries."""


def _store(tmp_path):
    from storage.sqlite_audit import SQLiteAuditStore
    s = SQLiteAuditStore(tmp_path=tmp_path)
    s.init_schema()
    return s


def test_log_returns_row_id(tmp_path):
    from validation.base import AuditEntry
    s = _store(tmp_path)
    rid = s.log(AuditEntry(kind='validation', agent_id='a1',
                           details={'outcome': 'approved'}))
    assert isinstance(rid, int)
    assert rid > 0


def test_query_by_agent_most_recent_first(tmp_path):
    import time
    from validation.base import AuditEntry
    s = _store(tmp_path)
    s.log(AuditEntry(kind='validation', agent_id='a1', details={'n': 1}))
    time.sleep(0.02)
    s.log(AuditEntry(kind='validation', agent_id='a1', details={'n': 2}))
    rows = s.query_by_agent('a1')
    assert len(rows) == 2
    assert rows[0]['details']['n'] == 2  # newest first


def test_query_by_agent_filters(tmp_path):
    from validation.base import AuditEntry
    s = _store(tmp_path)
    s.log(AuditEntry(kind='validation', agent_id='a1', details={}))
    s.log(AuditEntry(kind='validation', agent_id='a2', details={}))
    assert len(s.query_by_agent('a1')) == 1
    assert len(s.query_by_agent('a2')) == 1
    assert len(s.query_by_agent('a3')) == 0


def test_query_by_kind(tmp_path):
    from validation.base import AuditEntry
    s = _store(tmp_path)
    s.log(AuditEntry(kind='validation', agent_id='a1', details={}))
    s.log(AuditEntry(kind='trade_blocked', agent_id='a1', details={}))
    s.log(AuditEntry(kind='trade_executed', agent_id='a1', details={}))
    assert len(s.query_by_kind('validation')) == 1
    assert len(s.query_by_kind('trade_blocked')) == 1


def test_limit_caps_results(tmp_path):
    from validation.base import AuditEntry
    s = _store(tmp_path)
    for i in range(20):
        s.log(AuditEntry(kind='validation', agent_id='a1', details={'n': i}))
    assert len(s.query_by_agent('a1', limit=5)) == 5


def test_details_roundtrips_as_json(tmp_path):
    from validation.base import AuditEntry
    s = _store(tmp_path)
    s.log(AuditEntry(
        kind='validation', agent_id='a1',
        details={'violations': [{'rule_id': 'position_max_pct',
                                 'severity': 'modify'}]},
    ))
    row = s.query_by_agent('a1')[0]
    assert row['details']['violations'][0]['rule_id'] == 'position_max_pct'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage_audit.py -v`
Expected: 6 FAIL

- [ ] **Step 3: Implement**

```python
# storage/sqlite_audit.py
"""SQLiteAuditStore — append-only log. Never truncated in MVP (Spec § 7.5)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from data_schema.validation_state import SCHEMA_AUDIT_LOG

from .base import AuditStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _row_to_dict(row) -> dict:
    return {
        'id': row[0], 'timestamp': row[1], 'kind': row[2],
        'agent_id': row[3], 'persona_id': row[4], 'model_id': row[5],
        'prompt_version': row[6],
        'details': json.loads(row[7]) if row[7] else {},
    }


class SQLiteAuditStore(AuditStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_AUDIT_LOG)
            con.commit()
        finally:
            con.close()

    def log(self, entry) -> int:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_AUDIT_LOG)
            cur = con.execute(
                '''INSERT INTO audit_log
                   (kind, agent_id, persona_id, model_id,
                    prompt_version, details)
                   VALUES (?,?,?,?,?,?)''',
                (entry.kind, entry.agent_id, entry.persona_id,
                 entry.model_id, entry.prompt_version,
                 json.dumps(entry.details, ensure_ascii=False)),
            )
            con.commit()
            return cur.lastrowid
        finally:
            con.close()

    def query_by_agent(self, agent_id: str, limit: int = 100) -> list[dict]:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                '''SELECT id, timestamp, kind, agent_id, persona_id, model_id,
                          prompt_version, details
                   FROM audit_log WHERE agent_id = ?
                   ORDER BY id DESC LIMIT ?''',
                (agent_id, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_dict(r) for r in rows]

    def query_by_kind(self, kind: str, limit: int = 100) -> list[dict]:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                '''SELECT id, timestamp, kind, agent_id, persona_id, model_id,
                          prompt_version, details
                   FROM audit_log WHERE kind = ?
                   ORDER BY id DESC LIMIT ?''',
                (kind, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_dict(r) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage_audit.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add storage/sqlite_audit.py tests/test_storage_audit.py
git commit -m "feat(p2b): SQLiteAuditStore with query_by_agent/query_by_kind"
```

---

## Task 7: Storage factories for new stores

**Files:**
- Modify: `storage/__init__.py`
- Test: `tests/test_storage_factories_p2b.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storage_factories_p2b.py
"""Factory + set_* + reset() coverage for P2b stores."""


def test_redline_factory_returns_singleton():
    import storage
    storage.reset()
    a = storage.redline()
    b = storage.redline()
    assert a is b


def test_stock_status_factory_returns_singleton():
    import storage
    storage.reset()
    a = storage.stock_status()
    b = storage.stock_status()
    assert a is b


def test_audit_factory_returns_singleton():
    import storage
    storage.reset()
    a = storage.audit()
    b = storage.audit()
    assert a is b


def test_set_redline_overrides_factory(tmp_path):
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    s = SQLiteRedLineStore(tmp_path=tmp_path)
    storage.set_redline(s)
    assert storage.redline() is s


def test_set_stock_status_overrides_factory(tmp_path):
    import storage
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    storage.set_stock_status(s)
    assert storage.stock_status() is s


def test_set_audit_overrides_factory(tmp_path):
    import storage
    from storage.sqlite_audit import SQLiteAuditStore
    s = SQLiteAuditStore(tmp_path=tmp_path)
    storage.set_audit(s)
    assert storage.audit() is s


def test_reset_clears_all_p2b_stores(tmp_path):
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    storage.set_redline(SQLiteRedLineStore(tmp_path=tmp_path))
    storage.reset()
    # After reset, factory must construct fresh instance
    assert isinstance(storage.redline(), type(storage.redline()))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage_factories_p2b.py -v`
Expected: 7 FAIL (`AttributeError: module 'storage' has no attribute 'redline'`)

- [ ] **Step 3: Modify storage/__init__.py**

Replace the imports from `.base` with:

```python
from .base import (
    Agent, AgentStore, AuditStore, CalendarStore, FinancialStore,
    KlineStore, ModelInfo, ModelStore, Persona, PersonaStore,
    PromptVersion, PromptVersionStore, RedLineStore, StockStatusStore,
)
```

Append new module-level singletons after the existing ones:

```python
_redline: RedLineStore | None = None
_stock_status: StockStatusStore | None = None
_audit: AuditStore | None = None


def redline() -> RedLineStore:
    global _redline
    if _redline is None:
        from .sqlite_redline import SQLiteRedLineStore
        _redline = SQLiteRedLineStore()
    return _redline


def stock_status() -> StockStatusStore:
    global _stock_status
    if _stock_status is None:
        from .sqlite_stock_status import SQLiteStockStatusStore
        _stock_status = SQLiteStockStatusStore()
    return _stock_status


def audit() -> AuditStore:
    global _audit
    if _audit is None:
        from .sqlite_audit import SQLiteAuditStore
        _audit = SQLiteAuditStore()
    return _audit


def set_redline(impl: RedLineStore) -> None:
    global _redline
    _redline = impl


def set_stock_status(impl: StockStatusStore) -> None:
    global _stock_status
    _stock_status = impl


def set_audit(impl: AuditStore) -> None:
    global _audit
    _audit = impl
```

And extend `reset()` to clear the three new globals:

```python
def reset() -> None:
    global _kline, _financial, _models, _calendar
    global _personas, _agents, _prompt_versions
    global _redline, _stock_status, _audit
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage_factories_p2b.py -v`
Expected: 7 PASSED

Run: `pytest -q` (full regression)
Expected: All existing tests still green

- [ ] **Step 5: Commit**

```bash
git add storage/__init__.py tests/test_storage_factories_p2b.py
git commit -m "feat(p2b): storage factories redline() + stock_status() + audit()"
```

---

## Task 8: RuleHandler Protocol + registry

**Files:**
- Create: `validation/rules.py`
- Test: `tests/test_validation_rules_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validation_rules_registry.py
"""RuleHandler Protocol + registry."""
import pytest


def _dummy_req():
    from validation.base import ValidationRequest
    return ValidationRequest(
        agent_id='a1', decision={}, portfolio={}, market_context={},
        rules={'position_max_pct': 15.0},
    )


def test_register_then_get():
    from validation import rules

    rules.reset()

    class FakeHandler:
        RULE_ID = 'fake'

        def check(self, req):
            return None

    rules.register(FakeHandler())
    assert rules.get('fake').__class__.__name__ == 'FakeHandler'


def test_list_all_returns_registered():
    from validation import rules
    rules.reset()

    class A:
        RULE_ID = 'a'
        def check(self, req): return None

    class B:
        RULE_ID = 'b'
        def check(self, req): return None

    rules.register(A())
    rules.register(B())
    assert {h.RULE_ID for h in rules.list_all()} == {'a', 'b'}


def test_register_same_id_replaces():
    from validation import rules
    rules.reset()

    class H1:
        RULE_ID = 'dup'
        def check(self, req): return None

    class H2:
        RULE_ID = 'dup'
        def check(self, req): return None

    rules.register(H1())
    rules.register(H2())
    assert rules.get('dup').__class__.__name__ == 'H2'
    assert len(rules.list_all()) == 1


def test_get_unknown_returns_none():
    from validation import rules
    rules.reset()
    assert rules.get('nope') is None


def test_register_rejects_handler_without_rule_id():
    from validation import rules
    rules.reset()

    class Bad:
        def check(self, req): return None

    with pytest.raises(TypeError):
        rules.register(Bad())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validation_rules_registry.py -v`
Expected: 5 FAIL (`ImportError: cannot import name 'rules' from 'validation'`)

- [ ] **Step 3: Implement**

```python
# validation/rules.py
"""RuleHandler Protocol + module-level registry.

Handlers declare a string RULE_ID and implement check(req) -> Violation | None.
Registration is side-effectful: each handler module calls register() on import.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .base import ValidationRequest, Violation


@runtime_checkable
class RuleHandler(Protocol):
    RULE_ID: str

    def check(self, req: ValidationRequest) -> Violation | None: ...


_registry: dict[str, RuleHandler] = {}


def register(handler: RuleHandler) -> None:
    rule_id = getattr(handler, 'RULE_ID', None)
    if not rule_id:
        raise TypeError(f'{type(handler).__name__} must declare RULE_ID')
    _registry[rule_id] = handler


def get(rule_id: str) -> RuleHandler | None:
    return _registry.get(rule_id)


def list_all() -> list[RuleHandler]:
    return list(_registry.values())


def reset() -> None:
    """Clear registry — for tests only."""
    _registry.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validation_rules_registry.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add validation/rules.py tests/test_validation_rules_registry.py
git commit -m "feat(p2b): RuleHandler Protocol + module-level registry"
```

---

## Task 9: Handler — position_max_pct (auto-modify)

**Files:**
- Create: `validation/handlers/__init__.py`, `validation/handlers/position_max_pct.py`
- Test: `tests/test_handler_position_max_pct.py`

**Rule:** After this order, single-stock value as % of total equity must be ≤ `rules['position_max_pct']`. If violation is *quantitative* (shares can be reduced), auto-modify shares downward. Only rejects if `position_max_pct` is 0 (never buy — treat as reject).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_handler_position_max_pct.py
"""position_max_pct handler — auto-shrink when over-cap."""
from validation.base import ValidationRequest


def _make_req(*, action, shares, price, code='600519.SH',
              held_shares=0, cash=1_000_000, equity=1_000_000,
              max_pct=15.0):
    return ValidationRequest(
        agent_id='a1',
        decision={'action': action, 'code': code,
                  'shares': shares, 'price': price},
        portfolio={
            'cash': cash,
            'equity': equity,
            'positions': {code: {'shares': held_shares, 'avg_price': price}},
        },
        market_context={},
        rules={'position_max_pct': max_pct},
    )


def test_passes_when_under_cap():
    from validation.handlers.position_max_pct import Handler
    # buy 100 * 1000 = 100k on 1M equity = 10% ≤ 15%
    req = _make_req(action='buy', shares=100, price=1000.0)
    assert Handler().check(req) is None


def test_shrinks_when_over_cap():
    from validation.handlers.position_max_pct import Handler
    # buy 200 * 1000 = 200k on 1M equity = 20% > 15%.
    # Max allowed value = 150k ⇒ shares = floor(150k / 1000) = 150
    req = _make_req(action='buy', shares=200, price=1000.0)
    v = Handler().check(req)
    assert v is not None
    assert v.rule_id == 'position_max_pct'
    assert v.severity == 'modify'
    assert v.modification == {'shares': 150}


def test_accounts_for_existing_holding():
    from validation.handlers.position_max_pct import Handler
    # Already hold 100 shares; attempting to buy 100 more ⇒ post 200 shares = 20% > 15%
    req = _make_req(action='buy', shares=100, price=1000.0, held_shares=100)
    v = Handler().check(req)
    assert v is not None
    assert v.severity == 'modify'
    # Max total = 150 shares. Since 100 already held, can buy at most 50.
    assert v.modification == {'shares': 50}


def test_existing_holding_already_over_cap_rejects_buy():
    from validation.handlers.position_max_pct import Handler
    # Already hold 200 shares = 20% > 15%. Any additional buy is rejected
    # (can't shrink to 0; use sell action instead).
    req = _make_req(action='buy', shares=10, price=1000.0, held_shares=200)
    v = Handler().check(req)
    assert v is not None
    assert v.severity == 'reject'


def test_sell_is_always_ok():
    """Handler only constrains buys that would take position over cap."""
    from validation.handlers.position_max_pct import Handler
    req = _make_req(action='sell', shares=50, price=1000.0, held_shares=200)
    assert Handler().check(req) is None


def test_zero_cap_rejects_any_buy():
    from validation.handlers.position_max_pct import Handler
    req = _make_req(action='buy', shares=1, price=1000.0, max_pct=0.0)
    v = Handler().check(req)
    assert v is not None
    assert v.severity == 'reject'


def test_missing_rule_is_noop():
    """Handler is called only when rule is in effective_rules, but be defensive."""
    from validation.handlers.position_max_pct import Handler
    req = ValidationRequest(
        agent_id='a1', decision={'action': 'buy', 'code': 'X', 'shares': 1, 'price': 1.0},
        portfolio={'equity': 1.0, 'positions': {}}, market_context={}, rules={},
    )
    assert Handler().check(req) is None


def test_registered_on_import():
    from validation import rules
    import validation.handlers.position_max_pct  # noqa: F401
    assert rules.get('position_max_pct') is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_handler_position_max_pct.py -v`
Expected: 8 FAIL

- [ ] **Step 3: Implement**

```python
# validation/handlers/__init__.py
"""Importing this package registers every built-in rule handler.

Subagents: add `from . import <new_handler>` here when you add a handler
module, so tests and the engine both see it via the registry.
"""
from . import position_max_pct  # noqa: F401
```

```python
# validation/handlers/position_max_pct.py
"""Constrains single-stock value as % of equity.

Policy:
  - BUY that would bring position over cap  →  auto-modify, shrink shares
  - BUY when existing holding already over cap → reject
  - cap == 0 → reject any buy
  - SELL / non-buy → pass through
"""
from __future__ import annotations

import math

from validation.base import ValidationRequest, Violation
from validation import rules as _rules


RULE_ID = 'position_max_pct'


class Handler:
    RULE_ID = RULE_ID

    def check(self, req: ValidationRequest) -> Violation | None:
        cap_pct = req.rules.get('position_max_pct')
        if cap_pct is None:
            return None
        action = (req.decision.get('action') or '').lower()
        if action != 'buy':
            return None

        equity = float(req.portfolio.get('equity', 0.0))
        if equity <= 0:
            return None
        price = float(req.decision.get('price', 0.0))
        if price <= 0:
            return None

        code = req.decision.get('code')
        held = int(req.portfolio.get('positions', {}).get(code, {}).get('shares', 0))
        shares_req = int(req.decision.get('shares', 0))

        max_value = equity * (float(cap_pct) / 100.0)
        if max_value <= 0:
            return Violation(
                rule_id=RULE_ID, severity='reject',
                reason=f'position_max_pct={cap_pct} forbids any buy',
            )

        held_value = held * price
        if held_value >= max_value:
            return Violation(
                rule_id=RULE_ID, severity='reject',
                reason=(f'existing holding value {held_value:.0f} already '
                        f'≥ cap {max_value:.0f}'),
            )

        post_value = (held + shares_req) * price
        if post_value <= max_value:
            return None

        # Auto-shrink
        allowed_additional = int(math.floor((max_value - held_value) / price))
        if allowed_additional < shares_req:
            return Violation(
                rule_id=RULE_ID, severity='modify',
                reason=(f'post-trade value {post_value:.0f} > cap '
                        f'{max_value:.0f}; shrink to {allowed_additional} shares'),
                modification={'shares': allowed_additional},
            )
        return None


_rules.register(Handler())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_handler_position_max_pct.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add validation/handlers/ tests/test_handler_position_max_pct.py
git commit -m "feat(p2b): handler position_max_pct — auto-shrink over-cap buys"
```

---

## Task 10: Handler — ban_st (reject)

**Files:**
- Create: `validation/handlers/ban_st.py`
- Modify: `validation/handlers/__init__.py`
- Test: `tests/test_handler_ban_st.py`

**Rule:** If `rules['ban_st']` is True and `storage.stock_status().is_st(code)` is True, reject. Toggle False / missing → pass.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_handler_ban_st.py
"""ban_st handler — blocks trades on ST stocks."""
from validation.base import ValidationRequest


def _req(code, ban=True, action='buy'):
    return ValidationRequest(
        agent_id='a1',
        decision={'action': action, 'code': code, 'shares': 100, 'price': 10.0},
        portfolio={'equity': 1_000_000, 'positions': {}},
        market_context={}, rules={'ban_st': ban},
    )


def _wire(tmp_path):
    import storage
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    storage.set_stock_status(s)
    return s


def test_pass_when_code_not_st(tmp_path):
    from storage.base import StockStatusRow
    from validation.handlers.ban_st import Handler
    s = _wire(tmp_path)
    s.upsert(StockStatusRow(code='600519.SH', name='贵州茅台',
                            is_st=False, is_suspended=False, is_delisted=False))
    assert Handler().check(_req('600519.SH')) is None


def test_reject_when_code_is_st(tmp_path):
    from storage.base import StockStatusRow
    from validation.handlers.ban_st import Handler
    s = _wire(tmp_path)
    s.upsert(StockStatusRow(code='000666.SZ', name='*ST 经纬',
                            is_st=True, is_suspended=False, is_delisted=False))
    v = Handler().check(_req('000666.SZ'))
    assert v is not None
    assert v.severity == 'reject'
    assert 'ST' in v.reason


def test_pass_when_toggle_false(tmp_path):
    from storage.base import StockStatusRow
    from validation.handlers.ban_st import Handler
    s = _wire(tmp_path)
    s.upsert(StockStatusRow(code='X.SH', name='*ST X',
                            is_st=True, is_suspended=False, is_delisted=False))
    assert Handler().check(_req('X.SH', ban=False)) is None


def test_pass_when_unknown_code(tmp_path):
    """No row → not flagged → trade allowed (fail-open on missing data)."""
    from validation.handlers.ban_st import Handler
    _wire(tmp_path)
    assert Handler().check(_req('NOTINDB.SH')) is None


def test_sell_is_allowed_even_on_st(tmp_path):
    """Spec: ban_st blocks new buys; selling existing holdings remains allowed."""
    from storage.base import StockStatusRow
    from validation.handlers.ban_st import Handler
    s = _wire(tmp_path)
    s.upsert(StockStatusRow(code='Y.SH', name='*ST Y',
                            is_st=True, is_suspended=False, is_delisted=False))
    assert Handler().check(_req('Y.SH', action='sell')) is None


def test_registered_on_import():
    from validation import rules
    import validation.handlers.ban_st  # noqa: F401
    assert rules.get('ban_st') is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_handler_ban_st.py -v`
Expected: 6 FAIL

- [ ] **Step 3: Implement**

```python
# validation/handlers/ban_st.py
"""Rejects buys on ST stocks when the toggle is on."""
from __future__ import annotations

from validation.base import ValidationRequest, Violation
from validation import rules as _rules


RULE_ID = 'ban_st'


class Handler:
    RULE_ID = RULE_ID

    def check(self, req: ValidationRequest) -> Violation | None:
        if not req.rules.get('ban_st'):
            return None
        action = (req.decision.get('action') or '').lower()
        if action != 'buy':
            return None
        code = req.decision.get('code')
        if not code:
            return None
        import storage
        if storage.stock_status().is_st(code):
            return Violation(
                rule_id=RULE_ID, severity='reject',
                reason=f'{code} is ST — ban_st toggle rejects buy',
            )
        return None


_rules.register(Handler())
```

Append to `validation/handlers/__init__.py`:

```python
from . import ban_st  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_handler_ban_st.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add validation/handlers/ tests/test_handler_ban_st.py
git commit -m "feat(p2b): handler ban_st — rejects buys on ST-flagged stocks"
```

---

## Task 11: Handler — max_holdings (reject new openings)

**Files:**
- Create: `validation/handlers/max_holdings.py`
- Modify: `validation/handlers/__init__.py`
- Test: `tests/test_handler_max_holdings.py`

**Rule:** If at-cap, reject buys that would **open a new position** (code not currently held). Adding to existing positions is allowed. Sells / non-buy pass.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_handler_max_holdings.py
"""max_holdings handler — reject opening a new position when at cap."""
from validation.base import ValidationRequest


def _req(code, action='buy', positions=None, max_holdings=3):
    return ValidationRequest(
        agent_id='a1',
        decision={'action': action, 'code': code, 'shares': 100, 'price': 10.0},
        portfolio={'equity': 1_000_000,
                   'positions': positions or {}},
        market_context={},
        rules={'max_holdings': max_holdings},
    )


def test_open_new_when_below_cap_passes():
    from validation.handlers.max_holdings import Handler
    req = _req('X.SH', positions={'A.SH': {'shares': 100},
                                  'B.SH': {'shares': 100}})
    assert Handler().check(req) is None


def test_open_new_when_at_cap_rejects():
    from validation.handlers.max_holdings import Handler
    req = _req('D.SH', positions={
        'A.SH': {'shares': 100},
        'B.SH': {'shares': 100},
        'C.SH': {'shares': 100},
    })
    v = Handler().check(req)
    assert v is not None
    assert v.severity == 'reject'


def test_add_to_existing_at_cap_is_allowed():
    """Same code → no new position opened → pass even at cap."""
    from validation.handlers.max_holdings import Handler
    req = _req('A.SH', positions={
        'A.SH': {'shares': 100},
        'B.SH': {'shares': 100},
        'C.SH': {'shares': 100},
    })
    assert Handler().check(req) is None


def test_zero_share_position_does_not_count():
    """A stub entry with shares=0 isn't a real position."""
    from validation.handlers.max_holdings import Handler
    req = _req('X.SH', positions={
        'A.SH': {'shares': 100},
        'B.SH': {'shares': 100},
        'C.SH': {'shares': 0},
    })
    assert Handler().check(req) is None


def test_sell_is_noop():
    from validation.handlers.max_holdings import Handler
    req = _req('D.SH', action='sell', positions={
        'A.SH': {'shares': 100}, 'B.SH': {'shares': 100},
        'C.SH': {'shares': 100},
    })
    assert Handler().check(req) is None


def test_no_rule_is_noop():
    from validation.handlers.max_holdings import Handler
    req = ValidationRequest(
        agent_id='a1',
        decision={'action': 'buy', 'code': 'X', 'shares': 1, 'price': 1.0},
        portfolio={'equity': 1, 'positions': {}}, market_context={}, rules={},
    )
    assert Handler().check(req) is None


def test_registered_on_import():
    from validation import rules
    import validation.handlers.max_holdings  # noqa: F401
    assert rules.get('max_holdings') is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_handler_max_holdings.py -v`
Expected: 7 FAIL

- [ ] **Step 3: Implement**

```python
# validation/handlers/max_holdings.py
"""Caps number of distinct positions (new-opening rejection only)."""
from __future__ import annotations

from validation.base import ValidationRequest, Violation
from validation import rules as _rules


RULE_ID = 'max_holdings'


def _active_codes(positions: dict) -> set:
    return {c for c, p in (positions or {}).items()
            if int(p.get('shares', 0) or 0) > 0}


class Handler:
    RULE_ID = RULE_ID

    def check(self, req: ValidationRequest) -> Violation | None:
        cap = req.rules.get('max_holdings')
        if cap is None:
            return None
        action = (req.decision.get('action') or '').lower()
        if action != 'buy':
            return None
        code = req.decision.get('code')
        active = _active_codes(req.portfolio.get('positions', {}))
        if code in active:
            return None  # adding to existing — fine
        if len(active) < cap:
            return None
        return Violation(
            rule_id=RULE_ID, severity='reject',
            reason=(f'already holding {len(active)} positions ≥ cap {cap}; '
                    f'cannot open new position in {code}'),
        )


_rules.register(Handler())
```

Append to `validation/handlers/__init__.py`:

```python
from . import max_holdings  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_handler_max_holdings.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add validation/handlers/ tests/test_handler_max_holdings.py
git commit -m "feat(p2b): handler max_holdings — reject new positions at cap"
```

---

## Task 12: Handler — daily_loss_limit_pct (circuit breaker)

**Files:**
- Create: `validation/handlers/daily_loss_limit_pct.py`
- Modify: `validation/handlers/__init__.py`
- Test: `tests/test_handler_daily_loss_limit_pct.py`

**Rule:** If `market_context['pnl_today_pct']` ≤ `-rules['daily_loss_limit_pct']`, reject *all* trades (both buy and sell) for the rest of the day. Spec § 7.1 calls this `daily_loss_max_pct`; handler looks for either key on the rule dict.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_handler_daily_loss_limit_pct.py
"""daily_loss_limit_pct / daily_loss_max_pct — circuit breaker."""
from validation.base import ValidationRequest


def _req(pnl_today_pct, *, action='buy', limit_pct=3.0, alt_key=False):
    key = 'daily_loss_max_pct' if alt_key else 'daily_loss_limit_pct'
    return ValidationRequest(
        agent_id='a1',
        decision={'action': action, 'code': 'X.SH', 'shares': 1, 'price': 1.0},
        portfolio={'equity': 1, 'positions': {}},
        market_context={'pnl_today_pct': pnl_today_pct},
        rules={key: limit_pct},
    )


def test_pass_when_pnl_above_limit():
    from validation.handlers.daily_loss_limit_pct import Handler
    assert Handler().check(_req(-1.5)) is None  # -1.5% > -3%


def test_reject_when_pnl_below_limit():
    from validation.handlers.daily_loss_limit_pct import Handler
    v = Handler().check(_req(-3.5))  # -3.5% ≤ -3%
    assert v is not None
    assert v.severity == 'reject'


def test_reject_at_exact_limit():
    """Inclusive: hitting -limit exactly trips the breaker."""
    from validation.handlers.daily_loss_limit_pct import Handler
    v = Handler().check(_req(-3.0))
    assert v is not None
    assert v.severity == 'reject'


def test_reject_sells_too():
    """Breaker blocks all trades, not just buys."""
    from validation.handlers.daily_loss_limit_pct import Handler
    v = Handler().check(_req(-5.0, action='sell'))
    assert v is not None
    assert v.severity == 'reject'


def test_positive_pnl_always_ok():
    from validation.handlers.daily_loss_limit_pct import Handler
    assert Handler().check(_req(2.5)) is None


def test_accepts_spec_key_daily_loss_max_pct():
    from validation.handlers.daily_loss_limit_pct import Handler
    v = Handler().check(_req(-4.0, limit_pct=3.0, alt_key=True))
    assert v is not None
    assert v.severity == 'reject'


def test_missing_pnl_in_context_passes():
    """Conservatively pass when pnl unknown — engine audit still records."""
    from validation.handlers.daily_loss_limit_pct import Handler
    req = ValidationRequest(
        agent_id='a1',
        decision={'action': 'buy', 'code': 'X', 'shares': 1, 'price': 1.0},
        portfolio={'equity': 1, 'positions': {}},
        market_context={}, rules={'daily_loss_limit_pct': 3.0},
    )
    assert Handler().check(req) is None


def test_registered_on_import():
    from validation import rules
    import validation.handlers.daily_loss_limit_pct  # noqa: F401
    assert rules.get('daily_loss_limit_pct') is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_handler_daily_loss_limit_pct.py -v`
Expected: 8 FAIL

- [ ] **Step 3: Implement**

```python
# validation/handlers/daily_loss_limit_pct.py
"""Circuit breaker: if today's PnL% ≤ -limit, reject all trades."""
from __future__ import annotations

from validation.base import ValidationRequest, Violation
from validation import rules as _rules


RULE_ID = 'daily_loss_limit_pct'


class Handler:
    RULE_ID = RULE_ID

    def check(self, req: ValidationRequest) -> Violation | None:
        # Accept either spec key: daily_loss_max_pct (RedLine) or daily_loss_limit_pct (persona)
        limit = req.rules.get('daily_loss_limit_pct')
        if limit is None:
            limit = req.rules.get('daily_loss_max_pct')
        if limit is None:
            return None
        pnl = req.market_context.get('pnl_today_pct')
        if pnl is None:
            return None
        if float(pnl) <= -float(limit):
            return Violation(
                rule_id=RULE_ID, severity='reject',
                reason=(f"today's PnL {pnl:.2f}% ≤ -{limit}%; "
                        f'daily loss circuit breaker tripped'),
            )
        return None


_rules.register(Handler())
```

Append to `validation/handlers/__init__.py`:

```python
from . import daily_loss_limit_pct  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_handler_daily_loss_limit_pct.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add validation/handlers/ tests/test_handler_daily_loss_limit_pct.py
git commit -m "feat(p2b): handler daily_loss_limit_pct — circuit breaker on PnL drop"
```

---

## Task 13: ValidationEngine — orchestrator + audit

**Files:**
- Create: `validation/engine.py`
- Test: `tests/test_validation_engine.py`

**Responsibilities:**
1. Build effective rules: `apply_override(redline_store.get(), override)`
2. For each rule in effective rules, look up handler in registry and call `check(req)`
3. Collect violations; any `reject` → outcome=rejected, decision_out=None
4. Else if any `modify` → merge modifications into a copy of decision → outcome=modified
5. Else → outcome=approved, decision_out=decision
6. Log an `AuditEntry(kind='validation', ...)` with outcome + violations + decision snapshot

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validation_engine.py
"""ValidationEngine orchestration + audit integration."""
import pytest


@pytest.fixture
def wired(tmp_path):
    """Set up stores + import handlers (side-effect registers)."""
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.sqlite_audit import SQLiteAuditStore
    from validation.base import DEFAULT_REDLINES

    rl = SQLiteRedLineStore(tmp_path=tmp_path); rl.init_schema()
    ss = SQLiteStockStatusStore(tmp_path=tmp_path); ss.init_schema()
    au = SQLiteAuditStore(tmp_path=tmp_path); au.init_schema()
    storage.set_redline(rl)
    storage.set_stock_status(ss)
    storage.set_audit(au)

    # Ensure every handler registers itself
    from validation import rules
    rules.reset()
    import validation.handlers  # noqa: F401

    rl.set({**DEFAULT_REDLINES, 'position_max_pct': 15.0, 'ban_st': True})
    return {'redline': rl, 'stock_status': ss, 'audit': au}


def _portfolio(positions=None, equity=1_000_000, cash=1_000_000):
    return {'equity': equity, 'cash': cash, 'positions': positions or {}}


def _req(decision, portfolio=None, market_context=None, override=None):
    from validation.engine import ValidationEngine
    return ValidationEngine().validate(
        agent_id='a1',
        decision=decision,
        portfolio=portfolio or _portfolio(),
        market_context=market_context or {},
        rules_override=override or {},
    )


def test_approved_path(wired):
    out = _req(decision={'action': 'buy', 'code': 'X.SH',
                         'shares': 100, 'price': 10.0})  # 100*10=1000 = 0.1% ≤ 15%
    assert out.outcome == 'approved'
    assert out.decision_out == {'action': 'buy', 'code': 'X.SH',
                                'shares': 100, 'price': 10.0}
    assert out.violations == ()


def test_rejected_on_redline_ban_st(wired):
    from storage.base import StockStatusRow
    wired['stock_status'].upsert(StockStatusRow(
        code='ST.SH', name='*ST X', is_st=True,
        is_suspended=False, is_delisted=False,
    ))
    out = _req(decision={'action': 'buy', 'code': 'ST.SH',
                         'shares': 100, 'price': 10.0})
    assert out.outcome == 'rejected'
    assert out.decision_out is None
    assert any(v.rule_id == 'ban_st' for v in out.violations)


def test_modified_on_position_max_pct(wired):
    # 200 shares @ 1000 = 200,000 on 1M equity = 20% > 15% cap → shrink to 150
    out = _req(decision={'action': 'buy', 'code': 'X.SH',
                         'shares': 200, 'price': 1000.0})
    assert out.outcome == 'modified'
    assert out.decision_out['shares'] == 150
    assert any(v.rule_id == 'position_max_pct' and v.severity == 'modify'
               for v in out.violations)


def test_reject_wins_over_modify(wired):
    """If any handler rejects, modifications are discarded."""
    from storage.base import StockStatusRow
    wired['stock_status'].upsert(StockStatusRow(
        code='ST.SH', name='*ST X', is_st=True,
        is_suspended=False, is_delisted=False,
    ))
    out = _req(decision={'action': 'buy', 'code': 'ST.SH',
                         'shares': 200, 'price': 1000.0})
    assert out.outcome == 'rejected'
    assert out.decision_out is None


def test_audit_row_written_on_approve(wired):
    import storage
    _req(decision={'action': 'buy', 'code': 'X.SH',
                   'shares': 10, 'price': 10.0})
    rows = storage.audit().query_by_agent('a1')
    assert len(rows) == 1
    assert rows[0]['kind'] == 'validation'
    assert rows[0]['details']['outcome'] == 'approved'


def test_audit_row_captures_violations(wired):
    import storage
    _req(decision={'action': 'buy', 'code': 'X.SH',
                   'shares': 200, 'price': 1000.0})
    row = storage.audit().query_by_agent('a1')[0]
    assert row['details']['outcome'] == 'modified'
    v_ids = [v['rule_id'] for v in row['details']['violations']]
    assert 'position_max_pct' in v_ids


def test_override_narrows_rule(wired):
    # Override to 5%: 100 shares @ 1000 = 100k on 1M equity = 10% > 5%
    out = _req(
        decision={'action': 'buy', 'code': 'X.SH',
                  'shares': 100, 'price': 1000.0},
        override={'position_max_pct': 5.0},
    )
    assert out.outcome == 'modified'
    assert out.decision_out['shares'] == 50


def test_override_cannot_widen(wired):
    """RedLine is 15; override 40 must be clamped to 15."""
    out = _req(
        decision={'action': 'buy', 'code': 'X.SH',
                  'shares': 200, 'price': 1000.0},
        override={'position_max_pct': 40.0},
    )
    # Clamped to 15% → still shrinks to 150
    assert out.outcome == 'modified'
    assert out.decision_out['shares'] == 150
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validation_engine.py -v`
Expected: 8 FAIL

- [ ] **Step 3: Implement**

```python
# validation/engine.py
"""ValidationEngine — orchestrate RedLine + override + handlers + audit."""
from __future__ import annotations

from dataclasses import asdict

from .base import (
    AuditEntry, ValidationRequest, ValidationResult, Violation,
    apply_override,
)
from . import rules as _rules


class ValidationEngine:
    def validate(
        self,
        *,
        agent_id: str,
        decision: dict,
        portfolio: dict,
        market_context: dict,
        rules_override: dict | None = None,
        persona_id: str | None = None,
        model_id: str | None = None,
    ) -> ValidationResult:
        import storage
        redline = storage.redline().get()
        effective = apply_override(redline, rules_override)

        req = ValidationRequest(
            agent_id=agent_id, decision=dict(decision),
            portfolio=portfolio, market_context=market_context,
            rules=effective, persona_id=persona_id, model_id=model_id,
        )

        violations: list[Violation] = []
        for rule_id in effective:
            handler = _rules.get(rule_id)
            if handler is None:
                continue
            v = handler.check(req)
            if v is not None:
                violations.append(v)

        if any(v.severity == 'reject' for v in violations):
            outcome = 'rejected'
            decision_out = None
        elif any(v.severity == 'modify' for v in violations):
            outcome = 'modified'
            decision_out = dict(decision)
            for v in violations:
                if v.severity == 'modify' and v.modification:
                    decision_out.update(v.modification)
        else:
            outcome = 'approved'
            decision_out = dict(decision)

        # Audit — always written, regardless of outcome
        storage.audit().log(AuditEntry(
            kind='validation',
            agent_id=agent_id,
            persona_id=persona_id,
            model_id=model_id,
            details={
                'outcome': outcome,
                'decision_in': dict(decision),
                'decision_out': decision_out,
                'violations': [asdict(v) for v in violations],
                'effective_rules': effective,
            },
        ))

        return ValidationResult(
            outcome=outcome,
            decision_out=decision_out,
            violations=tuple(violations),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validation_engine.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add validation/engine.py tests/test_validation_engine.py
git commit -m "feat(p2b): ValidationEngine — RedLine+override+handlers+audit"
```

---

## Task 14: Post-backtest quality gate (soft labels)

**Files:**
- Create: `validation/quality_gate.py`
- Test: `tests/test_validation_quality_gate.py`

**Input:** `stats` dict with keys matching `DEFAULT_QUALITY_GATE` criteria (sharpe, max_drawdown_pct, trade_count, win_rate, max_daily_loss_pct, clean_zone_days, divergence_flag). `thresholds` arg defaults to `DEFAULT_QUALITY_GATE`, overridable per-persona.

**Output:** `QualityGateResult(label, criteria)` where:
- `label = 'fail'` if any criterion violated
- `label = 'warn'` if all pass but clean_zone_days within 1.5× of min (borderline)
- `label = 'pass'` otherwise

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validation_quality_gate.py
"""Post-backtest quality gate — soft-label pass/warn/fail."""


def _stats(**overrides):
    base = {
        'sharpe':              1.2,
        'max_drawdown_pct':   -12.0,
        'trade_count':         30,
        'win_rate':            55.0,
        'max_daily_loss_pct': -2.5,
        'clean_zone_days':     120,
        'divergence_flag':     False,
    }
    base.update(overrides)
    return base


def test_all_green_is_pass():
    from validation.quality_gate import evaluate_quality_gate
    r = evaluate_quality_gate(_stats())
    assert r.label == 'pass'
    assert all(c['ok'] for c in r.criteria.values())


def test_low_sharpe_fails():
    from validation.quality_gate import evaluate_quality_gate
    r = evaluate_quality_gate(_stats(sharpe=0.1))
    assert r.label == 'fail'
    assert r.criteria['min_sharpe']['ok'] is False


def test_drawdown_too_deep_fails():
    from validation.quality_gate import evaluate_quality_gate
    r = evaluate_quality_gate(_stats(max_drawdown_pct=-30.0))
    assert r.label == 'fail'


def test_too_few_trades_fails():
    from validation.quality_gate import evaluate_quality_gate
    r = evaluate_quality_gate(_stats(trade_count=3))
    assert r.label == 'fail'


def test_divergence_flag_fails():
    from validation.quality_gate import evaluate_quality_gate
    r = evaluate_quality_gate(_stats(divergence_flag=True))
    assert r.label == 'fail'


def test_borderline_clean_zone_is_warn():
    from validation.quality_gate import evaluate_quality_gate
    # clean_zone_days=70 >= 60 min but < 60*1.5=90 threshold
    r = evaluate_quality_gate(_stats(clean_zone_days=70))
    assert r.label == 'warn'


def test_custom_thresholds_override_defaults():
    from validation.quality_gate import evaluate_quality_gate
    strict = {'min_sharpe': 2.0}
    r = evaluate_quality_gate(_stats(sharpe=1.5), thresholds=strict)
    assert r.label == 'fail'
    # Only the overridden criterion evaluated
    assert 'min_sharpe' in r.criteria


def test_missing_stats_key_records_fail_on_that_criterion():
    from validation.quality_gate import evaluate_quality_gate
    stats = _stats()
    del stats['sharpe']
    r = evaluate_quality_gate(stats)
    assert r.label == 'fail'
    assert r.criteria['min_sharpe']['ok'] is False
    assert 'missing' in r.criteria['min_sharpe']['reason']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validation_quality_gate.py -v`
Expected: 8 FAIL

- [ ] **Step 3: Implement**

```python
# validation/quality_gate.py
"""Post-backtest quality gate — soft labels based on DEFAULT_QUALITY_GATE."""
from __future__ import annotations

from .base import DEFAULT_QUALITY_GATE, QualityGateResult


# (threshold_key, stats_key, direction)
# direction = 'ge' : stats_value must be >= threshold
#             'le' : stats_value must be <= threshold (threshold is negative)
#             'eq_false' : stats_value must equal the threshold (for divergence_flag: False means ok)
_CRITERIA = [
    ('min_sharpe',           'sharpe',              'ge'),
    ('max_drawdown_pct',     'max_drawdown_pct',    'ge'),   # -12 >= -25 ✓
    ('min_trade_count',      'trade_count',         'ge'),
    ('min_win_rate',         'win_rate',            'ge'),
    ('max_daily_loss_pct',   'max_daily_loss_pct',  'ge'),   # -2.5 >= -5 ✓
    ('min_clean_zone_days',  'clean_zone_days',     'ge'),
    ('max_divergence_flag',  'divergence_flag',     'eq_false'),
]


_WARN_BORDER_MULT = 1.5  # e.g., clean_zone_days < min*1.5 → warn


def evaluate_quality_gate(
    stats: dict, thresholds: dict | None = None,
) -> QualityGateResult:
    t = dict(DEFAULT_QUALITY_GATE)
    if thresholds:
        t.update(thresholds)

    criteria = {}
    any_fail = False
    any_borderline = False

    for thresh_key, stat_key, direction in _CRITERIA:
        if thresh_key not in t:
            continue
        threshold = t[thresh_key]
        actual = stats.get(stat_key)
        if actual is None:
            criteria[thresh_key] = {
                'ok': False, 'actual': None, 'threshold': threshold,
                'reason': f'missing stats[{stat_key!r}]',
            }
            any_fail = True
            continue

        if direction == 'ge':
            ok = actual >= threshold
            if ok and thresh_key == 'min_clean_zone_days':
                # Borderline: between min and min*1.5
                if actual < threshold * _WARN_BORDER_MULT:
                    any_borderline = True
        elif direction == 'le':
            ok = actual <= threshold
        elif direction == 'eq_false':
            ok = bool(actual) == bool(threshold)
        else:
            ok = False

        criteria[thresh_key] = {
            'ok': ok, 'actual': actual, 'threshold': threshold,
            'reason': '' if ok else f'{stat_key}={actual} fails vs {threshold}',
        }
        if not ok:
            any_fail = True

    if any_fail:
        label = 'fail'
    elif any_borderline:
        label = 'warn'
    else:
        label = 'pass'
    return QualityGateResult(label=label, criteria=criteria)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validation_quality_gate.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add validation/quality_gate.py tests/test_validation_quality_gate.py
git commit -m "feat(p2b): post-backtest quality gate — soft labels (pass/warn/fail)"
```

---

## Task 15: Daily stock_status refresh script

**Files:**
- Create: `scripts/setup/refresh_stock_status.py`
- Test: `tests/test_refresh_stock_status.py`

**Responsibility:** pull TDX snapshots for the HS300 pool, parse ST prefix from the name field, upsert into `stock_status`. Runnable as `python -m scripts.setup.refresh_stock_status`. Unit test mocks `tdx` so it runs offline.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_refresh_stock_status.py
"""Daily stock_status refresh pulls from TDX snapshot and upserts."""


def test_parse_st_from_name():
    from scripts.setup.refresh_stock_status import _is_st_name
    assert _is_st_name('*ST 经纬') is True
    assert _is_st_name('ST 金贵') is True
    assert _is_st_name('S*ST 金泰') is True
    assert _is_st_name('贵州茅台') is False
    assert _is_st_name('') is False
    assert _is_st_name(None) is False


def test_refresh_upserts_via_store(tmp_path, monkeypatch):
    """Verify the end-to-end flow with a mocked TDX snapshot."""
    import storage
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    storage.set_stock_status(s)

    # Mock codes + snapshot
    fake_codes = ['600519.SH', '000666.SZ', '000001.SZ']
    fake_snapshot = {
        '600519.SH': {'name': '贵州茅台', 'suspended': False},
        '000666.SZ': {'name': '*ST 经纬', 'suspended': False},
        '000001.SZ': {'name': '平安银行', 'suspended': True},
    }

    from scripts.setup import refresh_stock_status as mod
    monkeypatch.setattr(mod, '_load_pool_codes', lambda: fake_codes)
    monkeypatch.setattr(mod, '_fetch_snapshot', lambda codes: fake_snapshot)

    n = mod.run()
    assert n == 3
    assert s.is_st('600519.SH') is False
    assert s.is_st('000666.SZ') is True
    assert s.is_suspended('000001.SZ') is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_refresh_stock_status.py -v`
Expected: 2 FAIL (`ModuleNotFoundError: scripts.setup.refresh_stock_status`)

- [ ] **Step 3: Implement**

```python
# scripts/setup/refresh_stock_status.py
"""Refresh stock_status table from TDX snapshot.

Usage: python -m scripts.setup.refresh_stock_status
"""
from __future__ import annotations

import storage
from storage.base import StockStatusRow


# Pool to refresh daily — HS300 for MVP. Personas restrict to subset of this.
_HS300_MARKET = '23'


def _is_st_name(name: str | None) -> bool:
    """Detect ST / *ST / S*ST prefix in stock name."""
    if not name:
        return False
    n = name.strip().upper().replace(' ', '')
    return n.startswith('ST') or n.startswith('*ST') or n.startswith('S*ST')


def _load_pool_codes() -> list[str]:
    """HS300 codes from TDX. Returns list of codes like '600519.SH'."""
    from tdx_service import tdx
    if not tdx.initialize() or not tdx.is_connected():
        raise RuntimeError('TDX not connected — launch 通达信 and press F12')
    lst = tdx.get_stock_list(market=_HS300_MARKET)  # returns list[dict]
    codes: list[str] = []
    for item in lst:
        code = item.get('code') or item.get('stock_code')
        if code and '.' in code:
            codes.append(code)
    return codes


def _fetch_snapshot(codes: list[str]) -> dict[str, dict]:
    """Batched snapshot keyed by code. Each value has name + suspended flag."""
    from tdx_service import tdx
    raw = tdx.get_market_snapshot(codes)
    out: dict[str, dict] = {}
    for row in raw:
        code = row.get('code') or row.get('stock_code')
        if not code:
            continue
        out[code] = {
            'name': row.get('name') or row.get('stock_name'),
            'suspended': bool(row.get('suspended', False)),
        }
    return out


def run() -> int:
    """Return count of rows written."""
    codes = _load_pool_codes()
    snap = _fetch_snapshot(codes)
    rows = [
        StockStatusRow(
            code=code,
            name=info.get('name'),
            is_st=_is_st_name(info.get('name')),
            is_suspended=bool(info.get('suspended', False)),
            is_delisted=False,
        )
        for code, info in snap.items()
    ]
    return storage.stock_status().bulk_upsert(rows)


if __name__ == '__main__':
    n = run()
    print(f'refreshed stock_status: {n} rows')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_refresh_stock_status.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/setup/refresh_stock_status.py tests/test_refresh_stock_status.py
git commit -m "feat(p2b): scripts/setup/refresh_stock_status — daily TDX snapshot ingest"
```

---

## Post-plan verification

Run the full suite once after the last task:

```bash
pytest -q
```

Expected: all tests green, count increases by ~65 cases over P2a (149 → ~214+).

Review the new files against Spec § 7 once more:
- `validation/base.py` exposes `DEFAULT_REDLINES`, `DEFAULT_QUALITY_GATE`, `apply_override`
- `validation/engine.py` orchestrates the full flow and writes audit rows
- `validation/handlers/` has 4 MVP rules, all auto-registered on import
- `storage/{sqlite_redline,sqlite_stock_status,sqlite_audit}.py` back the three new tables
- `scripts/setup/refresh_stock_status.py` is the daily job

Not in P2b scope (future plans):
- **P2c**: `LLMStrategy` vnpy integration + full E2E backtest → invokes `ValidationEngine.validate()` per decision and calls `evaluate_quality_gate` on backtest stats
- **P2d**: baselines, cross-cutoff knowledge-leakage metrics, rating
- **P2e**: `/api/redline` + `/api/redline` PUT (writes `redline_changed` audit), Server-Sent Events for live `validation` events, RiskMonitor UI
