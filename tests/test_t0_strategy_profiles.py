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

    assert names == ['adaptive_vwap_cost']
    with pytest.raises(KeyError):
        get_t0_strategy_profile('missing')
