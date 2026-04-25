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

    def query_status(self, proposal) -> ExecutionResult:  # noqa: ANN001
        ts = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds')
        code = proposal.code or ''
        target_id = proposal.execution_order_id
        if not target_id:
            return ExecutionResult(
                success=False, mode='live', order_id=None,
                filled_qty=0, filled_price=0.0,
                error='no execution_order_id to query', executed_at=ts,
            )
        from tdx_service import tdx
        try:
            orders = tdx.get_orders(stock_code=code) or []
        except Exception as e:  # noqa: BLE001
            return ExecutionResult(
                success=False, mode='live', order_id=target_id,
                filled_qty=0, filled_price=0.0,
                error=f'{type(e).__name__}: {e}', executed_at=ts,
            )
        # Find by order_id; tqcenter dict keys vary, accept several aliases
        match = None
        for o in orders:
            if not isinstance(o, dict):
                continue
            oid = str(o.get('order_id') or o.get('id') or o.get('orderId') or '')
            if oid == str(target_id):
                match = o
                break
        if match is None:
            return ExecutionResult(
                success=True, mode='live', order_id=target_id,
                filled_qty=int(proposal.filled_qty or 0),
                filled_price=float(proposal.filled_price or 0.0),
                error="order not in today's order book",
                executed_at=ts,
            )
        filled = int(match.get('filled_qty') or match.get('matched_amount') or 0)
        avg_price = float(
            match.get('avg_price')
            or match.get('matched_price')
            or proposal.price
            or 0.0
        )
        return ExecutionResult(
            success=True, mode='live', order_id=target_id,
            filled_qty=filled, filled_price=avg_price,
            error=None, executed_at=ts,
        )

    def cancel(self, proposal) -> ExecutionResult:  # noqa: ANN001
        ts = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds')
        code = proposal.code or ''
        oid = proposal.execution_order_id
        if not oid:
            return ExecutionResult(
                success=False, mode='live', order_id=None,
                filled_qty=0, filled_price=0.0,
                error='no order_id to cancel', executed_at=ts,
            )
        from tdx_service import tdx
        try:
            result = tdx.cancel_order(stock_code=code, order_id=oid)
        except Exception as e:  # noqa: BLE001
            return ExecutionResult(
                success=False, mode='live', order_id=oid,
                filled_qty=0, filled_price=0.0,
                error=f'{type(e).__name__}: {e}', executed_at=ts,
            )
        if isinstance(result, dict) and result.get('error'):
            return ExecutionResult(
                success=False, mode='live', order_id=oid,
                filled_qty=0, filled_price=0.0,
                error=str(result['error']), executed_at=ts,
            )
        return ExecutionResult(
            success=True, mode='live',
            order_id=f'cancelled-{oid}',
            filled_qty=0, filled_price=0.0,
            error=None, executed_at=ts,
        )
