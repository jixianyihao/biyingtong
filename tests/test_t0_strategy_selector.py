from __future__ import annotations

from t0.strategy_selector import choose_best_t0_result, t0_strategy_variants


def test_choose_best_t0_result_prefers_positive_alpha_over_overtrading():
    single = {
        'selected_variant': 'single_round',
        'total_return_pct': 13.75,
        'alpha_vs_all_in_hold': 10_000.0,
        'win_rate': 65.0,
        'max_drawdown_pct': -25.0,
    }
    multi = {
        'selected_variant': 'multi_round_loss_stop',
        'total_return_pct': 11.25,
        'alpha_vs_all_in_hold': -14_000.0,
        'win_rate': 55.0,
        'max_drawdown_pct': -25.4,
    }

    assert choose_best_t0_result([multi, single]) is single


def test_choose_best_t0_result_uses_multi_when_it_improves_return_and_alpha():
    single = {
        'selected_variant': 'single_round',
        'total_return_pct': 16.74,
        'alpha_vs_all_in_hold': 31_000.0,
        'win_rate': 75.0,
        'max_drawdown_pct': -15.0,
    }
    multi = {
        'selected_variant': 'multi_round_loss_stop',
        'total_return_pct': 16.80,
        'alpha_vs_all_in_hold': 32_000.0,
        'win_rate': 70.0,
        'max_drawdown_pct': -15.3,
    }

    assert choose_best_t0_result([single, multi]) is multi


def test_choose_best_t0_result_prefers_cost_reduction_over_raw_return():
    high_return_low_cost_cut = {
        'selected_variant': 'chases_raw_return',
        'total_return_pct': 18.0,
        'alpha_vs_all_in_hold': 40_000.0,
        'cost_reduction_pct': 0.8,
        'win_rate': 80.0,
        'max_drawdown_pct': -12.0,
    }
    lower_return_better_cost_cut = {
        'selected_variant': 'lowers_cost_basis',
        'total_return_pct': 12.0,
        'alpha_vs_all_in_hold': 30_000.0,
        'cost_reduction_pct': 2.5,
        'win_rate': 70.0,
        'max_drawdown_pct': -13.0,
    }

    assert choose_best_t0_result([
        high_return_low_cost_cut,
        lower_return_better_cost_cut,
    ]) is lower_return_better_cost_cut


def test_choose_best_t0_result_prefers_smoother_cost_path_on_tie():
    choppy = {
        'selected_variant': 'choppy_cost_path',
        'total_return_pct': 14.0,
        'alpha_vs_all_in_hold': 30_000.0,
        'cost_reduction_pct': 2.0,
        'min_cost_reduction_pct': -2.0,
        'cost_reduction_positive_days_pct': 55.0,
        'win_rate': 80.0,
        'max_drawdown_pct': -10.0,
    }
    smoother = {
        'selected_variant': 'smoother_cost_path',
        'total_return_pct': 12.0,
        'alpha_vs_all_in_hold': 30_000.0,
        'cost_reduction_pct': 2.0,
        'min_cost_reduction_pct': -0.2,
        'cost_reduction_positive_days_pct': 90.0,
        'win_rate': 65.0,
        'max_drawdown_pct': -11.0,
    }

    assert choose_best_t0_result([choppy, smoother]) is smoother


def test_t0_strategy_variants_for_strong_bull_include_single_and_multi():
    allocation = {
        'mode': 'strong_bull_sell_rebalance',
        'strategy_params': {
            'max_round_trips_per_day': 3,
            'stop_after_daily_loss': True,
            'high_band': 0.88,
        },
    }

    variants = t0_strategy_variants(allocation)

    assert [v['selected_variant'] for v in variants] == [
        'single_round',
        'multi_round_loss_stop',
    ]
    assert variants[0]['max_round_trips_per_day'] == 1
    assert variants[0]['stop_after_daily_loss'] is False
    assert variants[0]['stop_after_cost_floor_pct'] == -2.0
    assert variants[1]['max_round_trips_per_day'] == 3
    assert variants[1]['stop_after_daily_loss'] is True
    assert variants[1]['stop_after_cost_floor_pct'] == -1.0


def test_t0_strategy_variants_for_balanced_include_cost_basis_choices():
    allocation = {
        'mode': 'balanced_range',
        'strategy_params': {
            'max_round_trips_per_day': 1,
            'take_profit_pct': 0.8,
            'stop_loss_pct': 1.2,
            'high_band': 0.82,
            'low_band': 0.25,
        },
    }

    variants = t0_strategy_variants(allocation)

    assert [v['selected_variant'] for v in variants] == [
        'default',
        'cost_basis_active',
        'cost_basis_guarded',
        'vwap_hybrid',
    ]
    assert variants[1]['max_round_trips_per_day'] >= 2
    assert variants[1]['stop_after_daily_loss'] is True
    assert variants[1]['take_profit_pct'] < 0.8
    assert variants[2]['stop_loss_pct'] < 1.2
    assert variants[2]['high_band'] > 0.82
    assert variants[0]['stop_after_cost_floor_pct'] == -2.0
    assert variants[1]['stop_after_cost_floor_pct'] == -1.5
    assert variants[2]['stop_after_cost_floor_pct'] == -0.8
    assert variants[3]['signal_mode'] == 'hybrid'
    assert variants[3]['vwap_deviation_pct'] == 0.9
    assert variants[3]['stop_after_cost_floor_pct'] == -1.0
