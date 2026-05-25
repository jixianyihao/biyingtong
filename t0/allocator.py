from __future__ import annotations

from typing import Any

from .backtest import _normalise_bars


BULL_RETURN_THRESHOLD_PCT = 3.0
STRONG_BULL_RETURN_THRESHOLD_PCT = 10.0
BEAR_RETURN_THRESHOLD_PCT = -3.0


def _trend_return_pct(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    first = float(rows[0]['close'])
    last = float(rows[-1]['close'])
    if first <= 0:
        return 0.0
    return round((last / first - 1.0) * 100.0, 4)


def _allocation(mode: str, trend_return_pct: float, reason: str) -> dict[str, Any]:
    if mode == 'bull_high_base':
        return {
            'mode': mode,
            'base_position_pct': 0.90,
            't_shares_pct': 0.15,
            'trend_return_pct': trend_return_pct,
            'reason': reason,
            'strategy_params': {
                'min_amplitude_pct': 1.0,
                'high_band': 0.82,
                'low_band': 0.25,
                'take_profit_pct': 0.8,
                'stop_loss_pct': 1.0,
                'allow_sell_first': False,
                'allow_buy_first': True,
                'max_round_trips_per_day': 1,
                'latest_entry_time': '14:00',
            },
        }
    if mode == 'strong_bull_sell_rebalance':
        return {
            'mode': mode,
            'base_position_pct': 0.99,
            't_shares_pct': 0.25,
            'trend_return_pct': trend_return_pct,
            'reason': reason,
            'strategy_params': {
                'min_amplitude_pct': 1.0,
                'high_band': 0.88,
                'low_band': 0.18,
                'take_profit_pct': 0.8,
                'stop_loss_pct': 1.0,
                'allow_sell_first': True,
                'allow_buy_first': False,
                'max_round_trips_per_day': 1,
                'latest_entry_time': '14:00',
            },
        }
    if mode == 'defensive_low_base':
        return {
            'mode': mode,
            'base_position_pct': 0.50,
            't_shares_pct': 0.15,
            'trend_return_pct': trend_return_pct,
            'reason': reason,
            'strategy_params': {
                'min_amplitude_pct': 1.5,
                'high_band': 0.86,
                'low_band': 0.18,
                'take_profit_pct': 0.8,
                'stop_loss_pct': 0.8,
                'max_round_trips_per_day': 1,
                'latest_entry_time': '13:30',
            },
        }
    return {
        'mode': 'balanced_range',
        'base_position_pct': 0.70,
        't_shares_pct': 0.25,
        'trend_return_pct': trend_return_pct,
        'reason': reason,
        'strategy_params': {
            'min_amplitude_pct': 1.0,
            'high_band': 0.82,
            'low_band': 0.25,
            'take_profit_pct': 0.8,
            'stop_loss_pct': 1.2,
            'max_round_trips_per_day': 1,
            'latest_entry_time': '14:00',
        },
    }


def choose_t0_allocation(
    bars: list[dict[str, Any]],
    *,
    requested_mode: str = 'auto',
) -> dict[str, Any]:
    """Choose base/T capital split for A-share intraday T.

    In an uptrend, the old 70/25 split leaves too much idle cash and can lose
    to simple buy-and-hold. Bull mode keeps higher base exposure and uses a
    smaller T leg to add intraday alpha without fighting the trend.
    """
    rows = _normalise_bars(bars)
    trend = _trend_return_pct(rows)
    mode = (requested_mode or 'auto').strip().lower()

    if mode in {'bull', 'bull_high_base'}:
        return _allocation(
            'bull_high_base',
            trend,
            'explicit bull mode: keep high base exposure, small T leg',
        )
    if mode in {'balanced', 'range', 'balanced_range'}:
        return _allocation(
            'balanced_range',
            trend,
            'explicit balanced mode: reserve cash for active T',
        )
    if mode in {'defensive', 'bear', 'defensive_low_base'}:
        return _allocation(
            'defensive_low_base',
            trend,
            'explicit defensive mode: reduce base exposure',
        )

    if trend >= STRONG_BULL_RETURN_THRESHOLD_PCT:
        return _allocation(
            'strong_bull_sell_rebalance',
            trend,
            f'trend return {trend:.2f}% >= '
            f'{STRONG_BULL_RETURN_THRESHOLD_PCT:.1f}%; strong bull mode keeps '
            'nearly full base exposure and uses sell-first T to harvest '
            'intraday spikes',
        )
    if trend >= BULL_RETURN_THRESHOLD_PCT:
        return _allocation(
            'bull_high_base',
            trend,
            f'trend return {trend:.2f}% >= {BULL_RETURN_THRESHOLD_PCT:.1f}%; '
            'bull mode buys intraday dips only and avoids sell-first trades',
        )
    if trend <= BEAR_RETURN_THRESHOLD_PCT:
        return _allocation(
            'defensive_low_base',
            trend,
            f'trend return {trend:.2f}% <= {BEAR_RETURN_THRESHOLD_PCT:.1f}%',
        )
    return _allocation(
        'balanced_range',
        trend,
        'sideways range: reserve enough cash for buy-first T',
    )
