"""Ingest market-index daily K-line (e.g. CSI 300 = 000300.SH) from TDX.

load_kline.py auto-infers exchange from symbol prefix, which miscategorises
indexes whose code happens to start with '0' (like 000300.SH = CSI 300 on SSE,
not SZSE). This helper always forces SSE.

Entry point: ``load_index(symbol, start, end)``.
"""
from __future__ import annotations

from datetime import datetime

from scripts.setup.vnpy_config import configure as _configure_vnpy
_configure_vnpy()

from vnpy.trader.constant import Exchange, Interval  # noqa: E402
from vnpy.trader.object import BarData  # noqa: E402

from tdx_service import tdx  # noqa: E402

# tqcenter vol is in 手 (100-share lots); indexes don't really have "shares"
# but we keep the same convention for consistency with load_kline.
_VOLUME_LOTS_TO_SHARES = 100


def _build_bar(symbol: str, raw: dict):
    try:
        bar_dt = datetime.strptime(raw['date'], '%Y-%m-%d')
    except (KeyError, ValueError, TypeError):
        return None
    return BarData(
        symbol=symbol,
        exchange=Exchange.SSE,
        datetime=bar_dt,
        interval=Interval.DAILY,
        open_price=float(raw.get('open', 0)),
        high_price=float(raw.get('high', 0)),
        low_price=float(raw.get('low', 0)),
        close_price=float(raw.get('close', 0)),
        volume=float(raw.get('vol', 0)) * _VOLUME_LOTS_TO_SHARES,
        turnover=0.0,
        open_interest=0.0,
        gateway_name='TDX',
    )


def load_index(symbol: str, start: datetime, end: datetime) -> int:
    """Fetch daily bars via tqcenter with explicit SSE code, save to storage."""
    if not tdx.ensure_connected():
        return 0

    today = datetime.now()
    calendar_span = max((today - start).days + 7, 30)
    count = max(int(calendar_span * 1.2), 30)

    full = f'{symbol}.SH'
    raw = tdx.get_kline(full, period='1d', count=count)
    if not raw:
        return 0

    bars = []
    for row in raw:
        bar = _build_bar(symbol, row)
        if bar is None:
            continue
        if bar.datetime < start or bar.datetime > end:
            continue
        bars.append(bar)

    if not bars:
        return 0

    from storage import kline
    return kline().save_bars(bars)


if __name__ == '__main__':
    now = datetime.now()
    start = datetime(now.year - 1, now.month, now.day)
    end = datetime(now.year, now.month, now.day)
    n = load_index('000300', start, end)
    print(f'000300: {n} bars loaded (SSE, CSI 300 index)')
