"""Ingest HS300 daily K-line from TDX (via tqcenter) into storage.kline().

Uses tdx_service.get_kline (tqcenter wrapper) to fetch, converts tqcenter's
lot-based volume to shares (×100), constructs vnpy BarData, and delegates
persistence to storage.kline().

Entry points:
- `load_single_stock(symbol, start, end)`
- `load_batch(symbols, start, end)`
"""
from __future__ import annotations

from datetime import datetime

from scripts.setup.vnpy_config import configure as _configure_vnpy

_configure_vnpy()

from vnpy.trader.constant import Exchange, Interval  # noqa: E402
from vnpy.trader.object import BarData  # noqa: E402

from tdx_service import tdx  # noqa: E402  (existing tqcenter wrapper)

# tqcenter vol is in 手 (100-share lots). vnpy BarData.volume is in shares.
_VOLUME_LOTS_TO_SHARES = 100


def _exchange_for(symbol: str) -> Exchange:
    if symbol.startswith(('6', '9')):
        return Exchange.SSE
    if symbol.startswith(('0', '3')):
        return Exchange.SZSE
    raise ValueError(f'Cannot infer exchange for symbol {symbol!r}')


def _tdx_full_code(symbol: str, exchange: Exchange) -> str:
    suffix = 'SH' if exchange == Exchange.SSE else 'SZ'
    return f'{symbol}.{suffix}'


def load_single_stock(symbol: str, start: datetime, end: datetime) -> int:
    """Fetch daily bars via tqcenter, construct BarData (volume × 100), save to storage."""
    try:
        exchange = _exchange_for(symbol)
    except ValueError:
        # Custom / test symbols: default to SSE
        exchange = Exchange.SSE

    full = _tdx_full_code(symbol, exchange)
    if not tdx.ensure_connected():
        return 0

    today = datetime.now()
    calendar_span = max((today - start).days + 7, 30)
    count = max(int(calendar_span * 1.2), 30)

    raw = tdx.get_kline(full, period='1d', count=count)
    if not raw:
        return 0

    bars: list[BarData] = []
    for row in raw:
        try:
            bar_dt = datetime.strptime(row['date'], '%Y-%m-%d')
        except (KeyError, ValueError):
            continue
        if bar_dt < start or bar_dt > end:
            continue
        bars.append(BarData(
            symbol=symbol,
            exchange=exchange,
            datetime=bar_dt,
            interval=Interval.DAILY,
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


def load_batch(symbols: list[str], start: datetime, end: datetime) -> dict[str, int]:
    result: dict[str, int] = {}
    for sym in symbols:
        try:
            result[sym] = load_single_stock(sym, start, end)
        except Exception as e:  # noqa: BLE001
            print(f'[load_batch] {sym} FAILED: {e}')
            result[sym] = 0
    return result


if __name__ == '__main__':
    now = datetime.now()
    start = datetime(now.year - 1, now.month, now.day)
    end = datetime(now.year, now.month, now.day)
    n = load_single_stock('600519', start, end)
    print(f'600519: {n} bars written via storage.kline()')
