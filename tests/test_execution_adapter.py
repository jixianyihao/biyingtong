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
    class Compliant:
        @property
        def mode(self) -> str:
            return 'dry_run'

        def place_order(self, proposal):  # noqa: ANN001
            return ExecutionResult(
                success=True, mode='dry_run', order_id='x',
                filled_qty=0, filled_price=0.0, error=None,
                executed_at=None,
            )

        def query_status(self, proposal):  # noqa: ANN001
            return ExecutionResult(
                success=True, mode='dry_run', order_id='x',
                filled_qty=0, filled_price=0.0, error=None,
                executed_at=None,
            )

        def cancel(self, proposal):  # noqa: ANN001
            return ExecutionResult(
                success=True, mode='dry_run', order_id='cancelled-x',
                filled_qty=0, filled_price=0.0, error=None,
                executed_at=None,
            )

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


# ─── Phase 25 polish: query_status + cancel ────────────────────────────


def _make_approved_proposal(
    *, execution_order_id='mock-abc123def456',
    filled_qty=100, filled_price=237.5,
    code='600519.SH', shares=100, price=237.5,
):
    from storage.base import TradeProposal
    return TradeProposal(
        id='prop-1', agent_id='agent-1',
        created_at=None, decision_at='2026-04-24T09:30:00',
        action='buy', code=code, shares=shares, price=price,
        reason='r', thinking='t', status='approved',
        decided_by='user', decided_at='2026-04-24T09:31:00',
        execution_mode='dry_run',
        execution_order_id=execution_order_id,
        execution_error=None,
        executed_at='2026-04-24T09:31:01',
        filled_qty=filled_qty, filled_price=filled_price,
    )


def test_mock_query_status_echoes_existing():
    from execution.mock import MockExecutionAdapter
    adapter = MockExecutionAdapter()
    p = _make_approved_proposal(
        execution_order_id='mock-xyz', filled_qty=100, filled_price=237.5,
    )
    r = adapter.query_status(p)
    assert r.success is True
    assert r.mode == 'dry_run'
    assert r.order_id == 'mock-xyz'  # echoed
    assert r.filled_qty == 100
    assert r.filled_price == 237.5
    assert r.error is None
    assert r.executed_at is not None


def test_mock_cancel_marks_cancelled():
    from execution.mock import MockExecutionAdapter
    adapter = MockExecutionAdapter()
    p = _make_approved_proposal(execution_order_id='mock-xyz')
    r = adapter.cancel(p)
    assert r.success is True
    assert r.mode == 'dry_run'
    assert r.order_id == 'cancelled-mock-xyz'
    assert r.filled_qty == 0
    assert r.filled_price == 0.0
    assert r.error is None
    assert r.executed_at is not None


def test_tdx_query_status_finds_matching_order(monkeypatch):
    from execution.tdx import TDXExecutionAdapter
    import tdx_service

    def fake_get_orders(stock_code=''):
        assert stock_code == '600519.SH'
        return [
            {'order_id': 'tdx-other', 'filled_qty': 100, 'avg_price': 100.0},
            {'order_id': 'tdx-12345', 'filled_qty': 100, 'avg_price': 237.6},
        ]
    monkeypatch.setattr(tdx_service.tdx, 'get_orders', fake_get_orders)

    adapter = TDXExecutionAdapter()
    p = _make_approved_proposal(execution_order_id='tdx-12345',
                                filled_qty=0, filled_price=0.0)
    r = adapter.query_status(p)
    assert r.success is True
    assert r.mode == 'live'
    assert r.order_id == 'tdx-12345'
    assert r.filled_qty == 100
    assert r.filled_price == 237.6
    assert r.error is None


def test_tdx_query_status_handles_missing_order(monkeypatch):
    from execution.tdx import TDXExecutionAdapter
    import tdx_service

    monkeypatch.setattr(tdx_service.tdx, 'get_orders',
                        lambda stock_code='': [{'order_id': 'tdx-other'}])
    adapter = TDXExecutionAdapter()
    p = _make_approved_proposal(execution_order_id='tdx-12345',
                                filled_qty=50, filled_price=237.5)
    r = adapter.query_status(p)
    # success=True so caller persists "no fresh data" without flipping a
    # hard error, but error includes hint and existing fields preserved.
    assert r.success is True
    assert r.mode == 'live'
    assert r.order_id == 'tdx-12345'
    assert r.filled_qty == 50
    assert r.filled_price == 237.5
    assert r.error and "order book" in r.error


def test_tdx_query_status_no_order_id():
    from execution.tdx import TDXExecutionAdapter
    adapter = TDXExecutionAdapter()
    p = _make_approved_proposal(execution_order_id=None)
    r = adapter.query_status(p)
    assert r.success is False
    assert r.error and 'no execution_order_id' in r.error.lower()


def test_tdx_cancel_calls_tdx_cancel_order(monkeypatch):
    from execution.tdx import TDXExecutionAdapter
    import tdx_service

    captured = {}

    def fake_cancel(stock_code, order_id):
        captured.update({'stock_code': stock_code, 'order_id': order_id})
        return {}  # any non-error dict
    monkeypatch.setattr(tdx_service.tdx, 'cancel_order', fake_cancel)

    adapter = TDXExecutionAdapter()
    p = _make_approved_proposal(execution_order_id='tdx-12345',
                                code='600519.SH')
    r = adapter.cancel(p)
    assert captured == {'stock_code': '600519.SH', 'order_id': 'tdx-12345'}
    assert r.success is True
    assert r.mode == 'live'
    assert r.order_id == 'cancelled-tdx-12345'
    assert r.error is None


def test_tdx_cancel_handles_error(monkeypatch):
    from execution.tdx import TDXExecutionAdapter
    import tdx_service

    monkeypatch.setattr(tdx_service.tdx, 'cancel_order',
                        lambda stock_code, order_id: {'error': 'order already filled'})
    adapter = TDXExecutionAdapter()
    p = _make_approved_proposal(execution_order_id='tdx-12345')
    r = adapter.cancel(p)
    assert r.success is False
    assert r.mode == 'live'
    assert r.order_id == 'tdx-12345'  # original id, NOT cancelled- prefix
    assert r.error == 'order already filled'


def test_tdx_cancel_no_order_id():
    from execution.tdx import TDXExecutionAdapter
    adapter = TDXExecutionAdapter()
    p = _make_approved_proposal(execution_order_id=None)
    r = adapter.cancel(p)
    assert r.success is False
    assert r.error and 'no order_id' in r.error.lower()
