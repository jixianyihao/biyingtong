"""RuleRunner — deterministic rule-strategy backtests, parallel structure to
BacktestRunner but driven by a Strategy instance instead of an LLM AgentRunner."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from validation.quality_gate import evaluate_quality_gate

from .base import BacktestResult
from .stats import aggregate


def _load_daily_closes(code: str, start: date, end: date) -> list:
    """[(date, close), ...] ascending for one stock."""
    import storage
    from datetime import datetime as _dt
    bars = storage.kline().load_range(
        code, '1d',
        _dt(start.year, start.month, start.day),
        _dt(end.year, end.month, end.day),
    )
    return [(b.datetime.date(), float(b.close_price)) for b in bars]


def _trading_days(start: str, end: str) -> list:
    import storage
    return storage.calendar().get_trading_days(_parse(start), _parse(end))


def _parse(s: str) -> date:
    return datetime.strptime(s, '%Y-%m-%d').date()


class RuleRunner:
    def __init__(self, strategy, initial_capital: float = 1_000_000.0):
        self._strategy = strategy
        self._default_capital = initial_capital

    def run(self, *, session_id: str, start_date: str, end_date: str,
            initial_capital: float | None = None,
            universe: list[str], notes: str | None = None) -> BacktestResult:
        import storage
        from .book import Book
        from .commission import FeeModel
        from .portfolio_adapter import build_portfolio

        cap = float(initial_capital or self._default_capital)
        storage.backtests().create_session(
            session_id, start_date, end_date,
            [f'rule:{self._strategy.name}'],
            notes=notes,
        )

        start = _parse(start_date)
        end = _parse(end_date)
        price_series: dict[str, dict] = {}
        for code in universe:
            price_series[code] = dict(_load_daily_closes(code, start, end))

        days = _trading_days(start_date, end_date)
        book = Book(cash=cap, fee_model=FeeModel())
        daily_records: list[dict] = []
        prev_equity = cap

        for d in days:
            mark_prices = {code: price_series[code].get(d) for code in universe
                           if price_series[code].get(d) is not None}
            for code in universe:
                if code not in mark_prices:
                    past = [p for dt, p in price_series[code].items() if dt <= d]
                    if past:
                        mark_prices[code] = past[-1]
            if not mark_prices:
                continue

            close_history = {}
            for code in universe:
                close_history[code] = [
                    (dt, price_series[code][dt])
                    for dt in sorted(price_series[code])
                    if dt <= d
                ]

            portfolio = build_portfolio(
                cash=book.cash, positions=book.positions_view(),
                mark_prices=mark_prices,
            )
            decisions = self._strategy.on_day(
                date=d, close_history=close_history, portfolio=portfolio,
            )

            trade_count_today = 0
            wins_today = 0
            for dec in decisions:
                action = dec.get('action')
                code = dec.get('code')
                shares = int(dec.get('shares') or 0)
                px = mark_prices.get(code, float(dec.get('price', 0.0)))
                if action == 'buy':
                    fill = book.execute_buy(code, shares=shares, price=px, d=d)
                    if fill:
                        trade_count_today += 1
                elif action == 'sell':
                    avg_before = book.positions_view().get(
                        code, {}).get('avg_price', 0.0)
                    fill = book.execute_sell(code, shares=shares, price=px, d=d)
                    if fill:
                        trade_count_today += 1
                        if px > avg_before:
                            wins_today += 1

            equity = book.equity(mark_prices)
            pnl_pct = ((equity - prev_equity) / prev_equity * 100.0
                       if prev_equity > 0 else 0.0)
            prev_equity = equity
            daily_records.append({
                'date': d, 'pnl_pct': pnl_pct, 'equity': equity,
                'cash': book.cash,
                'trade_count': trade_count_today, 'won': wins_today,
            })

        # Rule strategies don't have a training cutoff → entire window is "clean"
        overall, zones = aggregate(daily_records, cutoff='2099-12-31',
                                   initial_capital=cap)
        from .divergence import compute_divergence
        divergence_flag, _ = compute_divergence(zones)
        gate_input = {
            'sharpe': overall.sharpe,
            'max_drawdown_pct': overall.max_drawdown_pct,
            'trade_count': overall.trade_count,
            'win_rate': overall.win_rate,
            'max_daily_loss_pct': overall.max_daily_loss_pct,
            'clean_zone_days': next(
                (z.days for z in zones if z.zone == 'clean'), 0),
            'divergence_flag': divergence_flag,
        }
        gate = evaluate_quality_gate(gate_input)

        trades_serial = [
            {
                'date': f.date.isoformat(), 'code': f.code,
                'action': f.side, 'shares': f.shares,
                'price': f.price, 'fee': f.fee,
            }
            for f in book.fills
        ]
        daily_records_serial = [
            {
                'date': rec['date'].isoformat(),
                'equity': rec['equity'], 'cash': rec['cash'],
                'pnl_pct': rec['pnl_pct'],
                'trade_count': rec['trade_count'], 'won': rec['won'],
            }
            for rec in daily_records
        ]

        result = BacktestResult(
            id=str(uuid.uuid4()),
            session_id=session_id,
            agent_id='',
            persona_id=None, model_id=None,
            start_date=start_date, end_date=end_date,
            initial_capital=cap, stats=overall, zone_stats=zones,
            quality_gate_label=gate.label,
            quality_gate_criteria=gate.criteria,
            final_equity=prev_equity,
            daily_records=daily_records_serial,
            trades=trades_serial,
            thinking=[],
            kind='rule',
        )
        storage.backtests().insert(result)
        return result
