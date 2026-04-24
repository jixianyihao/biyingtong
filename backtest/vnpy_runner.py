"""VnpyBacktestRunner — LLM-agent backtests via vnpy.BacktestingEngine.

Replaces the hand-rolled BacktestRunner (backtest/runner.py). Reuses
vnpy's position tracking, matching, and calculate_statistics.

Known divergences from legacy runner (documented in design memo):
- Orders fill at NEXT bar open (vnpy default) vs legacy same-day close
- vnpy Sharpe annualizes with 240 trading days vs legacy 252
- No cash tracking per day — reconstructed post-hoc from equity - position value
"""
from __future__ import annotations

import uuid
from datetime import datetime

from backtest.base import BacktestResult, BacktestStats
from backtest.strategy import (
    LLMPortfolioStrategy,
    biyingtong_to_vt,
    vt_to_biyingtong,
)


_DEFAULT_RATE = 3e-4  # 0.03% commission
_DEFAULT_SLIPPAGE = 0
_DEFAULT_SIZE = 1
_DEFAULT_PRICETICK = 0.01


def _parse_date(s: str) -> datetime:
    return datetime.strptime(s, '%Y-%m-%d')


def _compute_win_rate(trades: list) -> float:
    """Count sells that closed at positive pnl vs total sells."""
    cost_basis: dict = {}
    pos: dict = {}
    wins = 0
    total_sells = 0
    for t in trades:
        sym = t.vt_symbol
        if t.direction.value == '多':  # BUY (LONG)
            prev_pos = pos.get(sym, 0)
            prev_cost = cost_basis.get(sym, 0)
            new_pos = prev_pos + t.volume
            cost_basis[sym] = (
                (prev_cost * prev_pos + float(t.price) * t.volume) / new_pos
                if new_pos > 0 else 0
            )
            pos[sym] = new_pos
        else:  # SELL
            total_sells += 1
            if float(t.price) > cost_basis.get(sym, 0):
                wins += 1
            pos[sym] = pos.get(sym, 0) - t.volume
    if total_sells == 0:
        return 0.0
    return 100.0 * wins / total_sells


def _map_stats_to_backtest_stats(stats: dict, trades: list,
                                 daily_results: list,
                                 initial_capital: float) -> BacktestStats:
    """Map vnpy statistics dict → our BacktestStats dataclass.

    Missing fields reconstructed:
    - win_rate: from trade list
    - max_daily_loss_pct: from daily net_pnl series, normalized to prev equity
    """
    sharpe = float(stats.get('sharpe_ratio', 0.0) or 0.0)
    total_return = float(stats.get('total_return', 0.0) or 0.0)
    max_dd_pct = float(stats.get('max_ddpercent', 0.0) or 0.0)
    end_balance = float(
        stats.get('end_balance', initial_capital) or initial_capital
    )
    trade_count = int(stats.get('total_trade_count', 0) or 0)

    win_rate = _compute_win_rate(trades)

    # Max single-day loss pct: normalized to prior equity
    equity = initial_capital
    max_daily_loss = 0.0
    for d in daily_results:
        pnl = float(getattr(d, 'net_pnl', 0.0))
        pct = (pnl / equity) * 100.0 if equity > 0 else 0.0
        if pct < max_daily_loss:
            max_daily_loss = pct
        equity += pnl

    # vnpy's max_ddpercent and total_return are already in percent (not fraction)
    return BacktestStats(
        sharpe=sharpe,
        max_drawdown_pct=max_dd_pct,
        trade_count=trade_count,
        win_rate=win_rate,
        max_daily_loss_pct=max_daily_loss,
        total_return_pct=total_return,
        final_equity=end_balance,
    )


def _daily_results_to_records(daily_results: list, initial_capital: float,
                              trades: list) -> list:
    """Reconstruct our daily_records shape from vnpy DailyResult + trades."""
    trades_by_day: dict = {}
    for t in trades:
        if hasattr(t.datetime, 'strftime'):
            date_key = t.datetime.strftime('%Y-%m-%d')
        else:
            date_key = str(t.datetime)[:10]
        trades_by_day.setdefault(date_key, []).append(t)

    records: list = []
    equity = initial_capital
    cost_basis: dict = {}
    pos: dict = {}

    for d in daily_results:
        pnl = float(getattr(d, 'net_pnl', 0.0))
        prev_equity = equity
        equity += pnl
        pnl_pct = (pnl / prev_equity * 100.0) if prev_equity > 0 else 0.0

        if hasattr(d.date, 'strftime'):
            date_str = d.date.strftime('%Y-%m-%d')
        else:
            date_str = str(d.date)[:10]

        day_trades = trades_by_day.get(date_str, [])
        wins = 0
        for t in day_trades:
            sym = t.vt_symbol
            if t.direction.value == '多':  # BUY
                prev_p = pos.get(sym, 0)
                prev_c = cost_basis.get(sym, 0)
                new_p = prev_p + t.volume
                cost_basis[sym] = (
                    (prev_c * prev_p + float(t.price) * t.volume) / new_p
                    if new_p > 0 else 0
                )
                pos[sym] = new_p
            else:  # SELL
                if float(t.price) > cost_basis.get(sym, 0):
                    wins += 1
                pos[sym] = pos.get(sym, 0) - t.volume

        # Cash ≈ equity - sum(end_pos * close_price) at end-of-day
        position_value = 0.0
        end_poses = getattr(d, 'end_poses', {}) or {}
        close_prices = getattr(d, 'close_prices', {}) or {}
        for vt_sym, p in end_poses.items():
            position_value += float(p) * float(close_prices.get(vt_sym, 0.0))
        cash = equity - position_value

        records.append({
            'date': date_str,
            'equity': equity,
            'cash': cash,
            'pnl_pct': pnl_pct,
            'trade_count': len(day_trades),
            'won': wins,
        })
    return records


def _trades_to_records(trades: list) -> list:
    out = []
    for t in trades:
        sym, _, exch = t.vt_symbol.partition('.')
        code = vt_to_biyingtong(sym, exch)
        if hasattr(t.datetime, 'strftime'):
            date_str = t.datetime.strftime('%Y-%m-%d')
        else:
            date_str = str(t.datetime)[:10]
        action = 'buy' if t.direction.value == '多' else 'sell'
        # vnpy doesn't attach fee per trade; approximate with default rate
        fee = float(t.volume) * float(t.price) * _DEFAULT_RATE
        out.append({
            'date': date_str,
            'code': code,
            'action': action,
            'shares': int(t.volume),
            'price': float(t.price),
            'fee': fee,
        })
    return out


def _thinking_from_strategy(strategy) -> list:
    """Reconstruct thinking entries from strategy.daily_decisions."""
    out = []
    for date_str, decisions in getattr(strategy, 'daily_decisions', []):
        out.append({
            'date': date_str,
            # Strategy doesn't capture per-day reasoning — AgentRunner.last_thinking
            # only holds the most recent day. Leave empty; Task 6 may backfill.
            'reasoning': '',
            'tool_calls': [],
            'decisions': [
                {
                    'action': d.get('action'),
                    'code': d.get('code'),
                    'shares': d.get('shares') or d.get('qty'),
                    'price': d.get('price'),
                    'outcome': 'approved',
                    'reasoning': d.get('reason') or d.get('reasoning'),
                }
                for d in decisions
            ],
        })
    return out


class VnpyBacktestRunner:
    """vnpy.BacktestingEngine-backed runner for LLM agents."""

    def __init__(self, llm, initial_capital: float = 1_000_000.0):
        self._llm = llm
        self._default_capital = initial_capital

    def run(self, *, session_id: str, agent_id: str,
            start_date: str, end_date: str,
            initial_capital: float | None = None,
            universe: list, notes: str | None = None) -> BacktestResult:
        import storage
        from vnpy_portfoliostrategy.backtesting import BacktestingEngine
        from vnpy.trader.constant import Interval

        cap = float(initial_capital or self._default_capital)
        storage.backtests().create_session(
            session_id, start_date, end_date, [agent_id], notes=notes,
        )

        vt_symbols = [biyingtong_to_vt(c) for c in universe]

        engine = BacktestingEngine()
        # silence Chinese stdout logs
        engine.output = lambda *a, **kw: None
        engine.set_parameters(
            vt_symbols=vt_symbols,
            interval=Interval.DAILY,
            start=_parse_date(start_date),
            end=_parse_date(end_date),
            rates={vt: _DEFAULT_RATE for vt in vt_symbols},
            slippages={vt: _DEFAULT_SLIPPAGE for vt in vt_symbols},
            sizes={vt: _DEFAULT_SIZE for vt in vt_symbols},
            priceticks={vt: _DEFAULT_PRICETICK for vt in vt_symbols},
            capital=cap,
        )

        engine.add_strategy(LLMPortfolioStrategy, {
            'agent_id': agent_id,
            'llm': self._llm,
            'initial_capital': cap,
        })

        engine.load_data()
        engine.run_backtesting()

        df = engine.calculate_result()
        trades = engine.get_all_trades() or []
        daily_results = engine.get_all_daily_results() or []

        if df is None or len(df) == 0:
            stats = BacktestStats(
                sharpe=0.0, max_drawdown_pct=0.0, trade_count=0,
                win_rate=0.0, max_daily_loss_pct=0.0,
                total_return_pct=0.0, final_equity=cap,
            )
        else:
            stats_dict = engine.calculate_statistics(df, output=False) or {}
            if stats_dict.get('end_balance', 0) in (0, None) and cap > 0:
                stats = BacktestStats(
                    sharpe=0.0, max_drawdown_pct=0.0,
                    trade_count=int(stats_dict.get('total_trade_count', 0) or 0),
                    win_rate=0.0, max_daily_loss_pct=0.0,
                    total_return_pct=0.0, final_equity=cap,
                )
            else:
                stats = _map_stats_to_backtest_stats(
                    stats_dict, trades, daily_results, cap,
                )

        daily_records = _daily_results_to_records(daily_results, cap, trades)
        trades_records = _trades_to_records(trades)

        # Zone split via legacy aggregate helper (reconstructed daily_records)
        from backtest.stats import aggregate
        from datetime import datetime as _dt
        daily_for_zone = [
            {
                'date': _dt.strptime(rec['date'], '%Y-%m-%d').date(),
                'equity': rec['equity'],
                'pnl_pct': rec['pnl_pct'],
                'trade_count': rec['trade_count'],
                'won': rec['won'],
            }
            for rec in daily_records
        ]

        cutoff = '2099-12-31'
        agent = storage.agents().get(agent_id)
        persona_id = agent.persona_id if agent else None
        model_id = agent.model_id if agent else None
        model = storage.models().get(model_id) if model_id else None
        if model is not None:
            cutoff = model.training_cutoff

        _, zones = aggregate(
            daily_for_zone, cutoff=cutoff, initial_capital=cap,
        )

        # Quality gate
        from backtest.divergence import compute_divergence
        from validation.quality_gate import evaluate_quality_gate
        divergence_flag, _ = compute_divergence(zones)
        gate_input = {
            'sharpe': stats.sharpe,
            'max_drawdown_pct': stats.max_drawdown_pct,
            'trade_count': stats.trade_count,
            'win_rate': stats.win_rate,
            'max_daily_loss_pct': stats.max_daily_loss_pct,
            'clean_zone_days': next(
                (z.days for z in zones if z.zone == 'clean'), 0,
            ),
            'divergence_flag': divergence_flag,
        }
        gate = evaluate_quality_gate(gate_input)

        strategy = getattr(engine, 'strategy', None)
        thinking = _thinking_from_strategy(strategy) if strategy else []

        result = BacktestResult(
            id=str(uuid.uuid4()),
            session_id=session_id, agent_id=agent_id,
            persona_id=persona_id, model_id=model_id,
            start_date=start_date, end_date=end_date,
            initial_capital=cap, stats=stats, zone_stats=zones,
            quality_gate_label=gate.label,
            quality_gate_criteria=gate.criteria,
            final_equity=stats.final_equity,
            daily_records=daily_records,
            trades=trades_records,
            thinking=thinking,
            kind='agent',
        )
        storage.backtests().insert(result)
        return result
