from __future__ import annotations

from typing import Any, Iterable


def t0_strategy_variants(allocation: dict[str, Any]) -> list[dict[str, Any]]:
    defaults = dict(allocation.get('strategy_params') or {})
    if allocation.get('mode') != 'strong_bull_sell_rebalance':
        return [{'selected_variant': 'default', **defaults}]

    single = {
        **defaults,
        'selected_variant': 'single_round',
        'max_round_trips_per_day': 1,
        'stop_after_daily_loss': False,
    }
    multi = {
        **defaults,
        'selected_variant': 'multi_round_loss_stop',
        'max_round_trips_per_day': max(
            2, int(defaults.get('max_round_trips_per_day') or 3),
        ),
        'stop_after_daily_loss': True,
    }
    return [single, multi]


def _result_rank(result: dict[str, Any]) -> tuple[bool, float, float, float, float]:
    alpha = float(result.get('alpha_vs_all_in_hold') or 0.0)
    return (
        alpha >= 0.0,
        float(result.get('total_return_pct') or 0.0),
        alpha,
        float(result.get('win_rate') or 0.0),
        float(result.get('max_drawdown_pct') or 0.0),
    )


def choose_best_t0_result(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Choose the least-overfit T0 portfolio result from precomputed variants.

    Positive alpha versus all-in hold is the first gate. After that, optimize
    for actual account return, then alpha and win rate. Drawdown is last because
    the high base position dominates drawdown in this T+0 simulator.
    """
    rows = list(results)
    if not rows:
        raise ValueError('no T0 results to choose from')
    return max(rows, key=_result_rank)
