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
