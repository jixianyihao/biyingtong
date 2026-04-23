"""Buy-and-hold baseline: equal-weight at day 1, hold to end."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from backtest.book import Book
from backtest.commission import FeeModel
from backtest.lot_allocator import allocate_lot
from backtest.stats import aggregate

from .base import BaselineResult, serialize_daily_records


def _parse(s: str) -> date:
    return datetime.strptime(s, '%Y-%m-%d').date()


def _trading_days(start: str, end: str) -> list:
    import storage
    return storage.calendar().get_trading_days(_parse(start), _parse(end))


def _load_prices(code: str, start, end) -> list:
    """[(date, close), ...] ascending."""
    import storage
    from datetime import datetime as _dt
    bars = storage.kline().load_range(
        code, '1d',
        _dt(start.year, start.month, start.day),
        _dt(end.year, end.month, end.day),
    )
    return [(b.datetime.date(), float(b.close_price)) for b in bars]


def run_buy_and_hold(*, session_id: str, start_date: str, end_date: str,
                     initial_capital: float, universe: list[str],
                     persist: bool = True) -> BaselineResult:
    days = _trading_days(start_date, end_date)
    if not days:
        raise ValueError('no trading days in range')

    start = _parse(start_date)
    end = _parse(end_date)
    price_series = {code: dict(_load_prices(code, start, end))
                    for code in universe}

    fee_model = FeeModel()
    book = Book(cash=initial_capital, fee_model=fee_model)
    entry_day = days[0]

    # Day-1 equal-weight buy. Iterative lot allocator picks the largest
    # 100-share multiple whose (notional + commission) fits in the cash
    # slice — an exact-fee-aware replacement for the older *0.995 buffer.
    alloc_per_stock = initial_capital / max(1, len(universe))
    for code in universe:
        px = price_series[code].get(entry_day)
        if px is None or px <= 0:
            continue
        shares = allocate_lot(cash=alloc_per_stock, price=px,
                              fee_model=fee_model)
        if shares < 100:
            continue
        book.execute_buy(code, shares=shares, price=px, d=entry_day)

    # Walk the rest of days to collect daily equity for stats
    daily_records = []
    prev_equity = initial_capital
    for d in days:
        mark_prices = {}
        for code in universe:
            p = price_series[code].get(d)
            if p is None:
                past = [v for dt, v in price_series[code].items() if dt <= d]
                if past:
                    p = past[-1]
            if p is not None:
                mark_prices[code] = p
        equity = book.equity(mark_prices)
        pnl_pct = ((equity - prev_equity) / prev_equity * 100.0
                   if prev_equity > 0 else 0.0)
        prev_equity = equity
        trades_today = (len(universe) if d == entry_day else 0)
        daily_records.append({
            'date': d, 'pnl_pct': pnl_pct, 'equity': equity,
            'trade_count': trades_today, 'won': 0,
        })

    overall, _zones = aggregate(daily_records, cutoff='2099-12-31',
                                initial_capital=initial_capital)
    result = BaselineResult(
        id=str(uuid.uuid4()), session_id=session_id,
        name='buy_and_hold',
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital,
        stats=overall, final_equity=prev_equity,
        daily_records=serialize_daily_records(daily_records),
    )
    if persist:
        import storage
        storage.baselines().insert(result)
    return result
