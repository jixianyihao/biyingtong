"""TDXExecutionAdapter — live order execution via tdx_service.place_order.

This is the one place where `tdx_service.place_order` should be called
from. All call-sites go through get_adapter() in __init__.py and thus
through BIYINGTONG_EXECUTION_MODE. Accidentally swapping in this adapter
is the only way real money moves.
"""
from __future__ import annotations

from datetime import datetime, timezone

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
        ts = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds')

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
