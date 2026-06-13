from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .optimizer import T0OptimizerConstraints


@dataclass(frozen=True)
class T0StrategyProfile:
    """Research-facing bundle for a pluggable T0 strategy family.

    A profile owns the defaults, optimizer grid, and validation constraints for
    one algorithm family. Execution stays in ``portfolio.py``; this module only
    describes which knobs a research run is allowed to sweep.
    """

    name: str
    display_name: str
    description: str
    base_params: dict[str, Any]
    optimizer_grid: dict[str, list[Any]]
    constraints: T0OptimizerConstraints

    def build_base_params(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        return {**self.base_params, **(overrides or {})}


ADAPTIVE_VWAP_COST_PROFILE = T0StrategyProfile(
    name='adaptive_vwap_cost',
    display_name='Adaptive VWAP Cost Reduction',
    description=(
        'A-share T+1 做T profile focused on gradually reducing the base '
        'position cost through adaptive VWAP/band mean-reversion signals.'
    ),
    base_params={
        'initial_capital': 1_000_000.0,
        'base_position_pct': 0.75,
        't_shares_pct': 0.20,
        'min_amplitude_pct': 1.0,
        'high_band': 0.82,
        'low_band': 0.25,
        'take_profit_pct': 0.75,
        'stop_loss_pct': 1.0,
        'allow_sell_first': True,
        'allow_buy_first': True,
        'stop_after_daily_loss': True,
    },
    optimizer_grid={
        'take_profit_pct': [0.55, 0.65, 0.75],
        'stop_loss_pct': [0.75, 0.9, 1.0],
        'vwap_deviation_pct': [0.7, 0.9],
        'stop_after_cost_floor_pct': [-0.75, -1.0, -1.25],
        'max_round_trips_per_day': [1, 2],
        'latest_entry_time': ['13:30', '14:00'],
        'signal_mode': ['band', 'hybrid', 'adaptive_vwap', 'hybrid_adaptive'],
        'vwap_zscore_threshold': [1.2, 1.5, 1.8],
        'execution_style': ['market', 'next_bar'],
    },
    constraints=T0OptimizerConstraints(
        min_full_cost_reduction_pct=0.0,
        min_validation_cost_reduction_pct=0.0,
        min_full_round_trips=1,
        min_validation_round_trips=1,
        min_fold_cost_reduction_pct=-2.0,
        min_fold_min_cost_reduction_pct=-2.0,
        min_full_alpha_vs_all_in=0.0,
        min_validation_alpha_vs_all_in=0.0,
        max_full_drawdown_abs_pct=20.0,
        max_validation_drawdown_abs_pct=20.0,
    ),
)

RISK_BALANCED_ADAPTIVE_VWAP_COST_PROFILE = T0StrategyProfile(
    name='risk_balanced_adaptive_vwap_cost',
    display_name='Risk-Balanced Adaptive VWAP Cost Reduction',
    description=(
        'Lower-base-position T0 profile for candidates where the main risk is '
        'base exposure drawdown. It still optimizes cost reduction, but sweeps '
        'base/T capital allocation and uses next-bar execution only.'
    ),
    base_params={
        'initial_capital': 1_000_000.0,
        'base_position_pct': 0.55,
        't_shares_pct': 0.16,
        'min_amplitude_pct': 1.0,
        'high_band': 0.84,
        'low_band': 0.22,
        'take_profit_pct': 0.65,
        'stop_loss_pct': 0.85,
        'allow_sell_first': True,
        'allow_buy_first': True,
        'stop_after_daily_loss': True,
    },
    optimizer_grid={
        'base_position_pct': [0.45, 0.55, 0.65],
        't_shares_pct': [0.12, 0.16, 0.20],
        'take_profit_pct': [0.55, 0.65, 0.75],
        'stop_loss_pct': [0.65, 0.75, 0.9],
        'vwap_deviation_pct': [0.7, 0.9],
        'stop_after_cost_floor_pct': [-0.5, -0.75, -1.0],
        'max_round_trips_per_day': [1, 2],
        'latest_entry_time': ['13:30', '14:00'],
        'signal_mode': ['adaptive_vwap', 'hybrid_adaptive'],
        'vwap_zscore_threshold': [1.5, 1.8],
        'execution_style': ['next_bar'],
    },
    constraints=T0OptimizerConstraints(
        min_full_cost_reduction_pct=0.0,
        min_validation_cost_reduction_pct=0.0,
        min_full_round_trips=1,
        min_validation_round_trips=1,
        min_fold_cost_reduction_pct=-1.2,
        min_fold_min_cost_reduction_pct=-1.2,
        min_full_alpha_vs_all_in=None,
        min_validation_alpha_vs_all_in=None,
        max_full_drawdown_abs_pct=12.0,
        max_validation_drawdown_abs_pct=12.0,
    ),
)

TREND_PULLBACK_T0_COST_PROFILE = T0StrategyProfile(
    name='trend_pullback_t0_cost',
    display_name='Trend Pullback T0 Cost Reduction',
    description=(
        'Bull-trend T0 profile: keep a meaningful base position, buy intraday '
        'pullbacks first, then sell old shares into rebound. Sell-first is '
        'disabled to reduce the risk of selling out early on trend days.'
    ),
    base_params={
        'initial_capital': 1_000_000.0,
        'base_position_pct': 0.65,
        't_shares_pct': 0.12,
        'min_amplitude_pct': 1.0,
        'high_band': 0.88,
        'low_band': 0.30,
        'take_profit_pct': 0.55,
        'stop_loss_pct': 0.75,
        'allow_sell_first': False,
        'allow_buy_first': True,
        'stop_after_daily_loss': True,
    },
    optimizer_grid={
        'base_position_pct': [0.55, 0.65, 0.75],
        't_shares_pct': [0.08, 0.12, 0.16],
        'take_profit_pct': [0.45, 0.55, 0.65],
        'stop_loss_pct': [0.55, 0.75, 0.9],
        'vwap_deviation_pct': [0.6, 0.8],
        'stop_after_cost_floor_pct': [-0.5, -0.75, -1.0],
        'max_round_trips_per_day': [1, 2],
        'latest_entry_time': ['13:30', '14:00'],
        'signal_mode': ['adaptive_vwap', 'hybrid_adaptive'],
        'vwap_zscore_threshold': [1.2, 1.5],
        'execution_style': ['next_bar'],
    },
    constraints=T0OptimizerConstraints(
        min_full_cost_reduction_pct=0.0,
        min_validation_cost_reduction_pct=0.0,
        min_full_round_trips=1,
        min_validation_round_trips=1,
        min_fold_cost_reduction_pct=-1.5,
        min_fold_min_cost_reduction_pct=-1.5,
        min_full_alpha_vs_all_in=None,
        min_validation_alpha_vs_all_in=None,
        max_full_drawdown_abs_pct=16.0,
        max_validation_drawdown_abs_pct=16.0,
    ),
)

DEFAULT_T0_STRATEGY_PROFILE = ADAPTIVE_VWAP_COST_PROFILE

_PROFILES = {
    ADAPTIVE_VWAP_COST_PROFILE.name: ADAPTIVE_VWAP_COST_PROFILE,
    RISK_BALANCED_ADAPTIVE_VWAP_COST_PROFILE.name: (
        RISK_BALANCED_ADAPTIVE_VWAP_COST_PROFILE
    ),
    TREND_PULLBACK_T0_COST_PROFILE.name: TREND_PULLBACK_T0_COST_PROFILE,
}


def list_t0_strategy_profiles() -> list[T0StrategyProfile]:
    return list(_PROFILES.values())


def get_t0_strategy_profile(name: str | None = None) -> T0StrategyProfile:
    key = (name or DEFAULT_T0_STRATEGY_PROFILE.name).strip()
    try:
        return _PROFILES[key]
    except KeyError as exc:
        raise KeyError(f'unknown T0 strategy profile: {key}') from exc
