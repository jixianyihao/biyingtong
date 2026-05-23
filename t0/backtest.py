from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any


@dataclass
class _Leg:
    side: str
    price: float
    shares: int
    ts: str


def _f(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ts(raw: Any) -> datetime | None:
    text = str(raw or '').strip()
    for width, fmt in (
        (19, '%Y-%m-%d %H:%M:%S'),
        (16, '%Y-%m-%d %H:%M'),
        (10, '%Y-%m-%d'),
    ):
        try:
            return datetime.strptime(text[:width], fmt)
        except ValueError:
            continue
    return None


def _normalise_bars(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for bar in bars or []:
        dt = _ts(bar.get('date'))
        close = _f(bar.get('close'))
        high = _f(bar.get('high'))
        low = _f(bar.get('low'))
        if dt is None or close is None or high is None or low is None:
            continue
        out.append({
            'dt': dt,
            'date': dt.date().isoformat(),
            'ts': dt.strftime('%Y-%m-%d %H:%M:%S'),
            'close': close,
            'high': high,
            'low': low,
        })
    return sorted(out, key=lambda x: x['dt'])


def _parse_hhmm(value: str | None, default: time) -> time:
    if not value:
        return default
    return datetime.strptime(value, '%H:%M').time()


def _fee(price: float, shares: int, *, fee_bps: float, sell_tax_bps: float,
         is_sell: bool) -> float:
    notional = price * shares
    fee = notional * fee_bps / 10_000.0
    if is_sell:
        fee += notional * sell_tax_bps / 10_000.0
    return fee


def _exec_price(price: float, *, is_buy: bool, slippage_bps: float) -> float:
    adj = price * slippage_bps / 10_000.0
    return price + adj if is_buy else price - adj


def _round_trip_pnl(open_leg: _Leg, close_price: float, *,
                    fee_bps: float, sell_tax_bps: float,
                    slippage_bps: float) -> tuple[float, float, float]:
    if open_leg.side == 'sell_first':
        buy_price = _exec_price(close_price, is_buy=True,
                                slippage_bps=slippage_bps)
        sell_fee = _fee(open_leg.price, open_leg.shares, fee_bps=fee_bps,
                        sell_tax_bps=sell_tax_bps, is_sell=True)
        buy_fee = _fee(buy_price, open_leg.shares, fee_bps=fee_bps,
                       sell_tax_bps=sell_tax_bps, is_sell=False)
        pnl = (open_leg.price - buy_price) * open_leg.shares - sell_fee - buy_fee
        return pnl, buy_price, buy_fee

    sell_price = _exec_price(close_price, is_buy=False,
                             slippage_bps=slippage_bps)
    buy_fee = _fee(open_leg.price, open_leg.shares, fee_bps=fee_bps,
                   sell_tax_bps=sell_tax_bps, is_sell=False)
    sell_fee = _fee(sell_price, open_leg.shares, fee_bps=fee_bps,
                    sell_tax_bps=sell_tax_bps, is_sell=True)
    pnl = (sell_price - open_leg.price) * open_leg.shares - buy_fee - sell_fee
    return pnl, sell_price, sell_fee


def run_t0_backtest(
    code: str,
    bars: list[dict[str, Any]],
    *,
    base_shares: int = 1000,
    t_shares: int = 500,
    min_amplitude_pct: float = 1.0,
    high_band: float = 0.82,
    low_band: float = 0.25,
    take_profit_pct: float = 1.0,
    stop_loss_pct: float = 2.0,
    fee_bps: float = 2.5,
    sell_tax_bps: float = 5.0,
    slippage_bps: float = 2.0,
    allow_sell_first: bool = True,
    allow_buy_first: bool = True,
    max_round_trips_per_day: int = 99,
    earliest_entry_time: str = '09:35',
    latest_entry_time: str = '14:30',
) -> dict[str, Any]:
    """Backtest a single-symbol intraday 做T rule on 1m bars.

    The model assumes an existing base position. It only measures incremental
    T-leg PnL, not the mark-to-market PnL of the base holding.
    """
    rows = _normalise_bars(bars)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row['date']].append(row)

    trades: list[dict[str, Any]] = []
    daily: list[dict[str, Any]] = []
    total_pnl = 0.0
    wins = 0
    losses = 0

    shares = min(base_shares, t_shares)
    earliest_entry = _parse_hhmm(earliest_entry_time, time(9, 35))
    latest_entry = _parse_hhmm(latest_entry_time, time(14, 30))
    for day in sorted(grouped):
        day_rows = grouped[day]
        day_high = day_rows[0]['high']
        day_low = day_rows[0]['low']
        base_price = day_rows[0]['close']
        open_leg: _Leg | None = None
        day_pnl = 0.0
        round_trips_today = 0
        sellable_shares = base_shares

        for idx, row in enumerate(day_rows):
            price = row['close']
            day_high = max(day_high, row['high'])
            day_low = min(day_low, row['low'])
            rng = day_high - day_low
            amplitude_pct = rng / base_price * 100.0 if base_price > 0 else 0.0
            pos = (price - day_low) / rng if rng > 0 else 0.5

            if open_leg is None:
                if round_trips_today >= max_round_trips_per_day:
                    continue
                if not (earliest_entry <= row['dt'].time() <= latest_entry):
                    continue
                if amplitude_pct < min_amplitude_pct:
                    continue
                if (
                    allow_sell_first
                    and sellable_shares >= shares
                    and pos >= high_band
                    and price >= base_price
                ):
                    sell_price = _exec_price(price, is_buy=False,
                                             slippage_bps=slippage_bps)
                    sellable_shares -= shares
                    open_leg = _Leg('sell_first', sell_price, shares, row['ts'])
                    trades.append({
                        'ts': row['ts'], 'action': 'sell_t',
                        'shares': shares, 'price': round(sell_price, 4),
                        'reason': 'near_intraday_high',
                    })
                elif allow_buy_first and sellable_shares >= shares and pos <= low_band:
                    buy_price = _exec_price(price, is_buy=True,
                                            slippage_bps=slippage_bps)
                    open_leg = _Leg('buy_first', buy_price, shares, row['ts'])
                    trades.append({
                        'ts': row['ts'], 'action': 'buy_t',
                        'shares': shares, 'price': round(buy_price, 4),
                        'reason': 'near_intraday_low',
                    })
                continue

            move_pct = ((price - open_leg.price) / open_leg.price * 100.0
                        if open_leg.price > 0 else 0.0)
            should_close = False
            reason = ''
            if open_leg.side == 'sell_first':
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

            pnl, close_exec_price, close_fee = _round_trip_pnl(
                open_leg, price, fee_bps=fee_bps,
                sell_tax_bps=sell_tax_bps, slippage_bps=slippage_bps,
            )
            if open_leg.side == 'buy_first':
                sellable_shares -= open_leg.shares
            day_pnl += pnl
            total_pnl += pnl
            if pnl > 0:
                wins += 1
            else:
                losses += 1
            round_trips_today += 1
            trades.append({
                'ts': row['ts'],
                'action': 'buy_back' if open_leg.side == 'sell_first' else 'sell_back',
                'shares': open_leg.shares,
                'price': round(close_exec_price, 4),
                'fee': round(close_fee, 4),
                'pnl': round(pnl, 4),
                'reason': reason,
            })
            open_leg = None

        daily.append({'date': day, 'pnl': round(day_pnl, 4)})

    round_trips = wins + losses
    win_rate = wins / round_trips * 100.0 if round_trips else 0.0
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for row in daily:
        equity += row['pnl']
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)

    return {
        'code': code,
        'bar_count': len(rows),
        'days': len(grouped),
        'round_trips': round_trips,
        'wins': wins,
        'losses': losses,
        'win_rate': round(win_rate, 2),
        'total_pnl': round(total_pnl, 4),
        'avg_daily_pnl': round(total_pnl / len(grouped), 4) if grouped else 0.0,
        'max_drawdown': round(max_drawdown, 4),
        'params': {
            'base_shares': base_shares,
            't_shares': shares,
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
