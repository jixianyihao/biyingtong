from __future__ import annotations

from collections import defaultdict
from math import floor
from typing import Any

from .backtest import _exec_price, _fee, _normalise_bars, _parse_hhmm


def _round_lot(shares: float) -> int:
    return max(0, int(floor(shares / 100.0) * 100))


def _affordable_lot(cash: float, price: float, *, fee_bps: float) -> int:
    if price <= 0:
        return 0
    per_share = price * (1.0 + fee_bps / 10_000.0)
    return _round_lot(cash / per_share)


def _max_drawdown_pct(curve: list[dict[str, Any]]) -> float:
    peak = None
    max_dd = 0.0
    for point in curve:
        equity = float(point['equity'])
        peak = equity if peak is None else max(peak, equity)
        if peak > 0:
            max_dd = min(max_dd, (equity / peak - 1.0) * 100.0)
    return round(max_dd, 4)


def run_t0_portfolio_backtest(
    code: str,
    bars: list[dict[str, Any]],
    *,
    initial_capital: float = 1_000_000.0,
    base_position_pct: float = 0.75,
    t_shares_pct: float = 0.20,
    min_amplitude_pct: float = 1.0,
    high_band: float = 0.82,
    low_band: float = 0.25,
    take_profit_pct: float = 0.8,
    stop_loss_pct: float = 1.2,
    fee_bps: float = 2.5,
    sell_tax_bps: float = 5.0,
    slippage_bps: float = 2.0,
    allow_sell_first: bool = True,
    allow_buy_first: bool = True,
    max_round_trips_per_day: int = 2,
    earliest_entry_time: str = '09:35',
    latest_entry_time: str = '14:00',
) -> dict[str, Any]:
    """Portfolio-level A-share 做T backtest.

    The account starts by buying a base position with base_position_pct of the
    initial capital and keeps the rest as T cash. Every intraday sell consumes
    same-day sellable old shares; same-day buybacks do not restore sellable
    shares until the next trading day.
    """
    rows = _normalise_bars(bars)
    if not rows:
        return {
            'code': code, 'bar_count': 0, 'days': 0,
            'initial_capital': round(initial_capital, 4),
            'final_equity': round(initial_capital, 4),
            'total_return_pct': 0.0, 't_pnl': 0.0,
            'round_trips': 0, 'wins': 0, 'losses': 0,
            'win_rate': 0.0, 'trades': [], 'daily': [],
        }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row['date']].append(row)

    first_price = rows[0]['close']
    last_price = rows[-1]['close']
    buy_exec = _exec_price(first_price, is_buy=True, slippage_bps=slippage_bps)
    base_budget = initial_capital * max(0.0, min(1.0, base_position_pct))
    base_shares = _affordable_lot(base_budget, buy_exec, fee_bps=fee_bps)
    base_cost = buy_exec * base_shares
    base_fee = _fee(buy_exec, base_shares, fee_bps=fee_bps,
                    sell_tax_bps=sell_tax_bps, is_sell=False)
    cash = initial_capital - base_cost - base_fee
    shares = base_shares
    t_shares = _round_lot(base_shares * max(0.0, t_shares_pct))

    all_in_shares = _affordable_lot(initial_capital, buy_exec, fee_bps=fee_bps)
    all_in_cost = all_in_shares * buy_exec
    all_in_fee = _fee(buy_exec, all_in_shares, fee_bps=fee_bps,
                      sell_tax_bps=sell_tax_bps, is_sell=False)
    all_in_cash = initial_capital - all_in_cost - all_in_fee

    earliest_entry = _parse_hhmm(earliest_entry_time, None)
    latest_entry = _parse_hhmm(latest_entry_time, None)

    trades: list[dict[str, Any]] = []
    daily: list[dict[str, Any]] = []
    wins = 0
    losses = 0
    t_pnl = 0.0

    for day in sorted(grouped):
        day_rows = grouped[day]
        day_high = day_rows[0]['high']
        day_low = day_rows[0]['low']
        base_price = day_rows[0]['close']
        sellable_shares = shares
        open_leg: dict[str, Any] | None = None
        day_t_pnl = 0.0
        round_trips_today = 0
        start_equity = cash + shares * base_price

        for idx, row in enumerate(day_rows):
            price = row['close']
            day_high = max(day_high, row['high'])
            day_low = min(day_low, row['low'])
            rng = day_high - day_low
            amplitude_pct = rng / base_price * 100.0 if base_price > 0 else 0.0
            pos = (price - day_low) / rng if rng > 0 else 0.5
            now_time = row['dt'].time()

            if open_leg is None:
                if t_shares <= 0 or round_trips_today >= max_round_trips_per_day:
                    continue
                if not (earliest_entry <= now_time <= latest_entry):
                    continue
                if amplitude_pct < min_amplitude_pct:
                    continue
                if (
                    allow_sell_first
                    and sellable_shares >= t_shares
                    and shares >= t_shares
                    and pos >= high_band
                    and price >= base_price
                ):
                    sell_price = _exec_price(price, is_buy=False,
                                             slippage_bps=slippage_bps)
                    sell_fee = _fee(sell_price, t_shares, fee_bps=fee_bps,
                                    sell_tax_bps=sell_tax_bps, is_sell=True)
                    cash += sell_price * t_shares - sell_fee
                    shares -= t_shares
                    sellable_shares -= t_shares
                    open_leg = {
                        'side': 'sell_first',
                        'price': sell_price,
                        'shares': t_shares,
                        'cash_open': sell_price * t_shares - sell_fee,
                    }
                    trades.append({
                        'ts': row['ts'], 'action': 'sell_t',
                        'shares': t_shares, 'price': round(sell_price, 4),
                        'fee': round(sell_fee, 4),
                    })
                elif allow_buy_first and sellable_shares >= t_shares and pos <= low_band:
                    buy_price = _exec_price(price, is_buy=True,
                                            slippage_bps=slippage_bps)
                    buy_fee = _fee(buy_price, t_shares, fee_bps=fee_bps,
                                   sell_tax_bps=sell_tax_bps, is_sell=False)
                    cost = buy_price * t_shares + buy_fee
                    if cash < cost:
                        continue
                    cash -= cost
                    shares += t_shares
                    open_leg = {
                        'side': 'buy_first',
                        'price': buy_price,
                        'shares': t_shares,
                        'cash_open': -cost,
                    }
                    trades.append({
                        'ts': row['ts'], 'action': 'buy_t',
                        'shares': t_shares, 'price': round(buy_price, 4),
                        'fee': round(buy_fee, 4),
                    })
                continue

            move_pct = ((price - open_leg['price']) / open_leg['price'] * 100.0
                        if open_leg['price'] > 0 else 0.0)
            should_close = False
            reason = ''
            if open_leg['side'] == 'sell_first':
                if -move_pct >= take_profit_pct:
                    should_close, reason = True, 'take_profit'
                elif move_pct >= stop_loss_pct:
                    should_close, reason = True, 'stop_loss'
                elif pos <= low_band:
                    should_close, reason = True, 'near_intraday_low'
            else:
                if move_pct >= take_profit_pct:
                    should_close, reason = True, 'take_profit'
                elif -move_pct >= stop_loss_pct:
                    should_close, reason = True, 'stop_loss'
                elif pos >= high_band:
                    should_close, reason = True, 'near_intraday_high'

            if not should_close and idx != len(day_rows) - 1:
                continue
            if not should_close:
                reason = 'forced_close'

            if open_leg['side'] == 'sell_first':
                buy_price = _exec_price(price, is_buy=True,
                                        slippage_bps=slippage_bps)
                buy_fee = _fee(buy_price, open_leg['shares'], fee_bps=fee_bps,
                               sell_tax_bps=sell_tax_bps, is_sell=False)
                cost = buy_price * open_leg['shares'] + buy_fee
                if cash < cost:
                    reason = 'cash_deficit_for_buyback'
                    continue
                cash -= cost
                shares += open_leg['shares']
                cash_close = -cost
                action = 'buy_back'
                close_price = buy_price
                close_fee = buy_fee
            else:
                if sellable_shares < open_leg['shares']:
                    reason = 'sellable_deficit_for_sellback'
                    continue
                sell_price = _exec_price(price, is_buy=False,
                                         slippage_bps=slippage_bps)
                sell_fee = _fee(sell_price, open_leg['shares'], fee_bps=fee_bps,
                                sell_tax_bps=sell_tax_bps, is_sell=True)
                proceeds = sell_price * open_leg['shares'] - sell_fee
                cash += proceeds
                shares -= open_leg['shares']
                sellable_shares -= open_leg['shares']
                cash_close = proceeds
                action = 'sell_back'
                close_price = sell_price
                close_fee = sell_fee

            pnl = open_leg['cash_open'] + cash_close
            t_pnl += pnl
            day_t_pnl += pnl
            if pnl > 0:
                wins += 1
            else:
                losses += 1
            round_trips_today += 1
            trades.append({
                'ts': row['ts'], 'action': action,
                'shares': open_leg['shares'], 'price': round(close_price, 4),
                'fee': round(close_fee, 4), 'pnl': round(pnl, 4),
                'reason': reason,
            })
            open_leg = None

        close_price = day_rows[-1]['close']
        equity = cash + shares * close_price
        daily.append({
            'date': day,
            'equity': round(equity, 4),
            'cash': round(cash, 4),
            'shares': shares,
            't_pnl': round(day_t_pnl, 4),
            'pnl_pct': round((equity / initial_capital - 1.0) * 100.0, 4),
            'day_return_pct': round(
                (equity / start_equity - 1.0) * 100.0 if start_equity > 0 else 0.0,
                4,
            ),
        })

    final_equity = cash + shares * last_price
    base_hold_equity = (initial_capital - base_cost - base_fee) + base_shares * last_price
    all_in_hold_equity = all_in_cash + all_in_shares * last_price
    round_trips = wins + losses

    return {
        'code': code,
        'bar_count': len(rows),
        'days': len(grouped),
        'initial_capital': round(initial_capital, 4),
        'first_date': rows[0]['ts'],
        'last_date': rows[-1]['ts'],
        'first_price': round(first_price, 4),
        'last_price': round(last_price, 4),
        'base_position_pct': base_position_pct,
        'base_shares': base_shares,
        't_shares': t_shares,
        'initial_cash': round(initial_capital - base_cost - base_fee, 4),
        'final_cash': round(cash, 4),
        'final_shares': shares,
        'final_equity': round(final_equity, 4),
        'total_return_pct': round((final_equity / initial_capital - 1.0) * 100.0, 4),
        'base_hold_equity': round(base_hold_equity, 4),
        'base_hold_return_pct': round((base_hold_equity / initial_capital - 1.0) * 100.0, 4),
        'all_in_hold_equity': round(all_in_hold_equity, 4),
        'all_in_hold_return_pct': round((all_in_hold_equity / initial_capital - 1.0) * 100.0, 4),
        'alpha_vs_base_hold': round(final_equity - base_hold_equity, 4),
        'alpha_vs_all_in_hold': round(final_equity - all_in_hold_equity, 4),
        't_pnl': round(t_pnl, 4),
        'round_trips': round_trips,
        'wins': wins,
        'losses': losses,
        'win_rate': round(wins / round_trips * 100.0, 2) if round_trips else 0.0,
        'max_drawdown_pct': _max_drawdown_pct(daily),
        'params': {
            'base_position_pct': base_position_pct,
            't_shares_pct': t_shares_pct,
            'min_amplitude_pct': min_amplitude_pct,
            'high_band': high_band,
            'low_band': low_band,
            'take_profit_pct': take_profit_pct,
            'stop_loss_pct': stop_loss_pct,
            'fee_bps': fee_bps,
            'sell_tax_bps': sell_tax_bps,
            'slippage_bps': slippage_bps,
            'allow_sell_first': allow_sell_first,
            'allow_buy_first': allow_buy_first,
            'max_round_trips_per_day': max_round_trips_per_day,
            'earliest_entry_time': earliest_entry_time,
            'latest_entry_time': latest_entry_time,
        },
        'daily': daily,
        'trades': trades,
    }
