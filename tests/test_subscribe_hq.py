from unittest.mock import MagicMock
import tdx_service as ts


def test_subscribe_hq_delegates_to_tq(monkeypatch):
    fake_tq = MagicMock()
    fake_tq.subscribe_hq = MagicMock(return_value='sub-123')
    monkeypatch.setattr(ts, 'tq', fake_tq)
    svc = ts.TDXService()
    svc._connected = True  # bypass ensure_connected
    cb = lambda payload: None
    handle = svc.subscribe_hq(['600519.SH'], cb)
    fake_tq.subscribe_hq.assert_called_once_with(
        stock_list=['600519.SH'], callback=cb
    )
    assert handle == 'sub-123'


def test_unsubscribe_hq_delegates(monkeypatch):
    fake_tq = MagicMock()
    fake_tq.unsubscribe_hq = MagicMock()
    monkeypatch.setattr(ts, 'tq', fake_tq)
    svc = ts.TDXService()
    svc._connected = True
    svc.unsubscribe_hq('sub-123')
    fake_tq.unsubscribe_hq.assert_called_once_with('sub-123')


def test_get_gpjy_value_passes_fields(monkeypatch):
    fake_tq = MagicMock()
    fake_tq.get_gpjy_value = MagicMock(return_value={'600519.SH': {}})
    monkeypatch.setattr(ts, 'tq', fake_tq)
    svc = ts.TDXService()
    svc._connected = True
    svc.get_gpjy_value(['600519.SH'], ['GP1', 'GP5'], '20260101', '20260422')
    fake_tq.get_gpjy_value.assert_called_once_with(
        stock_list=['600519.SH'],
        field_list=['GP1', 'GP5'],
        start_time='20260101', end_time='20260422',
    )


def test_get_bkjy_value_passes_fields(monkeypatch):
    fake_tq = MagicMock()
    fake_tq.get_bkjy_value = MagicMock(return_value={'880660.SH': {}})
    monkeypatch.setattr(ts, 'tq', fake_tq)
    svc = ts.TDXService()
    svc._connected = True
    svc.get_bkjy_value(['880660.SH'], ['BK5'], '20260101', '20260422')
    fake_tq.get_bkjy_value.assert_called_once_with(
        stock_list=['880660.SH'],
        field_list=['BK5'],
        start_time='20260101', end_time='20260422',
    )


def test_get_stock_list_in_sector_delegates(monkeypatch):
    fake_tq = MagicMock()
    fake_tq.get_stock_list_in_sector = MagicMock(
        return_value=['600519.SH', '000858.SZ']
    )
    monkeypatch.setattr(ts, 'tq', fake_tq)
    svc = ts.TDXService()
    svc._connected = True
    out = svc.get_stock_list_in_sector('白酒')
    assert out == ['600519.SH', '000858.SZ']


def test_subscribe_hq_returns_none_when_disconnected(monkeypatch):
    fake_tq = MagicMock()
    monkeypatch.setattr(ts, 'tq', fake_tq)
    svc = ts.TDXService()
    svc._connected = False
    assert svc.subscribe_hq(['600519.SH'], lambda _: None) is None
    fake_tq.subscribe_hq.assert_not_called()
