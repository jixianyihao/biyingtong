"""Load HS300 daily K-line from TDX (via tqcenter) into vnpy_sqlite.

Why we don't use vnpy_tdx: the PyPI package is an empty stub. The existing
tdx_service.py (tqcenter) already handles TDX auth + K-line retrieval; we
just convert its dict output into vnpy BarData objects for storage.

Entry points:
- `load_single_stock(symbol, start, end)` — one stock, returns bars written
- `load_batch(symbols, start, end)` — many stocks, returns {symbol: count}
"""
from __future__ import annotations

from datetime import datetime

from scripts.setup.vnpy_config import configure as _configure_vnpy

# Configure vnpy BEFORE importing vnpy_sqlite (it reads SETTINGS at import)
_configure_vnpy()

from vnpy.trader.constant import Exchange, Interval  # noqa: E402
from vnpy.trader.object import BarData  # noqa: E402
from vnpy_sqlite import Database  # noqa: E402

from tdx_service import tdx  # noqa: E402  (existing tqcenter wrapper)


def _exchange_for(symbol: str) -> Exchange:
    """Infer SSE / SZSE from the 6-digit symbol prefix."""
    if symbol.startswith(('6', '9')):
        return Exchange.SSE
    if symbol.startswith(('0', '3')):
        return Exchange.SZSE
    raise ValueError(f'Cannot infer exchange for symbol {symbol!r}')


def _tdx_full_code(symbol: str, exchange: Exchange) -> str:
    """tdx_service.get_kline expects '600519.SH' form."""
    suffix = 'SH' if exchange == Exchange.SSE else 'SZ'
    return f'{symbol}.{suffix}'


def load_single_stock(symbol: str, start: datetime, end: datetime) -> int:
    """Fetch daily bars via tqcenter and save to vnpy_sqlite.

    tdx.get_kline returns `count` bars ending today. We request enough bars
    to cover the [start, end] window, then filter to that window before save.

    Returns number of bars written.
    """
    exchange = _exchange_for(symbol)
    full = _tdx_full_code(symbol, exchange)

    if not tdx.ensure_connected():
        return 0

    # tqcenter returns `count` bars ending "now". Ask for enough to span [start, end].
    # Daily bars: N trading days ≈ N * 1.4 calendar days worst-case (weekends+holidays).
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
            volume=float(row.get('vol', 0)),
            turnover=0.0,
            open_interest=0.0,
            gateway_name='TDX',
        ))

    if bars:
        db = Database()
        try:
            db.save_bar_data(bars)
        finally:
            # vnpy_sqlite unconditionally calls db.connect() in __init__; close so
            # subsequent Database() instantiations (e.g. in tests) don't hit
            # peewee.OperationalError: Connection already opened.
            db.db.close()
    return len(bars)


def load_batch(symbols: list[str], start: datetime, end: datetime) -> dict[str, int]:
    """Fetch many stocks. Continues on per-stock error. Returns per-symbol counts."""
    result: dict[str, int] = {}
    for sym in symbols:
        try:
            result[sym] = load_single_stock(sym, start, end)
        except Exception as e:  # noqa: BLE001
            print(f'[load_batch] {sym} FAILED: {e}')
            result[sym] = 0
    return result


if __name__ == '__main__':
    # Smoke test — load 1 year of 茅台
    now = datetime.now()
    start = datetime(now.year - 1, now.month, now.day)
    end = datetime(now.year, now.month, now.day)
    n = load_single_stock('600519', start, end)
    print(f'600519: {n} bars written to vnpy_sqlite')
