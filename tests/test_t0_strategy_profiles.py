from __future__ import annotations

import pytest

from t0.optimizer import T0OptimizerConstraints
from t0.strategy_profiles import (
    DEFAULT_T0_STRATEGY_PROFILE,
    get_t0_strategy_profile,
    list_t0_strategy_profiles,
)


def test_default_t0_strategy_profile_owns_optimizer_grid_and_constraints():
    profile = DEFAULT_T0_STRATEGY_PROFILE

    assert profile.name == 'adaptive_vwap_cost'
    assert 'adaptive_vwap' in profile.optimizer_grid['signal_mode']
    assert 'hybrid_adaptive' in profile.optimizer_grid['signal_mode']
    assert profile.optimizer_grid['execution_style'] == ['market', 'next_bar']
    assert profile.base_params['initial_capital'] == 1_000_000.0
    assert profile.base_params['base_position_pct'] == 0.75
    assert isinstance(profile.constraints, T0OptimizerConstraints)


def test_t0_strategy_profile_can_merge_base_params_without_mutating_defaults():
    profile = get_t0_strategy_profile('adaptive_vwap_cost')

    merged = profile.build_base_params({
        'take_profit_pct': 0.55,
        'signal_mode': 'adaptive_vwap',
    })

    assert merged['initial_capital'] == 1_000_000.0
    assert merged['take_profit_pct'] == 0.55
    assert merged['signal_mode'] == 'adaptive_vwap'
    assert profile.base_params['take_profit_pct'] == 0.75


def test_t0_strategy_profile_registry_lists_and_rejects_unknown_profiles():
    names = [profile.name for profile in list_t0_strategy_profiles()]

    assert names == [
        'adaptive_vwap_cost',
        'risk_balanced_adaptive_vwap_cost',
        'trend_pullback_t0_cost',
    ]
    with pytest.raises(KeyError):
        get_t0_strategy_profile('missing')


def test_risk_balanced_t0_strategy_profile_sweeps_lower_base_exposure():
    profile = get_t0_strategy_profile('risk_balanced_adaptive_vwap_cost')

    assert profile.base_params['base_position_pct'] == 0.55
    assert profile.optimizer_grid['base_position_pct'] == [0.45, 0.55, 0.65]
    assert profile.optimizer_grid['t_shares_pct'] == [0.12, 0.16, 0.20]
    assert profile.optimizer_grid['execution_style'] == ['next_bar']
    assert profile.constraints.max_full_drawdown_abs_pct == 12.0
    assert profile.constraints.max_validation_drawdown_abs_pct == 12.0


def test_trend_pullback_t0_strategy_profile_avoids_sell_first_in_bull_trends():
    profile = get_t0_strategy_profile('trend_pullback_t0_cost')

    assert profile.base_params['allow_sell_first'] is False
    assert profile.base_params['allow_buy_first'] is True
    assert profile.optimizer_grid['base_position_pct'] == [0.55, 0.65, 0.75]
    assert profile.optimizer_grid['signal_mode'] == ['adaptive_vwap', 'hybrid_adaptive']
    assert profile.optimizer_grid['execution_style'] == ['next_bar']
    assert profile.constraints.min_full_alpha_vs_all_in is None
    assert profile.constraints.min_validation_alpha_vs_all_in is None
    assert profile.constraints.max_full_drawdown_abs_pct == 16.0
