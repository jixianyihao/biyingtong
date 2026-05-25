from __future__ import annotations

from t0.allocator import choose_t0_allocation


def _bar(ts: str, close: float):
    return {
        'date': ts,
        'open': close,
        'high': close,
        'low': close,
        'close': close,
        'vol': 100_000,
    }


def test_bullish_trend_uses_high_base_position_and_small_t_leg():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-02-10 15:00:00', 102.0),
        _bar('2026-03-02 15:00:00', 104.5),
        _bar('2026-04-01 15:00:00', 107.0),
    ]

    allocation = choose_t0_allocation(bars)

    assert allocation['mode'] == 'bull_high_base'
    assert allocation['base_position_pct'] == 0.90
    assert allocation['t_shares_pct'] == 0.15
    assert allocation['trend_return_pct'] == 7.0
    assert allocation['strategy_params']['allow_sell_first'] is False
    assert allocation['strategy_params']['allow_buy_first'] is True
    assert allocation['strategy_params']['high_band'] == 0.82
    assert allocation['strategy_params']['low_band'] == 0.25
    assert allocation['strategy_params']['stop_loss_pct'] == 1.0


def test_strong_bull_trend_uses_sell_first_rebalance_mode():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-02-10 15:00:00', 104.0),
        _bar('2026-03-02 15:00:00', 109.0),
        _bar('2026-04-01 15:00:00', 113.0),
    ]

    allocation = choose_t0_allocation(bars)

    assert allocation['mode'] == 'strong_bull_sell_rebalance'
    assert allocation['base_position_pct'] == 0.99
    assert allocation['t_shares_pct'] == 0.25
    assert allocation['trend_return_pct'] == 13.0
    assert allocation['strategy_params']['allow_sell_first'] is True
    assert allocation['strategy_params']['allow_buy_first'] is False
    assert allocation['strategy_params']['high_band'] == 0.88
    assert allocation['strategy_params']['low_band'] == 0.18


def test_sideways_trend_keeps_balanced_cash_for_active_t():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-02-10 15:00:00', 101.0),
        _bar('2026-03-02 15:00:00', 99.0),
        _bar('2026-04-01 15:00:00', 101.5),
    ]

    allocation = choose_t0_allocation(bars)

    assert allocation['mode'] == 'balanced_range'
    assert allocation['base_position_pct'] == 0.70
    assert allocation['t_shares_pct'] == 0.25


def test_explicit_bull_mode_overrides_trend_classifier():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-04-01 15:00:00', 96.0),
    ]

    allocation = choose_t0_allocation(bars, requested_mode='bull')

    assert allocation['mode'] == 'bull_high_base'
    assert allocation['base_position_pct'] == 0.90
    assert allocation['t_shares_pct'] == 0.15
