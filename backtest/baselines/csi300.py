"""CSI 300 index baseline: passive tracker of 000300.SH."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from backtest.stats import aggregate

from .base import BaselineResult


_INDEX_CODE = '000300.SH'


def _parse(s: str) -> date:
    return datetime.strptime(s, '%Y-%m-%d').date()


def _trading_days(start: str, end: str) -> list:
    import storage
    return storage.calendar().get_trading_days(_parse(start), _parse(end))


def _load_index_series(start, end) -> list:
    import storage
    from datetime import datetime as _dt
    bars = storage.kline().load_range(
        _INDEX_CODE, '1d',
        _dt(start.year, start.month, start.day),
        _dt(end.year, end.month, end.day),
    )
    return [(b.datetime.date(), float(b.close_price)) for b in bars]


def run_csi300(*, session_id: str, start_date: str, end_date: str,
               initial_capital: float,
               persist: bool = True) -> BaselineResult:
    days = _trading_days(start_date, end_date)
    start = _parse(start_date)
    end = _parse(end_date)
    index_bars = _load_index_series(start, end)
    index_by_day = dict(index_bars)

    if not days or not index_bars:
        raise ValueError('no index bars in range')

    base_px = index_bars[0][1]
    daily_records = []
    prev_equity = initial_capital
    for d in days:
        px = index_by_day.get(d)
        if px is None:
            past = [v for dt, v in index_bars if dt <= d]
            if past:
                px = past[-1]
        if px is None:
            continue
        # Equity = capital × (today's index / start index)
        equity = initial_capital * (px / base_px)
        pnl_pct = ((equity - prev_equity) / prev_equity * 100.0
                   if prev_equity > 0 else 0.0)
        prev_equity = equity
        daily_records.append({
            'date': d, 'pnl_pct': pnl_pct, 'equity': equity,
            'trade_count': 0, 'won': 0,
        })

    overall, _zones = aggregate(daily_records, cutoff='2099-12-31',
                                initial_capital=initial_capital)
    daily_records_serial = [
        {'date': rec['date'].isoformat(),
         'equity': rec['equity'],
         'pnl_pct': rec['pnl_pct'],
         'trade_count': rec['trade_count'],
         'won': rec['won']}
        for rec in daily_records
    ]
    result = BaselineResult(
        id=str(uuid.uuid4()), session_id=session_id, name='csi300',
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital,
        stats=overall, final_equity=prev_equity,
        daily_records=daily_records_serial,
    )
    if persist:
        import storage
        storage.baselines().insert(result)
    return result
