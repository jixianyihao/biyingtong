from __future__ import annotations

from itertools import product
from typing import Any, Iterable

from .backtest import run_t0_backtest


def _bar_day(bar: dict[str, Any]) -> str | None:
    raw = str(bar.get('date') or '').strip()
    return raw[:10] if len(raw) >= 10 else None


def _split_bars_by_date(
    bars: list[dict[str, Any]],
    *,
    train_fraction: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    days = sorted({d for bar in bars if (d := _bar_day(bar))})
    if len(days) < 2:
        return list(bars), []
    split_idx = int(len(days) * train_fraction)
    split_idx = max(1, min(len(days) - 1, split_idx))
    train_days = set(days[:split_idx])
    train = [bar for bar in bars if _bar_day(bar) in train_days]
    test = [bar for bar in bars if _bar_day(bar) not in train_days]
    return train, test


def default_param_grid() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    modes = {
        'sell_first_only': (True, False),
        'both': (True, True),
    }
    for (
        mode,
        min_amp,
        high_band,
        low_band,
        take_profit,
        stop_loss,
        max_trips,
        latest_entry,
    ) in product(
        modes.keys(),
        [1.0, 1.5, 2.0],
        [0.82, 0.88],
        [0.18, 0.25],
        [0.8, 1.2],
        [1.2, 2.0],
        [1, 2, 3],
        ['14:00', '14:30'],
    ):
        allow_sell, allow_buy = modes[mode]
        rows.append({
            'mode': mode,
            'min_amplitude_pct': min_amp,
            'high_band': high_band,
            'low_band': low_band,
            'take_profit_pct': take_profit,
            'stop_loss_pct': stop_loss,
            'max_round_trips_per_day': max_trips,
            'latest_entry_time': latest_entry,
            'allow_sell_first': allow_sell,
            'allow_buy_first': allow_buy,
        })
    return rows


def _profit_factor(result: dict[str, Any]) -> float:
    gains = 0.0
    losses = 0.0
    for trade in result.get('trades', []):
        pnl = trade.get('pnl')
        if pnl is None:
            continue
        if pnl > 0:
            gains += pnl
        elif pnl < 0:
            losses += abs(pnl)
    if losses == 0:
        return 999.0 if gains > 0 else 0.0
    return gains / losses


def _rank_score(result: dict[str, Any]) -> float:
    # Penalize drawdown and tiny sample sizes. This is for ranking candidates,
    # not a claim of statistical significance.
    pnl = float(result.get('total_pnl', 0.0))
    dd = abs(float(result.get('max_drawdown', 0.0)))
    trips = int(result.get('round_trips', 0))
    sample_penalty = max(0, 8 - trips) * 200.0
    return pnl - dd * 0.35 - sample_penalty


def run_grid_search(
    code: str,
    bars: list[dict[str, Any]],
    *,
    param_grid: Iterable[dict[str, Any]] | None = None,
    top_n: int = 20,
    base_shares: int = 1000,
    t_shares: int = 500,
    fee_bps: float = 2.5,
    sell_tax_bps: float = 5.0,
    slippage_bps: float = 2.0,
    train_fraction: float = 0.67,
) -> list[dict[str, Any]]:
    candidates = param_grid if param_grid is not None else default_param_grid()
    train_bars, test_bars = _split_bars_by_date(
        bars,
        train_fraction=train_fraction,
    )
    ranked: list[dict[str, Any]] = []
    for params in candidates:
        mode = params.get('mode', 'custom')
        kwargs = {k: v for k, v in params.items() if k != 'mode'}
        common = {
            'base_shares': base_shares,
            't_shares': t_shares,
            'fee_bps': fee_bps,
            'sell_tax_bps': sell_tax_bps,
            'slippage_bps': slippage_bps,
            **kwargs,
        }
        result = run_t0_backtest(code, bars, **common)
        train_result = run_t0_backtest(code, train_bars, **common)
        test_result = run_t0_backtest(code, test_bars, **common) if test_bars else {
            'days': 0, 'round_trips': 0, 'win_rate': 0.0,
            'total_pnl': 0.0, 'max_drawdown': 0.0,
        }
        robust = (
            train_result['round_trips'] > 0 and test_result['round_trips'] > 0
            and train_result['total_pnl'] > 0 and test_result['total_pnl'] > 0
        )
        robust_score = _rank_score(result)
        if robust:
            robust_score += float(test_result['total_pnl']) * 0.35
        else:
            robust_score -= 1_500.0
        row = {
            'rank_score': round(robust_score, 4),
            'profit_factor': round(_profit_factor(result), 3),
            'mode': mode,
            'total_pnl': result['total_pnl'],
            'max_drawdown': result['max_drawdown'],
            'round_trips': result['round_trips'],
            'win_rate': result['win_rate'],
            'days': result['days'],
            'bar_count': result['bar_count'],
            'train_days': train_result['days'],
            'test_days': test_result['days'],
            'train_total_pnl': train_result['total_pnl'],
            'test_total_pnl': test_result['total_pnl'],
            'train_round_trips': train_result['round_trips'],
            'test_round_trips': test_result['round_trips'],
            'test_win_rate': test_result['win_rate'],
            'test_max_drawdown': test_result['max_drawdown'],
            'robust': robust,
            'params': {'mode': mode, **kwargs},
        }
        ranked.append(row)
    ranked.sort(
        key=lambda x: (
            x['rank_score'],
            x['total_pnl'],
            x['profit_factor'],
            x['round_trips'],
        ),
        reverse=True,
    )
    return ranked[:top_n]
