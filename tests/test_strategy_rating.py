"""Strategy Rating (Spec §9) — 5 sub-scores + weighted overall + letter."""
from __future__ import annotations

from backtest.base import BacktestResult, BacktestStats, ZoneStats
from rating.strategy_rating import compute_strategy_rating, StrategyRating


def _make_result(
    *,
    sharpe=1.0,
    max_drawdown_pct=-10.0,
    trade_count=20,
    win_rate=55.0,
    max_daily_loss_pct=-2.0,
    total_return_pct=15.0,
    final_equity=1_150_000.0,
    zones=None,
) -> BacktestResult:
    stats = BacktestStats(
        sharpe=sharpe,
        max_drawdown_pct=max_drawdown_pct,
        trade_count=trade_count,
        win_rate=win_rate,
        max_daily_loss_pct=max_daily_loss_pct,
        total_return_pct=total_return_pct,
        final_equity=final_equity,
    )
    zone_stats = zones if zones is not None else []
    return BacktestResult(
        id='r-test', session_id='s-test', agent_id='a-test',
        persona_id='linyuan', model_id='claude-opus-4-7',
        start_date='2025-01-01', end_date='2025-02-01',
        initial_capital=1_000_000.0, final_equity=final_equity,
        stats=stats, zone_stats=zone_stats,
        quality_gate_label='pass', quality_gate_criteria={},
    )


def test_empty_ish_stats_give_low_score():
    """Flat sharpe, heavy mdd → low overall, letter D/C."""
    r = _make_result(
        sharpe=0.0,
        max_drawdown_pct=-40.0,       # MDD beyond 30% → mdd_score = 0
        trade_count=0,                # trade_count<5 → trading_efficiency=0
        max_daily_loss_pct=-12.0,     # daily loss>10% → daily_score = 0
        total_return_pct=-30.0,
        final_equity=700_000.0,
    )
    rating = compute_strategy_rating(r)
    assert rating.return_power == 0.0
    assert rating.risk_control == 0.0
    # stability = 100 - abs(-40)*2 = 100 - 80 = 20
    assert rating.stability == 20.0
    assert rating.trading_efficiency == 0.0
    assert rating.overfitting_risk == 50.0   # no zone data
    assert rating.letter == 'D'
    assert rating.overall < 60


def test_high_sharpe_low_drawdown_gets_a_or_a_plus():
    """Strong clean-zone sharpe + shallow MDD → A or A+."""
    zones = [
        ZoneStats(zone='pollution', days=20,
                  stats={'sharpe': 2.5, 'max_drawdown_pct': -4.0,
                         'trade_count': 10, 'win_rate': 60.0,
                         'max_daily_loss_pct': -1.0,
                         'total_return_pct': 8.0,
                         'final_equity': 1_080_000.0}),
        ZoneStats(zone='buffer', days=5, stats={}),
        ZoneStats(zone='clean', days=30,
                  stats={'sharpe': 2.6, 'max_drawdown_pct': -5.0,
                         'trade_count': 20, 'win_rate': 65.0,
                         'max_daily_loss_pct': -1.5,
                         'total_return_pct': 18.0,
                         'final_equity': 1_180_000.0}),
    ]
    r = _make_result(
        sharpe=2.5, max_drawdown_pct=-5.0, trade_count=30,
        max_daily_loss_pct=-1.5, total_return_pct=25.0,
        final_equity=1_250_000.0, zones=zones,
    )
    rating = compute_strategy_rating(r)
    assert rating.letter in ('A', 'A+')
    assert rating.overall >= 80
    assert rating.return_power >= 80  # clean sharpe 2.6/2.5*100 ≈ 100+ clamped
    assert rating.risk_control >= 80
    # Zones diverge only by 0.1 sharpe → overfitting_risk near 95
    assert rating.overfitting_risk >= 90


def test_trade_count_below_5_zeros_out_efficiency():
    r = _make_result(trade_count=3, total_return_pct=10.0)
    rating = compute_strategy_rating(r)
    assert rating.trading_efficiency == 0.0
    assert any('trading_efficiency = 0' in n for n in rating.notes)


def test_zone_divergence_reduces_overfitting_risk():
    """Big clean↔pollution sharpe gap → low overfitting_risk score."""
    zones = [
        ZoneStats(zone='pollution', days=20,
                  stats={'sharpe': 3.0, 'max_drawdown_pct': -2.0,
                         'trade_count': 10, 'win_rate': 70.0,
                         'max_daily_loss_pct': -0.5,
                         'total_return_pct': 20.0,
                         'final_equity': 1_200_000.0}),
        ZoneStats(zone='buffer', days=5, stats={}),
        ZoneStats(zone='clean', days=30,
                  stats={'sharpe': 0.5, 'max_drawdown_pct': -15.0,
                         'trade_count': 20, 'win_rate': 45.0,
                         'max_daily_loss_pct': -3.0,
                         'total_return_pct': 2.0,
                         'final_equity': 1_020_000.0}),
    ]
    r = _make_result(zones=zones)
    rating = compute_strategy_rating(r)
    # divergence = |3.0 - 0.5| = 2.5 → max(0, 1 - 2.5/2.0) = 0 → overfitting_risk = 0
    assert rating.overfitting_risk == 0.0


def test_no_zone_data_yields_neutral_overfitting_risk():
    r = _make_result(zones=[])
    rating = compute_strategy_rating(r)
    assert rating.overfitting_risk == 50.0
    assert any('overfitting_risk = 50' in n for n in rating.notes)


def test_letter_grade_thresholds():
    """Each letter boundary resolves correctly."""
    # Build minimal inputs that yield known overall.
    # Easiest: craft stats so risk+stability+efficiency dominate.
    # But simpler: directly exercise _grade via the pure function.
    from rating.strategy_rating import _grade
    assert _grade(100) == 'A+'
    assert _grade(90) == 'A+'
    assert _grade(89.9) == 'A'
    assert _grade(80) == 'A'
    assert _grade(79.9) == 'B'
    assert _grade(70) == 'B'
    assert _grade(69.9) == 'C'
    assert _grade(60) == 'C'
    assert _grade(59.9) == 'D'
    assert _grade(0) == 'D'


def test_notes_surface_approximations():
    """Every MVP approximation used should be surfaced in notes."""
    # No zone data, no trades → full set of notes fires
    r = _make_result(trade_count=2, zones=[])
    rating = compute_strategy_rating(r)
    joined = ' | '.join(rating.notes)
    assert 'return_power' in joined   # no clean zone
    assert 'stability' in joined      # MDD proxy
    assert 'trading_efficiency' in joined  # <5 trades
    assert 'overfitting_risk' in joined    # neutral


def test_rating_dataclass_is_frozen_and_serializable():
    """StrategyRating is a frozen dataclass — usable as a dict via asdict()."""
    from dataclasses import asdict, FrozenInstanceError
    import pytest as _pt
    r = _make_result()
    rating = compute_strategy_rating(r)
    assert isinstance(rating, StrategyRating)
    # Freeze guarantees
    with _pt.raises(FrozenInstanceError):
        rating.letter = 'X'  # type: ignore[misc]
    d = asdict(rating)
    assert set(d.keys()) == {
        'return_power', 'risk_control', 'stability',
        'trading_efficiency', 'overfitting_risk',
        'overall', 'letter', 'notes',
    }
    # letter is consistent with overall
    assert d['letter'] in ('A+', 'A', 'B', 'C', 'D')
