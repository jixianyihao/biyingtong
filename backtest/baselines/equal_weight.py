"""Equal-weight monthly rebalance baseline."""
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
    import storage
    from datetime import datetime as _dt
    bars = storage.kline().load_range(
        code, '1d',
        _dt(start.year, start.month, start.day),
        _dt(end.year, end.month, end.day),
    )
    return [(b.datetime.date(), float(b.close_price)) for b in bars]


def _is_month_start(d: date, prev_d: date | None) -> bool:
    """First trading day we see in a new (year, month) vs the previous day."""
    if prev_d is None:
        return True
    return (d.year, d.month) != (prev_d.year, prev_d.month)


def run_equal_weight(*, session_id: str, start_date: str, end_date: str,
                     initial_capital: float, universe: list[str],
                     persist: bool = True) -> BaselineResult:
    days = _trading_days(start_date, end_date)
    if not days:
        raise ValueError('no trading days in range')

    start = _parse(start_date)
    end = _parse(end_date)
    price_series = {code: dict(_load_prices(code, start, end))
                    for code in universe}

    book = Book(cash=initial_capital, fee_model=FeeModel())
    daily_records = []
    prev_equity = initial_capital
    prev_d = None
    n = max(1, len(universe))

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

        trades_today = 0
        if _is_month_start(d, prev_d):
            # Sell everything sellable (T+1 permitting), then buy equal-weight
            for code in list(book.positions_view().keys()):
                pos = book.positions_view().get(code, {})
                shares = pos.get('shares', 0)
                if shares > 0 and code in mark_prices:
                    fill = book.execute_sell(
                        code, shares=shares, price=mark_prices[code], d=d,
                    )
                    if fill:
                        trades_today += 1

            equity_now = book.equity(mark_prices)
            target_per_stock = equity_now / n
            for code in universe:
                px = mark_prices.get(code)
                if px is None or px <= 0:
                    continue
                # After each buy book.cash drops below the nominal target —
                # the allocator needs the TRUE cash budget, not the target.
                shares = allocate_lot(
                    cash=min(book.cash, target_per_stock),
                    price=px, fee_model=book.fee_model,
                )
                if shares < 100:
                    continue
                fill = book.execute_buy(code, shares=shares, price=px, d=d)
                if fill:
                    trades_today += 1

        equity = book.equity(mark_prices)
        pnl_pct = ((equity - prev_equity) / prev_equity * 100.0
                   if prev_equity > 0 else 0.0)
        prev_equity = equity
        prev_d = d
        daily_records.append({
            'date': d, 'pnl_pct': pnl_pct, 'equity': equity,
            'trade_count': trades_today, 'won': 0,
        })

    overall, _zones = aggregate(daily_records, cutoff='2099-12-31',
                                initial_capital=initial_capital)
    result = BaselineResult(
        id=str(uuid.uuid4()), session_id=session_id, name='equal_weight',
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital,
        stats=overall, final_equity=prev_equity,
        daily_records=serialize_daily_records(daily_records),
    )
    if persist:
        import storage
        storage.baselines().insert(result)
    return result
