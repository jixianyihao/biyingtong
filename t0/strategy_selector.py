from __future__ import annotations

from typing import Any, Iterable


def _clamped_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamped_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def t0_strategy_variants(allocation: dict[str, Any]) -> list[dict[str, Any]]:
    defaults = dict(allocation.get('strategy_params') or {})
    base_take_profit = _clamped_float(defaults.get('take_profit_pct'), 0.8)
    base_stop_loss = _clamped_float(defaults.get('stop_loss_pct'), 1.2)
    base_high_band = _clamped_float(defaults.get('high_band'), 0.82)
    base_low_band = _clamped_float(defaults.get('low_band'), 0.25)
    base_rounds = _clamped_int(defaults.get('max_round_trips_per_day'), 1)

    if allocation.get('mode') != 'strong_bull_sell_rebalance':
        default = {'selected_variant': 'default', **defaults}
        active = {
            **defaults,
            'selected_variant': 'cost_basis_active',
            'max_round_trips_per_day': max(2, base_rounds),
            'stop_after_daily_loss': True,
            # Faster profit-taking monetizes smaller intraday reversions into
            # realized T PnL, which is what lowers effective base cost.
            'take_profit_pct': max(0.45, min(base_take_profit, 0.65)),
            'stop_loss_pct': min(base_stop_loss, 1.0),
        }
        guarded = {
            **defaults,
            'selected_variant': 'cost_basis_guarded',
            'max_round_trips_per_day': max(2, base_rounds),
            'stop_after_daily_loss': True,
            # Require a more stretched price before opening; this trades less
            # often but avoids cost-basis damage on noisy, trendless chops.
            'high_band': min(0.92, max(base_high_band, 0.86)),
            'low_band': max(0.12, min(base_low_band, 0.18)),
            'take_profit_pct': max(0.5, min(base_take_profit, 0.7)),
            'stop_loss_pct': min(base_stop_loss, 0.8),
        }
        return [default, active, guarded]

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


def _result_rank(
    result: dict[str, Any],
) -> tuple[bool, bool, float, float, float, float, float]:
    alpha = float(result.get('alpha_vs_all_in_hold') or 0.0)
    cost_reduction = float(result.get('cost_reduction_pct') or 0.0)
    return (
        cost_reduction >= 0.0,
        alpha >= 0.0,
        cost_reduction,
        alpha,
        float(result.get('total_return_pct') or 0.0),
        float(result.get('win_rate') or 0.0),
        float(result.get('max_drawdown_pct') or 0.0),
    )


def choose_best_t0_result(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Choose the least-overfit T0 portfolio result from precomputed variants.

    Lowering the base-position cost is the first objective. Positive alpha
    versus all-in hold stays as a guardrail, then the selector uses T cost
    reduction before raw account return. Drawdown is last because the high base
    position dominates drawdown in this T+0 simulator.
    """
    rows = list(results)
    if not rows:
        raise ValueError('no T0 results to choose from')
    return max(rows, key=_result_rank)
