"""build_market_snapshot — fetches + summarizes per-stock data for prompt injection."""
from datetime import date


def test_snapshot_shape(monkeypatch):
    from agents.context_builder import build_market_snapshot
    # Mock the underlying tool calls
    from tools import get_kline, get_financials, get_technical
    monkeypatch.setattr(get_kline, 'call', lambda i: {
        'code': i['code'], 'period': '1d',
        'bars': [{'date': '2025-11-17', 'close': 100.0},
                 {'date': '2025-11-16', 'close': 99.0}],
    })
    monkeypatch.setattr(get_financials, 'call', lambda i: {
        'code': i['code'],
        'pe': 15.0, 'pb': 3.0, 'roe': 25.0,
        'net_margin': 40.0, 'revenue_growth': 12.0,
    })
    monkeypatch.setattr(get_technical, 'call', lambda i: {
        'code': i['code'], 'indicators': {
            'ma20': 98.5, 'rsi14': 55.0, 'macd': 0.3,
        },
    })

    snap = build_market_snapshot(['X.SH'], date(2025, 11, 17))
    assert snap['date'] == '2025-11-17'
    assert 'X.SH' in snap['stocks']
    s = snap['stocks']['X.SH']
    assert s['kline_summary']['latest_close'] == 100.0
    assert s['financials']['pe'] == 15.0
    assert s['technical']['ma20'] == 98.5


def test_snapshot_missing_data_returns_none(monkeypatch):
    from agents.context_builder import build_market_snapshot
    from tools import get_kline, get_financials, get_technical
    monkeypatch.setattr(get_kline, 'call', lambda i: {'bars': []})
    monkeypatch.setattr(get_financials, 'call',
                        lambda i: (_ for _ in ()).throw(
                            RuntimeError('no data')))
    monkeypatch.setattr(get_technical, 'call',
                        lambda i: (_ for _ in ()).throw(
                            RuntimeError('no data')))

    snap = build_market_snapshot(['X.SH'], date(2025, 11, 17))
    s = snap['stocks']['X.SH']
    assert s['kline_summary'] is None
    assert s['financials'] is None
    assert s['technical'] is None


def test_snapshot_multi_stock(monkeypatch):
    from agents.context_builder import build_market_snapshot
    from tools import get_kline, get_financials, get_technical
    call_log = []

    def kline_call(i):
        call_log.append(('kline', i['code']))
        return {'bars': [{'date': '2025-11-17', 'close': 100.0}]}

    monkeypatch.setattr(get_kline, 'call', kline_call)
    monkeypatch.setattr(get_financials, 'call', lambda i: {})
    monkeypatch.setattr(get_technical, 'call', lambda i: {})

    snap = build_market_snapshot(['A.SH', 'B.SZ', 'C.SH'], date(2025, 11, 17))
    assert set(snap['stocks'].keys()) == {'A.SH', 'B.SZ', 'C.SH'}
    assert len([c for c in call_log if c[0] == 'kline']) == 3
