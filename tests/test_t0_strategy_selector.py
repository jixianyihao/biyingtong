from __future__ import annotations

from t0.strategy_selector import (
    choose_best_t0_result,
    choose_best_validated_t0_result,
    t0_strategy_variants,
)


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


def test_choose_best_validated_t0_result_rejects_train_only_cost_trap():
    train_trap = {
        'selected_variant': 'train_only_trap',
        'total_return_pct': 8.0,
        'alpha_vs_all_in_hold': 20_000.0,
        'cost_reduction_pct': 2.4,
        'min_cost_reduction_pct': 0.2,
        'cost_reduction_positive_days_pct': 90.0,
        'win_rate': 70.0,
        'max_drawdown_pct': -8.0,
    }
    train_stable = {
        'selected_variant': 'validation_stable',
        'total_return_pct': 7.0,
        'alpha_vs_all_in_hold': 18_000.0,
        'cost_reduction_pct': 1.5,
        'min_cost_reduction_pct': -0.1,
        'cost_reduction_positive_days_pct': 80.0,
        'win_rate': 65.0,
        'max_drawdown_pct': -8.5,
    }
    validation_trap = {
        **train_trap,
        'cost_reduction_pct': -1.1,
        'min_cost_reduction_pct': -1.4,
        'cost_reduction_positive_days_pct': 35.0,
    }
    validation_stable = {
        **train_stable,
        'cost_reduction_pct': 0.8,
        'min_cost_reduction_pct': -0.2,
        'cost_reduction_positive_days_pct': 70.0,
    }

    selected = choose_best_validated_t0_result(
        [train_trap, train_stable],
        [validation_trap, validation_stable],
    )

    assert selected is train_stable


def test_choose_best_validated_t0_result_falls_back_without_validation():
    train_a = {
        'selected_variant': 'a',
        'cost_reduction_pct': 0.5,
        'alpha_vs_all_in_hold': 1.0,
        'total_return_pct': 1.0,
    }
    train_b = {
        'selected_variant': 'b',
        'cost_reduction_pct': 1.5,
        'alpha_vs_all_in_hold': 1.0,
        'total_return_pct': 1.0,
    }

    assert choose_best_validated_t0_result([train_a, train_b], []) is train_b


def test_choose_best_validated_t0_result_requires_train_and_validation_cost():
    train_negative_validation_good = {
        'selected_variant': 'validation_only',
        'cost_reduction_pct': -0.5,
        'min_cost_reduction_pct': -0.5,
        'cost_reduction_positive_days_pct': 40.0,
        'alpha_vs_all_in_hold': 1.0,
        'total_return_pct': 1.0,
    }
    train_positive_validation_ok = {
        'selected_variant': 'stable',
        'cost_reduction_pct': 0.8,
        'min_cost_reduction_pct': -0.2,
        'cost_reduction_positive_days_pct': 70.0,
        'alpha_vs_all_in_hold': 1.0,
        'total_return_pct': 1.0,
    }
    validation_only = {
        **train_negative_validation_good,
        'cost_reduction_pct': 2.0,
        'min_cost_reduction_pct': -0.1,
    }
    validation_stable = {
        **train_positive_validation_ok,
        'cost_reduction_pct': 0.6,
        'min_cost_reduction_pct': -0.2,
    }

    selected = choose_best_validated_t0_result(
        [train_negative_validation_good, train_positive_validation_ok],
        [validation_only, validation_stable],
    )

    assert selected is train_positive_validation_ok


def test_choose_best_validated_t0_result_falls_back_when_validation_all_fails():
    train_winner = {
        'selected_variant': 'train_winner',
        'cost_reduction_pct': 1.2,
        'min_cost_reduction_pct': -0.2,
        'cost_reduction_positive_days_pct': 80.0,
        'alpha_vs_all_in_hold': 1.0,
        'total_return_pct': 1.0,
    }
    train_loser = {
        'selected_variant': 'train_loser',
        'cost_reduction_pct': 0.7,
        'min_cost_reduction_pct': -0.1,
        'cost_reduction_positive_days_pct': 90.0,
        'alpha_vs_all_in_hold': 1.0,
        'total_return_pct': 1.0,
    }
    validation_winner = {**train_winner, 'cost_reduction_pct': -0.3}
    validation_loser = {**train_loser, 'cost_reduction_pct': -0.1}

    selected = choose_best_validated_t0_result(
        [train_winner, train_loser],
        [validation_winner, validation_loser],
    )

    assert selected is train_winner


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
        'vwap_hybrid_next_bar',
        'vwap_hybrid_guarded_next_bar',
        'vwap_hybrid_profit_guard_next_bar',
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
    assert variants[4]['selected_variant'] == 'vwap_hybrid_next_bar'
    assert variants[4]['signal_mode'] == 'hybrid'
    assert variants[4]['vwap_deviation_pct'] == 0.9
    assert variants[4]['execution_style'] == 'next_bar'
    assert variants[3]['stop_after_cost_floor_pct'] == -1.0
    assert variants[5]['signal_mode'] == 'hybrid'
    assert variants[5]['execution_style'] == 'next_bar'
    assert variants[5]['vwap_deviation_pct'] == 0.7
    assert variants[5]['max_round_trips_per_day'] == 1
    assert variants[5]['take_profit_pct'] == 0.55
    assert variants[5]['stop_loss_pct'] == 0.9
    assert variants[5]['stop_after_daily_loss'] is True
    assert variants[5]['stop_after_cost_floor_pct'] == -1.0
    assert variants[6]['signal_mode'] == 'hybrid'
    assert variants[6]['execution_style'] == 'next_bar'
    assert variants[6]['vwap_deviation_pct'] == 0.9
    assert variants[6]['max_round_trips_per_day'] == 1
    assert variants[6]['take_profit_pct'] == 0.75
    assert variants[6]['stop_loss_pct'] == 1.0
    assert variants[6]['stop_after_daily_loss'] is True
    assert variants[6]['stop_after_cost_floor_pct'] == -1.0
