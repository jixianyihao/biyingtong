"""5-minute bar ingestion — mirror of load_kline.py but with intraday granularity.

Uses tdx_service.get_kline(period='5m') and constructs BarData with
Interval.MINUTE_5. Unblocks the intraday_t0 persona which until now had
only daily bars despite the persona spec calling for 5m.
"""
from __future__ import annotations

from datetime import datetime

from scripts.setup.vnpy_config import configure as _configure_vnpy

_configure_vnpy()

from vnpy.trader.constant import Exchange, Interval  # noqa: E402
from vnpy.trader.object import BarData  # noqa: E402

from tdx_service import tdx  # noqa: E402


_VOLUME_LOTS_TO_SHARES = 100


def _exchange_for(symbol: str) -> Exchange:
    if symbol.startswith(('6', '9')):
        return Exchange.SSE
    if symbol.startswith(('0', '3')):
        return Exchange.SZSE
    raise ValueError(f'Cannot infer exchange for symbol {symbol!r}')


def _tdx_full_code(symbol: str, exchange: Exchange) -> str:
    return f"{symbol}.{'SH' if exchange == Exchange.SSE else 'SZ'}"


def _parse_dt(raw: str) -> datetime | None:
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y%m%d%H%M'):
        try:
            return datetime.strptime(raw, fmt)
        except (ValueError, TypeError):
            continue
    return None


def load_single_stock_5m(symbol: str, start: datetime, end: datetime) -> int:
    """Fetch 5m bars via tqcenter, build BarData(MINUTE_5), persist via storage."""
    try:
        exchange = _exchange_for(symbol)
    except ValueError:
        exchange = Exchange.SSE

    full = _tdx_full_code(symbol, exchange)
    if not tdx.ensure_connected():
        return 0

    # 48 five-minute bars per trading day; pad for weekends.
    span_days = max((end - start).days + 2, 2)
    count = max(span_days * 60, 60)

    raw = tdx.get_kline(full, period='5m', count=count)
    if not raw:
        return 0

    bars: list[BarData] = []
    interval = getattr(Interval, 'MINUTE_5', None) or getattr(Interval, 'MINUTE')
    for row in raw:
        bar_dt = _parse_dt(row.get('date', ''))
        if bar_dt is None or bar_dt < start or bar_dt > end:
            continue
        bars.append(BarData(
            symbol=symbol,
            exchange=exchange,
            datetime=bar_dt,
            interval=interval,
            open_price=float(row.get('open', 0)),
            high_price=float(row.get('high', 0)),
            low_price=float(row.get('low', 0)),
            close_price=float(row.get('close', 0)),
            volume=float(row.get('vol', 0)) * _VOLUME_LOTS_TO_SHARES,
            turnover=0.0,
            open_interest=0.0,
            gateway_name='TDX',
        ))

    if not bars:
        return 0

    from storage import kline
    return kline().save_bars(bars)


def load_batch_5m(symbols: list[str], start: datetime, end: datetime) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in symbols:
        try:
            out[s] = load_single_stock_5m(s, start, end)
        except Exception as e:  # noqa: BLE001
            print(f'[load_batch_5m] {s} FAILED: {e}')
            out[s] = 0
    return out


if __name__ == '__main__':
    from datetime import timedelta
    now = datetime.now()
    start = now - timedelta(days=2)
    n = load_single_stock_5m('600519', start=start, end=now)
    print(f'600519: {n} 5m bars written via storage.kline()')
