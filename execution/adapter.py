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

    def query_status(self, proposal) -> ExecutionResult:  # noqa: ANN001
        """Re-query the order's current fill status. Returns updated
        ExecutionResult — caller persists via storage.proposals().update_execution.
        For Mock, returns the same fields (no-op refresh)."""
        ...

    def cancel(self, proposal) -> ExecutionResult:  # noqa: ANN001
        """Cancel a previously placed order. Success → ExecutionResult with
        error=None and a cancellation marker (e.g. order_id prefixed 'cancelled-').
        Mock always succeeds; TDX delegates to tdx.cancel_order."""
        ...
