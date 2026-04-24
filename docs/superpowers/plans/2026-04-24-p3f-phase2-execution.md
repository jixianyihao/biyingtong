# P3-F Phase 2 — approve → TDX place_order 真单通路

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
>
> **⚠⚠ 用户 2026-04-24 明确同意真金险 Phase 2 上线，但要求：默认 dry-run、toggle + 二次确认 UI 才走真 TDX。本 plan 严格遵守。**

**Goal:** 把 `POST /api/proposals/:id/approve` 从纯 DB 状态变更接入真实订单执行路径。真实路径走 vnpy-friendly 的 `ExecutionAdapter` 抽象，默认 `dry_run` adapter（不发真单），通过 env var 切到 `live` adapter（走 `tdx_service.place_order`）。

**Architecture:**
- `execution/adapter.py` — `ExecutionAdapter` Protocol + `ExecutionResult` dataclass
- `execution/mock.py` — `MockExecutionAdapter` 永远成功，filled_qty=shares，生成假 order_id
- `execution/tdx.py` — `TDXExecutionAdapter` 包 `tdx_service.place_order`，转 proposal → 订单参数
- `execution/__init__.py` — `get_adapter()` 工厂，读 env var `BIYINGTONG_EXECUTION_MODE` (默认 `dry_run`)
- approve 端点：status → 'approved'；调 adapter.place_order；把结果写回 DB 新字段；返回 proposal + execution 信息
- schema 加列（trade_proposals）：`execution_mode`、`execution_order_id`、`execution_error`、`executed_at`、`filled_qty`、`filled_price`
- UI：TopBar 加 execution-mode badge（dry-run 灰色 / LIVE 红色）；approve 在 live 模式下弹 2 步确认 Modal（输入 "确认" 字符串才能真 approve）

**Tech Stack:** Python 3.10 / Flask / SQLite / React 19 / TypeScript / tqcenter (TDX SDK)

---

## File Structure

**Backend (new):**
- `execution/__init__.py` — `get_adapter()` factory + public exports
- `execution/adapter.py` — `ExecutionAdapter` Protocol + `ExecutionResult` dataclass
- `execution/mock.py` — `MockExecutionAdapter`
- `execution/tdx.py` — `TDXExecutionAdapter`
- `tests/test_execution_adapter.py` — Protocol + both impls
- `tests/test_api_proposals_phase2.py` — approve endpoint in dry_run vs live

**Backend (modify):**
- `data_schema/deployment_state.py` — extend `trade_proposals` schema (add 6 columns)
- `storage/base.py` — `TradeProposal` dataclass adds 6 execution fields; `TradeProposalStore` Protocol gains `update_execution()`
- `storage/sqlite_proposals.py` — ALTER TABLE (if table exists) + update_execution impl
- `api/proposals.py` — `approve_proposal` calls adapter, persists execution result
- `api/execution.py` (new) — `GET /api/execution/mode` reports current adapter mode

**Frontend (new):**
- `frontend/src/components/LiveApproveModal.tsx` — 2-step confirmation modal
- `frontend/src/components/ExecutionModeBadge.tsx` — header badge

**Frontend (modify):**
- `frontend/src/api/hooks.ts` — `useExecutionMode()` hook
- `frontend/src/api/types.ts` — `ExecutionMode`, `ExecutionResult`, updated `TradeProposal`
- `frontend/src/api/client.ts` — `getExecutionMode()` + updated approve mutation
- `frontend/src/components/ProposalsPanel.tsx` — branch UI on mode; show execution result after approve
- `frontend/src/components/TopBar.tsx` — mount `<ExecutionModeBadge />`

**Not touched:**
- `tdx_service.place_order` — existing method, no change
- Rule/LLM backtest paths — orthogonal
- Phase 1 proposal creation / deploy infrastructure — unchanged

---

### Task 1: ExecutionAdapter Protocol + ExecutionResult dataclass

**Files:**
- Create: `execution/__init__.py` (factory shell only, body in Task 4)
- Create: `execution/adapter.py`
- Test: `tests/test_execution_adapter.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_execution_adapter.py
from execution.adapter import ExecutionAdapter, ExecutionResult


def test_execution_result_dataclass_shape():
    r = ExecutionResult(
        success=True, mode='dry_run', order_id='mock-123',
        filled_qty=100, filled_price=237.5,
        error=None, executed_at='2026-04-24T10:00:00',
    )
    assert r.success is True
    assert r.mode == 'dry_run'
    assert r.order_id == 'mock-123'
    assert r.filled_qty == 100
    assert r.filled_price == 237.5
    assert r.error is None


def test_execution_adapter_protocol_runtime_checkable():
    from typing import runtime_checkable

    class Compliant:
        def place_order(self, proposal):  # noqa: ANN001
            return ExecutionResult(
                success=True, mode='dry_run', order_id='x',
                filled_qty=0, filled_price=0.0, error=None,
                executed_at=None,
            )

        @property
        def mode(self) -> str:
            return 'dry_run'

    assert isinstance(Compliant(), ExecutionAdapter)
```

Run: `pytest tests/test_execution_adapter.py -v`
Expected: FAIL (module doesn't exist).

- [ ] **Step 2: Implement adapter.py**

```python
# execution/adapter.py
"""ExecutionAdapter Protocol + shared ExecutionResult.

The Protocol isolates the approve endpoint from the concrete execution
backend (Mock for tests/dry-run, TDX for live). No code outside this
module should import `tdx_service.place_order` directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ExecutionResult:
    success: bool
    mode: str              # 'dry_run' or 'live'
    order_id: str | None   # TDX order id, or mock id
    filled_qty: int
    filled_price: float
    error: str | None      # human-readable error, None on success
    executed_at: str | None  # ISO timestamp


@runtime_checkable
class ExecutionAdapter(Protocol):
    @property
    def mode(self) -> str: ...
    def place_order(self, proposal) -> ExecutionResult: ...  # noqa: ANN001
```

And minimal shell:

```python
# execution/__init__.py
"""Execution adapters — abstraction over order submission.

Default mode: dry_run (MockExecutionAdapter). Set BIYINGTONG_EXECUTION_MODE=live
to engage TDXExecutionAdapter. See plan 2026-04-24-p3f-phase2-execution.md.
"""
from .adapter import ExecutionAdapter, ExecutionResult

__all__ = ['ExecutionAdapter', 'ExecutionResult', 'get_adapter']


def get_adapter():
    """Factory — populated in Task 4."""
    raise NotImplementedError('populated in Task 4')
```

- [ ] **Step 3: Verify green**

Run: `pytest tests/test_execution_adapter.py -v`
Expected: PASS (2/2).

- [ ] **Step 4: Commit**

```bash
git add execution/__init__.py execution/adapter.py tests/test_execution_adapter.py
git commit -m "feat(execution): ExecutionAdapter Protocol + ExecutionResult dataclass"
```

---

### Task 2: MockExecutionAdapter

**Files:**
- Create: `execution/mock.py`
- Test: extend `tests/test_execution_adapter.py`

- [ ] **Step 1: Failing test**

Append to `tests/test_execution_adapter.py`:

```python
def _make_proposal(action='buy', code='600519.SH', shares=100, price=237.5):
    from storage.base import TradeProposal
    return TradeProposal(
        id='prop-1', agent_id='agent-1',
        created_at=None, decision_at='2026-04-24T09:30:00',
        action=action, code=code, shares=shares, price=price,
        reason='test', thinking='t', status='pending',
        decided_by=None, decided_at=None,
    )


def test_mock_adapter_always_succeeds():
    from execution.mock import MockExecutionAdapter
    adapter = MockExecutionAdapter()
    assert adapter.mode == 'dry_run'
    r = adapter.place_order(_make_proposal())
    assert r.success is True
    assert r.mode == 'dry_run'
    assert r.order_id is not None and r.order_id.startswith('mock-')
    assert r.filled_qty == 100
    assert r.filled_price == 237.5
    assert r.error is None
    assert r.executed_at is not None
```

Run → RED.

- [ ] **Step 2: Implement**

```python
# execution/mock.py
"""MockExecutionAdapter — dry-run path, never talks to TDX.

Fills as requested (filled_qty == proposal.shares, filled_price == proposal.price).
Generates a UUID-based mock order id so DB rows can carry the value through.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from .adapter import ExecutionAdapter, ExecutionResult


class MockExecutionAdapter(ExecutionAdapter):
    @property
    def mode(self) -> str:
        return 'dry_run'

    def place_order(self, proposal) -> ExecutionResult:  # noqa: ANN001
        shares = int(proposal.shares or 0)
        price = float(proposal.price or 0.0)
        return ExecutionResult(
            success=True, mode='dry_run',
            order_id=f'mock-{uuid.uuid4().hex[:12]}',
            filled_qty=shares, filled_price=price,
            error=None,
            executed_at=datetime.utcnow().isoformat(timespec='seconds'),
        )
```

- [ ] **Step 3: Verify + commit**

```bash
pytest tests/test_execution_adapter.py -v  # 3/3
git add execution/mock.py tests/test_execution_adapter.py
git commit -m "feat(execution): MockExecutionAdapter (dry-run path)"
```

---

### Task 3: TDXExecutionAdapter

**Files:**
- Create: `execution/tdx.py`
- Test: extend `tests/test_execution_adapter.py`

- [ ] **Step 1: Failing tests (use monkeypatch — never hit real TDX)**

Append:

```python
def test_tdx_adapter_maps_buy_to_tdx_place_order(monkeypatch):
    from execution.tdx import TDXExecutionAdapter
    import tdx_service

    captured = {}
    def fake_place(stock_code, side, qty, price, price_type=0):
        captured.update({'stock_code': stock_code, 'side': side,
                         'qty': qty, 'price': price})
        return {'order_id': 'tdx-12345'}
    monkeypatch.setattr(tdx_service.tdx, 'place_order', fake_place)

    adapter = TDXExecutionAdapter()
    assert adapter.mode == 'live'
    r = adapter.place_order(_make_proposal(action='buy', code='600519.SH',
                                            shares=100, price=237.5))
    assert captured == {'stock_code': '600519.SH', 'side': 'buy',
                        'qty': 100, 'price': 237.5}
    assert r.success is True
    assert r.mode == 'live'
    assert r.order_id == 'tdx-12345'


def test_tdx_adapter_handles_error_response(monkeypatch):
    from execution.tdx import TDXExecutionAdapter
    import tdx_service
    monkeypatch.setattr(tdx_service.tdx, 'place_order',
                        lambda *a, **kw: {'error': 'insufficient funds'})
    adapter = TDXExecutionAdapter()
    r = adapter.place_order(_make_proposal())
    assert r.success is False
    assert r.mode == 'live'
    assert r.error == 'insufficient funds'
    assert r.filled_qty == 0


def test_tdx_adapter_rejects_sell_action_with_zero_shares(monkeypatch):
    from execution.tdx import TDXExecutionAdapter
    calls = []
    import tdx_service
    monkeypatch.setattr(tdx_service.tdx, 'place_order',
                        lambda *a, **kw: calls.append((a, kw)) or {'order_id': 'x'})
    adapter = TDXExecutionAdapter()
    # shares=0 should be short-circuited without hitting TDX
    r = adapter.place_order(_make_proposal(action='buy', shares=0, price=237.5))
    assert r.success is False
    assert r.error and 'shares' in r.error.lower()
    assert calls == []
```

Run → RED.

- [ ] **Step 2: Implement**

```python
# execution/tdx.py
"""TDXExecutionAdapter — live order execution via tdx_service.place_order.

This is the one place where `tdx_service.place_order` should be called
from. All call-sites go through get_adapter() in __init__.py and thus
through BIYINGTONG_EXECUTION_MODE. Accidentally swapping in this adapter
is the only way real money moves.
"""
from __future__ import annotations

from datetime import datetime

from .adapter import ExecutionAdapter, ExecutionResult


class TDXExecutionAdapter(ExecutionAdapter):
    @property
    def mode(self) -> str:
        return 'live'

    def place_order(self, proposal) -> ExecutionResult:  # noqa: ANN001
        shares = int(proposal.shares or 0)
        price = float(proposal.price or 0.0)
        action = (proposal.action or '').lower()
        code = proposal.code or ''
        ts = datetime.utcnow().isoformat(timespec='seconds')

        if shares <= 0:
            return ExecutionResult(
                success=False, mode='live', order_id=None,
                filled_qty=0, filled_price=0.0,
                error='shares must be > 0',
                executed_at=ts,
            )
        if action not in ('buy', 'sell'):
            return ExecutionResult(
                success=False, mode='live', order_id=None,
                filled_qty=0, filled_price=0.0,
                error=f'unsupported action: {action!r}',
                executed_at=ts,
            )
        if not code:
            return ExecutionResult(
                success=False, mode='live', order_id=None,
                filled_qty=0, filled_price=0.0,
                error='code is required',
                executed_at=ts,
            )

        from tdx_service import tdx
        try:
            result = tdx.place_order(
                stock_code=code, side=action,
                qty=shares, price=price,
            )
        except Exception as e:  # noqa: BLE001
            return ExecutionResult(
                success=False, mode='live', order_id=None,
                filled_qty=0, filled_price=0.0,
                error=f'{type(e).__name__}: {e}',
                executed_at=ts,
            )

        if isinstance(result, dict) and result.get('error'):
            return ExecutionResult(
                success=False, mode='live', order_id=None,
                filled_qty=0, filled_price=0.0,
                error=str(result.get('error')),
                executed_at=ts,
            )
        order_id = None
        if isinstance(result, dict):
            order_id = str(result.get('order_id')
                           or result.get('id')
                           or result.get('orderId') or '') or None
        elif result not in (None, -1):
            order_id = str(result)
        # If TDX doesn't return fill details synchronously, we record
        # filled_qty=shares optimistically so the UI can show "submitted".
        # Real fill status comes from subsequent order-status polling.
        return ExecutionResult(
            success=True, mode='live', order_id=order_id,
            filled_qty=shares, filled_price=price,
            error=None, executed_at=ts,
        )
```

- [ ] **Step 3: Verify + commit**

```bash
pytest tests/test_execution_adapter.py -v  # 6/6
git add execution/tdx.py tests/test_execution_adapter.py
git commit -m "feat(execution): TDXExecutionAdapter (live path via tdx_service.place_order)"
```

---

### Task 4: get_adapter() factory + mode toggle

**Files:** `execution/__init__.py`

- [ ] **Step 1: Failing test**

Append to `tests/test_execution_adapter.py`:

```python
def test_get_adapter_default_is_dry_run(monkeypatch):
    monkeypatch.delenv('BIYINGTONG_EXECUTION_MODE', raising=False)
    import importlib
    import execution
    importlib.reload(execution)
    adapter = execution.get_adapter()
    assert adapter.mode == 'dry_run'


def test_get_adapter_live_when_env_set(monkeypatch):
    monkeypatch.setenv('BIYINGTONG_EXECUTION_MODE', 'live')
    import importlib
    import execution
    importlib.reload(execution)
    adapter = execution.get_adapter()
    assert adapter.mode == 'live'


def test_get_adapter_explicit_dry_run(monkeypatch):
    monkeypatch.setenv('BIYINGTONG_EXECUTION_MODE', 'dry_run')
    import importlib
    import execution
    importlib.reload(execution)
    adapter = execution.get_adapter()
    assert adapter.mode == 'dry_run'


def test_get_adapter_unknown_mode_falls_back_to_dry_run_with_warning(monkeypatch, capsys):
    monkeypatch.setenv('BIYINGTONG_EXECUTION_MODE', 'prod-yolo')
    import importlib
    import execution
    importlib.reload(execution)
    adapter = execution.get_adapter()
    assert adapter.mode == 'dry_run'  # safe fallback — never silently go live on typo
    captured = capsys.readouterr()
    assert 'prod-yolo' in captured.out or 'prod-yolo' in captured.err
```

Run → RED (factory raises NotImplementedError).

- [ ] **Step 2: Implement**

```python
# execution/__init__.py (full content)
"""Execution adapters — abstraction over order submission.

Default mode: dry_run (MockExecutionAdapter). Set BIYINGTONG_EXECUTION_MODE=live
to engage TDXExecutionAdapter. See plan 2026-04-24-p3f-phase2-execution.md.
"""
from __future__ import annotations

import os

from .adapter import ExecutionAdapter, ExecutionResult
from .mock import MockExecutionAdapter
from .tdx import TDXExecutionAdapter

__all__ = [
    'ExecutionAdapter', 'ExecutionResult',
    'MockExecutionAdapter', 'TDXExecutionAdapter',
    'get_adapter',
]


_VALID_MODES = ('dry_run', 'live')


def get_adapter() -> ExecutionAdapter:
    """Factory reading BIYINGTONG_EXECUTION_MODE.

    Safe fallback: unknown / unset / empty values resolve to dry_run.
    Typos MUST NOT silently escalate to live execution.
    """
    raw = (os.environ.get('BIYINGTONG_EXECUTION_MODE') or 'dry_run').strip().lower()
    if raw not in _VALID_MODES:
        print(f'[execution] WARNING: unknown BIYINGTONG_EXECUTION_MODE={raw!r}; '
              f'falling back to dry_run')
        return MockExecutionAdapter()
    if raw == 'live':
        return TDXExecutionAdapter()
    return MockExecutionAdapter()
```

- [ ] **Step 3: Verify + commit**

```bash
pytest tests/test_execution_adapter.py -v  # 10/10
git add execution/__init__.py
git commit -m "feat(execution): get_adapter() factory + env-var mode toggle (default dry_run)"
```

---

### Task 5: Schema migration — extend trade_proposals

**Files:**
- Modify: `data_schema/deployment_state.py`
- Modify: `storage/base.py` (TradeProposal dataclass adds fields; TradeProposalStore.update_execution Protocol method)
- Modify: `storage/sqlite_proposals.py` (impl + ALTER TABLE)
- Test: new `tests/test_storage_proposals_execution.py`

- [ ] **Step 1: Extend TradeProposal dataclass**

In `storage/base.py`, find the `@dataclass` for `TradeProposal`. Add 6 fields AT THE END with defaults (so old call-sites still work):

```python
@dataclass
class TradeProposal:
    id: str
    agent_id: str
    created_at: str | None
    decision_at: str
    action: str
    code: str | None
    shares: int | None
    price: float | None
    reason: str | None
    thinking: str | None
    status: str
    decided_by: str | None = None
    decided_at: str | None = None
    # Phase 2 execution fields
    execution_mode: str | None = None      # 'dry_run' | 'live'
    execution_order_id: str | None = None
    execution_error: str | None = None
    executed_at: str | None = None
    filled_qty: int | None = None
    filled_price: float | None = None
```

- [ ] **Step 2: Extend Protocol**

In `storage/base.py`, the `TradeProposalStore` Protocol gains:

```python
    def update_execution(self, proposal_id: str, *,
                         execution_mode: str,
                         execution_order_id: str | None,
                         execution_error: str | None,
                         filled_qty: int | None,
                         filled_price: float | None,
                         executed_at: str) -> bool:
        """Write execution result fields for a proposal. Returns True on match."""
        ...
```

- [ ] **Step 3: Extend schema DDL**

In `data_schema/deployment_state.py`, the `trade_proposals` CREATE TABLE statement: add 6 columns. Also add a safety `ALTER TABLE ... ADD COLUMN` block that runs on `init_schema()` for rows from Phase 1 DBs already in the wild:

```sql
-- In the CREATE TABLE block, add before the closing paren:
    execution_mode       TEXT,
    execution_order_id   TEXT,
    execution_error      TEXT,
    executed_at          DATETIME,
    filled_qty           INTEGER,
    filled_price         REAL
```

Add a helper list of `ALTER TABLE` statements to run idempotently in `init_schema`:

```python
TRADE_PROPOSALS_PHASE2_ALTERS = [
    'ALTER TABLE trade_proposals ADD COLUMN execution_mode TEXT',
    'ALTER TABLE trade_proposals ADD COLUMN execution_order_id TEXT',
    'ALTER TABLE trade_proposals ADD COLUMN execution_error TEXT',
    'ALTER TABLE trade_proposals ADD COLUMN executed_at DATETIME',
    'ALTER TABLE trade_proposals ADD COLUMN filled_qty INTEGER',
    'ALTER TABLE trade_proposals ADD COLUMN filled_price REAL',
]
```

- [ ] **Step 4: Update SQLite impl**

`storage/sqlite_proposals.py::init_schema` runs CREATE then each ALTER wrapped in try/except sqlite3.OperationalError ("duplicate column name" is the expected error on re-run; swallow it).

Extend row mapping (`_row_to_proposal`) to pull the 6 new columns into the dataclass. If the table is legacy (pre-ALTER) the SELECT may fail — but post-`init_schema` it always has them.

Add `update_execution()` method with UPDATE statement.

- [ ] **Step 5: Test**

```python
# tests/test_storage_proposals_execution.py
import pytest
from storage.base import TradeProposal
from storage.sqlite_proposals import SQLiteTradeProposalStore


@pytest.fixture
def store(tmp_path):
    s = SQLiteTradeProposalStore(tmp_path=tmp_path)
    s.init_schema()
    return s


def _seed(store):
    p = TradeProposal(
        id='p-1', agent_id='a-1', created_at=None,
        decision_at='2026-04-24T09:30:00', action='buy', code='600519.SH',
        shares=100, price=237.5, reason='r', thinking='t', status='pending',
    )
    store.insert(p)
    return p


def test_new_proposal_has_null_execution_fields(store):
    _seed(store)
    got = store.get('p-1')
    assert got.execution_mode is None
    assert got.execution_order_id is None
    assert got.filled_qty is None


def test_update_execution_writes_fields(store):
    _seed(store)
    ok = store.update_execution(
        'p-1', execution_mode='dry_run', execution_order_id='mock-abc',
        execution_error=None, filled_qty=100, filled_price=237.5,
        executed_at='2026-04-24T10:00:00',
    )
    assert ok is True
    got = store.get('p-1')
    assert got.execution_mode == 'dry_run'
    assert got.execution_order_id == 'mock-abc'
    assert got.filled_qty == 100
    assert got.filled_price == 237.5
    assert got.executed_at == '2026-04-24T10:00:00'


def test_update_execution_missing_returns_false(store):
    assert store.update_execution(
        'ghost', execution_mode='dry_run', execution_order_id='x',
        execution_error=None, filled_qty=0, filled_price=0.0,
        executed_at='2026-04-24T10:00:00',
    ) is False


def test_init_schema_is_idempotent(store, tmp_path):
    # Second init on same path must not raise (ALTER column-exists handled)
    s2 = SQLiteTradeProposalStore(tmp_path=tmp_path)
    s2.init_schema()
    s2.init_schema()  # third call for good measure
```

Run → PASS after impl.

- [ ] **Step 6: Commit**

```bash
git add data_schema/deployment_state.py storage/base.py storage/sqlite_proposals.py tests/test_storage_proposals_execution.py tests/test_storage_base.py
git commit -m "feat(schema): trade_proposals execution fields + idempotent ALTER migration"
```

Also update `tests/test_storage_base.py` `TradeProposalStore` Protocol compliance fixture to include `update_execution`.

---

### Task 6: approve endpoint integration

**Files:**
- Modify: `api/proposals.py::approve_proposal`
- Create: `api/execution.py` — `GET /api/execution/mode`
- Test: `tests/test_api_proposals_phase2.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_api_proposals_phase2.py
import pytest

# Fixture `client` assumed available (reuses tests/test_p3f_phase1.py pattern
# or conftest; check existing conftest before writing).


def test_approve_dry_run_mode_persists_execution_result(client, monkeypatch, seeded_pending_proposal):
    # Default env (no BIYINGTONG_EXECUTION_MODE) → dry_run
    monkeypatch.delenv('BIYINGTONG_EXECUTION_MODE', raising=False)
    resp = client.post(f'/api/proposals/{seeded_pending_proposal.id}/approve')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['status'] == 'approved'
    assert body['execution_mode'] == 'dry_run'
    assert body['execution_order_id'].startswith('mock-')
    assert body['filled_qty'] == seeded_pending_proposal.shares
    assert body['execution_error'] is None


def test_approve_live_mode_calls_tdx(client, monkeypatch, seeded_pending_proposal):
    import tdx_service
    monkeypatch.setenv('BIYINGTONG_EXECUTION_MODE', 'live')
    calls = []
    monkeypatch.setattr(tdx_service.tdx, 'place_order',
                        lambda **kw: calls.append(kw) or {'order_id': 'tdx-999'})
    # Re-import execution so get_adapter() re-reads env
    import importlib, execution
    importlib.reload(execution)
    # Patch api/proposals to use reloaded factory — or the approve handler
    # imports inside the function, so no re-import needed.

    resp = client.post(f'/api/proposals/{seeded_pending_proposal.id}/approve')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['status'] == 'approved'
    assert body['execution_mode'] == 'live'
    assert body['execution_order_id'] == 'tdx-999'
    assert len(calls) == 1


def test_approve_live_mode_handles_tdx_error(client, monkeypatch, seeded_pending_proposal):
    import tdx_service
    monkeypatch.setenv('BIYINGTONG_EXECUTION_MODE', 'live')
    monkeypatch.setattr(tdx_service.tdx, 'place_order',
                        lambda **kw: {'error': 'insufficient funds'})
    import importlib, execution
    importlib.reload(execution)

    resp = client.post(f'/api/proposals/{seeded_pending_proposal.id}/approve')
    assert resp.status_code == 200  # approved + execution failed — still 200, UI shows error
    body = resp.get_json()
    assert body['status'] == 'approved'
    assert body['execution_mode'] == 'live'
    assert body['execution_error'] == 'insufficient funds'
    assert body['execution_order_id'] is None


def test_approve_already_decided_returns_409(client, seeded_pending_proposal):
    client.post(f'/api/proposals/{seeded_pending_proposal.id}/approve')  # first: 200
    r2 = client.post(f'/api/proposals/{seeded_pending_proposal.id}/approve')
    assert r2.status_code == 409


def test_execution_mode_endpoint(client, monkeypatch):
    monkeypatch.delenv('BIYINGTONG_EXECUTION_MODE', raising=False)
    import importlib, execution
    importlib.reload(execution)
    resp = client.get('/api/execution/mode')
    assert resp.status_code == 200
    assert resp.get_json() == {'mode': 'dry_run'}

    monkeypatch.setenv('BIYINGTONG_EXECUTION_MODE', 'live')
    importlib.reload(execution)
    resp = client.get('/api/execution/mode')
    assert resp.get_json() == {'mode': 'live'}
```

Fixture `seeded_pending_proposal` seeds a `TradeProposal(status='pending')` into storage.

Run → RED.

- [ ] **Step 2: Update approve_proposal**

In `api/proposals.py`:

```python
@api_bp.route('/proposals/<proposal_id>/approve', methods=['POST'])
def approve_proposal(proposal_id):
    """Phase 2: flip status → approved AND dispatch to ExecutionAdapter.

    The adapter is selected via BIYINGTONG_EXECUTION_MODE:
      dry_run (default) → MockExecutionAdapter (no TDX call)
      live             → TDXExecutionAdapter (real order)

    Execution failures do NOT revert the approval; the proposal stays
    'approved' with execution_error populated. UI surfaces this.
    """
    import storage
    from execution import get_adapter

    p = storage.proposals().get(proposal_id)
    if p is None:
        return jsonify({'error': 'not_found'}), 404
    if p.status != 'pending':
        return jsonify({'error': f'already {p.status}'}), 409

    storage.proposals().update_status(proposal_id, 'approved',
                                      decided_by='user')
    # Re-read so decided_at/decided_by are fresh
    p = storage.proposals().get(proposal_id)

    adapter = get_adapter()
    exec_result = adapter.place_order(p)
    storage.proposals().update_execution(
        proposal_id,
        execution_mode=exec_result.mode,
        execution_order_id=exec_result.order_id,
        execution_error=exec_result.error,
        filled_qty=exec_result.filled_qty,
        filled_price=exec_result.filled_price,
        executed_at=exec_result.executed_at,
    )
    return jsonify(_proposal_to_dict(storage.proposals().get(proposal_id)))
```

Update `_proposal_to_dict` to include the 6 new fields.

- [ ] **Step 3: Create api/execution.py**

```python
# api/execution.py
"""GET /api/execution/mode — tells the UI which mode the server is in."""
from __future__ import annotations

from flask import jsonify

from . import api_bp


@api_bp.route('/execution/mode')
def get_execution_mode():
    from execution import get_adapter
    return jsonify({'mode': get_adapter().mode})
```

Register in `api/__init__.py` if the pattern requires (check other submodules — many are auto-imported).

- [ ] **Step 4: Verify + commit**

```bash
pytest tests/test_api_proposals_phase2.py tests/test_p3f_phase1.py -v
git add api/proposals.py api/execution.py api/__init__.py tests/test_api_proposals_phase2.py
git commit -m "feat(api): approve_proposal dispatches to ExecutionAdapter + mode endpoint"
```

---

### Task 7: Frontend types + client + hook

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/hooks.ts`

- [ ] **Step 1: Extend TradeProposal type**

```typescript
// types.ts
export type ExecutionMode = 'dry_run' | 'live';

export type TradeProposal = {
  id: string;
  agent_id: string;
  created_at: string | null;
  decision_at: string;
  action: 'buy' | 'sell' | 'hold';
  code: string | null;
  shares: number | null;
  price: number | null;
  reason: string | null;
  thinking: string | null;
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  decided_by: string | null;
  decided_at: string | null;
  // Phase 2 execution
  execution_mode: ExecutionMode | null;
  execution_order_id: string | null;
  execution_error: string | null;
  executed_at: string | null;
  filled_qty: number | null;
  filled_price: number | null;
};
```

- [ ] **Step 2: client.getExecutionMode**

```typescript
// client.ts
export async function getExecutionMode(): Promise<{ mode: ExecutionMode }> {
  const r = await fetch(`${API_BASE}/api/execution/mode`);
  if (!r.ok) throw new Error(`GET /api/execution/mode: ${r.status}`);
  return r.json();
}
```

- [ ] **Step 3: hook**

```typescript
// hooks.ts
export function useExecutionMode() {
  return useQuery({
    queryKey: ['execution-mode'],
    queryFn: getExecutionMode,
    staleTime: Infinity,  // mode doesn't change without server restart
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/api/hooks.ts
git commit -m "feat(ui): execution mode type + useExecutionMode hook"
```

---

### Task 8: ExecutionModeBadge in TopBar

**Files:**
- Create: `frontend/src/components/ExecutionModeBadge.tsx`
- Modify: `frontend/src/components/TopBar.tsx`

- [ ] **Step 1: Component**

```tsx
// frontend/src/components/ExecutionModeBadge.tsx
import { useExecutionMode } from '../api/hooks';

export function ExecutionModeBadge() {
  const { data } = useExecutionMode();
  const mode = data?.mode ?? 'dry_run';
  const isLive = mode === 'live';
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px]
                  font-medium tracking-wider uppercase ${
        isLive
          ? 'bg-red-500/20 text-red-400 border border-red-500/50 animate-pulse'
          : 'bg-surface-2 text-text-dim border border-border'
      }`}
      title={isLive
        ? '⚠ LIVE TRADING — 审批将提交真实订单到 TDX'
        : 'DRY-RUN — 审批仅写 DB 状态，不下真单'}
    >
      {isLive ? '● LIVE' : 'DRY-RUN'}
    </span>
  );
}
```

- [ ] **Step 2: Mount in TopBar**

In `frontend/src/components/TopBar.tsx`, add `<ExecutionModeBadge />` next to the existing RedLine chips. Use the established alignment.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ExecutionModeBadge.tsx frontend/src/components/TopBar.tsx
git commit -m "feat(ui): ExecutionModeBadge in TopBar (live mode pulses red)"
```

---

### Task 9: LiveApproveModal — 2-step confirmation

**Files:**
- Create: `frontend/src/components/LiveApproveModal.tsx`
- Modify: `frontend/src/components/ProposalsPanel.tsx`

- [ ] **Step 1: LiveApproveModal component**

Renders on top of the page with backdrop. Shows:
- proposal summary table (code / action / shares / price / 估算金额 = shares × price)
- red warning banner: "⚠ 此操作会向通达信提交真实订单，不可撤销"
- input: "请输入 `确认下单` 以继续"
- buttons: `取消` (always enabled) and `确认提交` (enabled only when input exactly matches `确认下单`)

```tsx
// frontend/src/components/LiveApproveModal.tsx
import { useState } from 'react';
import type { TradeProposal } from '../api/types';

export function LiveApproveModal({
  proposal,
  onConfirm,
  onCancel,
}: {
  proposal: TradeProposal;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [typed, setTyped] = useState('');
  const REQUIRED_PHRASE = '确认下单';
  const canSubmit = typed === REQUIRED_PHRASE;
  const estAmount = (proposal.shares ?? 0) * (proposal.price ?? 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
         onClick={onCancel}>
      <div className="panel panel-border-soft p-6 min-w-[420px] max-w-[560px]"
           onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-text-hi mb-1">提交真实订单</h2>
        <div className="text-xs text-text-dim mb-4">
          LIVE TRADING — 通达信 place_order
        </div>

        <div className="bg-red-500/10 border border-red-500/40 rounded p-3 mb-4
                        text-red-300 text-sm">
          ⚠ 此操作会向通达信提交真实订单，<b>不可撤销</b>。
        </div>

        <table className="w-full text-sm mb-4">
          <tbody>
            <tr><td className="py-1 text-text-dim">代码</td><td>{proposal.code}</td></tr>
            <tr><td className="py-1 text-text-dim">方向</td>
                <td className={proposal.action === 'buy' ? 'text-red-400' : 'text-green-400'}>
                  {proposal.action === 'buy' ? '买入' : '卖出'}
                </td></tr>
            <tr><td className="py-1 text-text-dim">数量</td><td>{proposal.shares} 股</td></tr>
            <tr><td className="py-1 text-text-dim">价格</td><td>¥ {proposal.price?.toFixed(2)}</td></tr>
            <tr><td className="py-1 text-text-dim">预估金额</td>
                <td className="font-semibold">¥ {estAmount.toFixed(2)}</td></tr>
          </tbody>
        </table>

        <label className="block text-sm text-text-dim mb-2">
          请输入 <code className="text-red-400">{REQUIRED_PHRASE}</code> 以继续：
        </label>
        <input
          type="text"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder={REQUIRED_PHRASE}
          autoFocus
          className="w-full bg-surface-2 border border-border rounded px-3 py-2
                     text-sm mb-4 focus:outline-none focus:border-red-500/60"
        />

        <div className="flex gap-2 justify-end">
          <button onClick={onCancel}
                  className="px-4 py-1.5 rounded bg-surface-2 text-text-hi
                             border border-border hover:bg-surface-3">
            取消
          </button>
          <button
            onClick={onConfirm}
            disabled={!canSubmit}
            className={`px-4 py-1.5 rounded border text-sm font-medium ${
              canSubmit
                ? 'bg-red-500/80 text-white border-red-500 hover:bg-red-500'
                : 'bg-surface-2 text-text-faint border-border cursor-not-allowed'
            }`}
          >
            确认提交
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire into ProposalsPanel**

In `ProposalsPanel.tsx`:
- Import `useExecutionMode`, `LiveApproveModal`, `TradeProposal`
- State: `modalFor: TradeProposal | null`
- Approve button click handler:
  - If `executionMode === 'live'` → set `modalFor = proposal` (opens modal)
  - Else → directly call existing `useApproveProposal` mutation (dry-run)
- Modal `onConfirm` → call mutation, close modal
- Modal `onCancel` → just close modal
- After mutation success, if `execution_error` exists, show a toast or inline error card

Also add a small chip on each proposal card showing `DRY-RUN filled` or `LIVE pending` after approval to surface the execution mode.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LiveApproveModal.tsx frontend/src/components/ProposalsPanel.tsx
git commit -m "feat(ui): LiveApproveModal — 2-step confirmation required in live mode"
```

---

### Task 10: Regression + roadmap + merge

- [ ] **Full test suite:** `pytest -q`
  - Expected: 665 baseline + ~15 new (3 protocol + 2 mock + 3 tdx + 4 factory + 4 schema + 5 api) ≈ 680 passed
- [ ] **Frontend:** `cd frontend && npm run build` — green
- [ ] **Manual browser smoke (if dev env available):**
  - Start Flask (default mode) → visit /live → badge says "DRY-RUN"
  - Approve a pending proposal → no modal, proposal approved with dry_run fields populated
  - Restart with `BIYINGTONG_EXECUTION_MODE=live` + seed a proposal → badge pulses LIVE → approve → modal demands typed "确认下单" → on confirm, tq.place_order called (with mocked TDX so no real order)
- [ ] **Update roadmap:** `docs/superpowers/plans/2026-04-23-status-and-roadmap.md` — mark P3-F Phase 2 as ✅ Done with commit range + guardrails note
- [ ] **CLAUDE.md:** brief update — remove "Phase 2 is gated/deferred" since it's now delivered (guardrailed behind env var)
- [ ] **Memory:** update `framework_first_principle.md` — mark "订单生命周期" item as done via `execution/` module
- [ ] **Merge to main + push**

---

## Self-Review

**Safety against real-money accidents:**
- ✅ Default mode is `dry_run` — must set env var explicitly for live
- ✅ Typo in env var → falls back to `dry_run` with warning
- ✅ Live UI shows pulsing red `LIVE` badge in TopBar at all times
- ✅ Live approve requires typed "确认下单" confirmation (not just a button click)
- ✅ `tdx_service.place_order` is called from exactly ONE place (`TDXExecutionAdapter`) — easy to audit
- ✅ Validation rules ALREADY applied at proposal creation time via Phase 1 (inherits from Bug A fix in cleanup-round)
- ⚠ If a user approves a proposal that was created hours/days earlier under stale market data, the price may be off. Mitigation: UI shows proposal age; deep fix is a proposal-staleness rule (out of scope).

**Blast radius after Phase 2 lands but BEFORE env var flipped:** zero. Behavior is byte-identical to Phase 1 because MockExecutionAdapter just adds mock execution metadata to the DB row.

**Blast radius with env=live:** real orders submitted on every approve. Second-confirmation UI is the last line. If someone deletes the modal check in code, real orders fire on single click. Mitigation: the 2-step check lives in ONE component; add a test later (or post-hoc) that asserts the confirmation flow is present.

**Not covered (explicit non-goals of Phase 2):**
- Order status polling / fill tracking updates over time
- Partial-fill handling
- Position state sync from TDX (on approve, we assume filled_qty=shares optimistically)
- Cancel-order UI
- Multi-user auth (still single-user assumption from Phase 1)

These are Phase 2.5 / future work.

---

## Execution

Subagent-driven. File-ownership split for parallel:

- **Subagent A (execution core — Tasks 1-4):** `execution/*`, `tests/test_execution_adapter.py`
- **Subagent B (storage + API — Tasks 5-6):** `data_schema/deployment_state.py`, `storage/base.py` (TradeProposal + Protocol), `storage/sqlite_proposals.py`, `api/proposals.py`, `api/execution.py`, `api/__init__.py`, `tests/test_storage_proposals_execution.py`, `tests/test_api_proposals_phase2.py`, `tests/test_storage_base.py`
- **Subagent C (frontend — Tasks 7-9):** all `frontend/src/**` edits

A and C are fully disjoint; B depends on A for `execution.get_adapter` (only at runtime — A's committed code is enough). Dispatch A first, then B+C in parallel.

Task 10 runs on controller after all three return.

Total: ~3-4 hours.
