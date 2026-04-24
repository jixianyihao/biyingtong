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
