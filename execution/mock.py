"""MockExecutionAdapter — dry-run path, never talks to TDX.

Fills as requested (filled_qty == proposal.shares, filled_price == proposal.price).
Generates a UUID-based mock order id so DB rows can carry the value through.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

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
            executed_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds'),
        )

    def query_status(self, proposal) -> ExecutionResult:  # noqa: ANN001
        """Mock: echo current execution_* fields as if fully filled."""
        shares = int(proposal.shares or 0)
        price = float(proposal.price or 0.0)
        return ExecutionResult(
            success=True, mode='dry_run',
            order_id=proposal.execution_order_id or f'mock-{uuid.uuid4().hex[:12]}',
            filled_qty=proposal.filled_qty if proposal.filled_qty is not None else shares,
            filled_price=proposal.filled_price if proposal.filled_price is not None else price,
            error=None,
            executed_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds'),
        )

    def cancel(self, proposal) -> ExecutionResult:  # noqa: ANN001
        return ExecutionResult(
            success=True, mode='dry_run',
            order_id=f'cancelled-{proposal.execution_order_id or "n/a"}',
            filled_qty=0, filled_price=0.0,
            error=None,  # error=None means "cancel succeeded"
            executed_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds'),
        )
