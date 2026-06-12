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
    base_cost_floor = _clamped_float(
        defaults.get('stop_after_cost_floor_pct'), -2.0,
    )

    if allocation.get('mode') != 'strong_bull_sell_rebalance':
        default = {
            'selected_variant': 'default',
            'stop_after_cost_floor_pct': base_cost_floor,
            **defaults,
        }
        active = {
            **defaults,
            'selected_variant': 'cost_basis_active',
            'max_round_trips_per_day': max(2, base_rounds),
            'stop_after_daily_loss': True,
            'stop_after_cost_floor_pct': -1.5,
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
            'stop_after_cost_floor_pct': -0.8,
            # Require a more stretched price before opening; this trades less
            # often but avoids cost-basis damage on noisy, trendless chops.
            'high_band': min(0.92, max(base_high_band, 0.86)),
            'low_band': max(0.12, min(base_low_band, 0.18)),
            'take_profit_pct': max(0.5, min(base_take_profit, 0.7)),
            'stop_loss_pct': min(base_stop_loss, 0.8),
        }
        vwap_hybrid = {
            **defaults,
            'selected_variant': 'vwap_hybrid',
            'signal_mode': 'hybrid',
            'vwap_deviation_pct': 0.9,
            'max_round_trips_per_day': max(2, base_rounds),
            'stop_after_daily_loss': True,
            'stop_after_cost_floor_pct': -1.0,
            'take_profit_pct': max(0.45, min(base_take_profit, 0.7)),
            'stop_loss_pct': min(base_stop_loss, 0.9),
        }
        vwap_hybrid_next_bar = {
            **vwap_hybrid,
            'selected_variant': 'vwap_hybrid_next_bar',
            'execution_style': 'next_bar',
        }
        vwap_hybrid_guarded_next_bar = {
            **vwap_hybrid_next_bar,
            'selected_variant': 'vwap_hybrid_guarded_next_bar',
            # Real LC1 sweep on 300951.SZ favored this as a validation-stable
            # defensive path: lower full-period cost cut, but much better
            # validation cost path and worst-fold drawdown of cost basis.
            'vwap_deviation_pct': 0.7,
            'max_round_trips_per_day': 1,
            'take_profit_pct': 0.55,
            'stop_loss_pct': 0.9,
            'stop_after_cost_floor_pct': -1.0,
            'stop_after_daily_loss': True,
        }
        vwap_hybrid_profit_guard_next_bar = {
            **vwap_hybrid_next_bar,
            'selected_variant': 'vwap_hybrid_profit_guard_next_bar',
            # Optimizer-backed 300951.SZ LC1 result:
            # cost +1.5638%, validation cost +1.2514%, worst fold -0.3217%.
            'vwap_deviation_pct': 0.9,
            'max_round_trips_per_day': 1,
            'take_profit_pct': 0.75,
            'stop_loss_pct': 1.0,
            'stop_after_cost_floor_pct': -1.0,
            'stop_after_daily_loss': True,
        }
        return [
            default,
            active,
            guarded,
            vwap_hybrid,
            vwap_hybrid_next_bar,
            vwap_hybrid_guarded_next_bar,
            vwap_hybrid_profit_guard_next_bar,
        ]

    single = {
        **defaults,
        'selected_variant': 'single_round',
        'max_round_trips_per_day': 1,
        'stop_after_daily_loss': False,
        'stop_after_cost_floor_pct': base_cost_floor,
    }
    multi = {
        **defaults,
        'selected_variant': 'multi_round_loss_stop',
        'max_round_trips_per_day': max(
            2, int(defaults.get('max_round_trips_per_day') or 3),
        ),
        'stop_after_daily_loss': True,
        'stop_after_cost_floor_pct': -1.0,
    }
    return [single, multi]


def _result_rank(
    result: dict[str, Any],
) -> tuple[bool, bool, float, float, float, float, float, float, float]:
    alpha = float(result.get('alpha_vs_all_in_hold') or 0.0)
    cost_reduction = float(result.get('cost_reduction_pct') or 0.0)
    min_cost_reduction = float(result.get('min_cost_reduction_pct') or 0.0)
    positive_days = float(result.get('cost_reduction_positive_days_pct') or 0.0)
    return (
        cost_reduction >= 0.0,
        alpha >= 0.0,
        cost_reduction,
        min_cost_reduction,
        positive_days,
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


def _validated_result_rank(
    train_result: dict[str, Any],
    validation_result: dict[str, Any] | None,
) -> tuple[float, float, float, float, float, float, float]:
    """Rank a train-selected variant with out-of-sample cost-basis evidence."""
    if validation_result is None:
        return (
            float(train_result.get('cost_reduction_pct') or 0.0),
            float(train_result.get('cost_reduction_pct') or 0.0),
            float(train_result.get('min_cost_reduction_pct') or 0.0),
            float(train_result.get('cost_reduction_positive_days_pct') or 0.0),
            float(train_result.get('cost_reduction_positive_days_pct') or 0.0),
            float(train_result.get('alpha_vs_all_in_hold') or 0.0),
            float(train_result.get('total_return_pct') or 0.0),
        )

    validation_cost = float(validation_result.get('cost_reduction_pct') or 0.0)
    validation_min = float(
        validation_result.get('min_cost_reduction_pct') or 0.0,
    )
    validation_positive_days = float(
        validation_result.get('cost_reduction_positive_days_pct') or 0.0,
    )
    train_cost = float(train_result.get('cost_reduction_pct') or 0.0)
    train_min = float(train_result.get('min_cost_reduction_pct') or 0.0)
    alpha = float(train_result.get('alpha_vs_all_in_hold') or 0.0)
    return (
        min(train_cost, validation_cost),
        train_cost + validation_cost,
        min(train_min, validation_min),
        validation_positive_days,
        float(train_result.get('cost_reduction_positive_days_pct') or 0.0),
        alpha,
        float(train_result.get('total_return_pct') or 0.0),
    )


def choose_best_validated_t0_result(
    train_results: Iterable[dict[str, Any]],
    validation_results: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Choose a T0 variant using train data plus validation cost path.

    The endpoint still returns the selected training result so callers can reuse
    its variant and params, but variants that damage validation cost basis are
    ranked below slightly weaker train winners.
    """
    train_rows = list(train_results)
    if not train_rows:
        raise ValueError('no T0 results to choose from')
    validation_by_variant = {
        row.get('selected_variant'): row
        for row in validation_results
        if row.get('selected_variant') is not None
    }
    if not validation_by_variant:
        return choose_best_t0_result(train_rows)
    stable_rows = [
        row for row in train_rows
        if (
            float(row.get('cost_reduction_pct') or 0.0) >= 0.0 and
            (validation := validation_by_variant.get(
                row.get('selected_variant'),
            )) is not None and
            float(validation.get('cost_reduction_pct') or 0.0) >= 0.0 and
            float(validation.get('min_cost_reduction_pct') or 0.0) >= -1.0
        )
    ]
    if not stable_rows:
        return choose_best_t0_result(train_rows)
    return max(
        stable_rows,
        key=lambda row: _validated_result_rank(
            row,
            validation_by_variant.get(row.get('selected_variant')),
        ),
    )
