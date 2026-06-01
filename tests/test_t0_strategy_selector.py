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
    assert variants[1]['max_round_trips_per_day'] == 3
    assert variants[1]['stop_after_daily_loss'] is True
