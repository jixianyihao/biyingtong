"""BacktestRunner — orchestrates agent decisions over a date range."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from agents.runner import AgentRunner
from validation.quality_gate import evaluate_quality_gate

from .base import BacktestResult
from .portfolio_adapter import build_portfolio
from .stats import aggregate


def _load_daily_closes(code: str, start: date, end: date) -> list:
    """Returns [(date, close), ...] ascending for one stock."""
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
    return storage.calendar().get_trading_days(
        _parse(start), _parse(end),
    )


def _parse(s: str) -> date:
    return datetime.strptime(s, '%Y-%m-%d').date()


class BacktestRunner:
    def __init__(self, llm, initial_capital: float = 1_000_000.0):
        self._llm = llm
        self._default_capital = initial_capital

    def run(self, *, session_id: str, agent_id: str,
            start_date: str, end_date: str,
            initial_capital: float | None = None,
            universe: list[str],
            notes: str | None = None) -> BacktestResult:
        import storage

        cap = float(initial_capital or self._default_capital)
        storage.backtests().create_session(
            session_id, start_date, end_date, [agent_id], notes=notes,
        )

        # Load price series per symbol once; use forward-fill for missing days
        start = _parse(start_date)
        end = _parse(end_date)
        price_series: dict[str, dict] = {}
        for code in universe:
            price_series[code] = dict(_load_daily_closes(code, start, end))

        days = _trading_days(start_date, end_date)
        agent = storage.agents().get(agent_id)
        persona_id = agent.persona_id if agent else None
        model_id = agent.model_id if agent else None

        runner = AgentRunner(llm=self._llm)
        from .book import Book
        from .commission import FeeModel
        book = Book(cash=cap, fee_model=FeeModel())
        daily_records: list[dict] = []
        prev_equity = cap

        for d in days:
            mark_prices = {code: price_series[code].get(d) for code in universe
                           if price_series[code].get(d) is not None}
            # Fallback: use last seen close if today missing
            for code in universe:
                if code not in mark_prices:
                    past = [p for dt, p in price_series[code].items() if dt <= d]
                    if past:
                        mark_prices[code] = past[-1]
            if not mark_prices:
                continue

            portfolio = build_portfolio(
                cash=book.cash, positions=book.positions_view(),
                mark_prices=mark_prices,
            )
            decisions = runner.run_day(
                agent_id=agent_id, date=d.strftime('%Y-%m-%d'),
                portfolio=portfolio, market_context={},
                mark_prices=mark_prices,
            )

            # Apply decisions to the book at today's close
            trade_count_today = 0
            wins_today = 0
            for dec in decisions:
                action = dec.get('action')
                code = dec.get('code')
                shares = int(dec.get('shares') or dec.get('qty') or 0)
                px = mark_prices.get(code, float(dec.get('price', 0.0)))
                if action == 'buy':
                    fill = book.execute_buy(code, shares=shares,
                                            price=px, d=d)
                    if fill:
                        trade_count_today += 1
                elif action == 'sell':
                    # Track win via avg price before sell removes tranches
                    avg_before = book.positions_view().get(
                        code, {}).get('avg_price', 0.0)
                    fill = book.execute_sell(code, shares=shares,
                                             price=px, d=d)
                    if fill:
                        trade_count_today += 1
                        if px > avg_before:
                            wins_today += 1

            # Mark-to-market equity
            equity = book.equity(mark_prices)
            pnl_pct = ((equity - prev_equity) / prev_equity * 100.0
                       if prev_equity > 0 else 0.0)
            prev_equity = equity

            daily_records.append({
                'date': d, 'pnl_pct': pnl_pct, 'equity': equity,
                'trade_count': trade_count_today, 'won': wins_today,
            })

        # Aggregate + quality gate
        cutoff = '2099-12-31'
        model = storage.models().get(model_id) if model_id else None
        if model is not None:
            cutoff = model.training_cutoff
        elif model_id:
            # Non-empty model_id but not in registry → log warning
            from validation.base import AuditEntry
            # Dedup: skip if we already warned about this exact (agent, model)
            prior = storage.audit().query_by_agent(agent_id, limit=200)
            already_warned = any(
                r.get('kind') == 'warning'
                and r.get('details', {}).get('kind') == 'unknown_model'
                and r.get('details', {}).get('model_id') == model_id
                for r in prior
            )
            if not already_warned:
                storage.audit().log(AuditEntry(
                    kind='warning', agent_id=agent_id,
                    persona_id=persona_id, model_id=model_id,
                    details={'kind': 'unknown_model', 'model_id': model_id},
                ))

        overall, zones = aggregate(daily_records, cutoff=cutoff,
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

        result = BacktestResult(
            id=str(uuid.uuid4()),
            session_id=session_id, agent_id=agent_id,
            persona_id=persona_id, model_id=model_id,
            start_date=start_date, end_date=end_date,
            initial_capital=cap, stats=overall, zone_stats=zones,
            quality_gate_label=gate.label,
            quality_gate_criteria=gate.criteria,
            final_equity=prev_equity,
        )
        storage.backtests().insert(result)
        return result
