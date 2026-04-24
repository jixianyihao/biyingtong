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
