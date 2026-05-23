from __future__ import annotations

import pytest

from t0.backtest import run_t0_backtest


def _bar(ts: str, price: float, high: float | None = None, low: float | None = None):
    return {
        'date': ts,
        'open': price,
        'high': price if high is None else high,
        'low': price if low is None else low,
        'close': price,
        'vol': 100_000,
    }


def test_sell_high_buy_back_low_round_trip_is_profitable():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-01-26 09:35:00', 103.0, high=103.2, low=100.0),
        _bar('2026-01-26 10:10:00', 101.0, high=103.2, low=100.8),
        _bar('2026-01-26 14:55:00', 101.2),
    ]

    result = run_t0_backtest(
        '688981.SH',
        bars,
        base_shares=1000,
        t_shares=500,
        min_amplitude_pct=1.0,
        take_profit_pct=1.0,
        stop_loss_pct=2.0,
        fee_bps=0.0,
        sell_tax_bps=0.0,
        slippage_bps=0.0,
    )

    assert result['round_trips'] == 1
    assert result['wins'] == 1
    assert result['losses'] == 0
    assert result['total_pnl'] == pytest.approx(1000.0)
    assert result['trades'][0]['action'] == 'sell_t'
    assert result['trades'][1]['action'] == 'buy_back'


def test_low_amplitude_day_does_not_trade():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-01-26 10:00:00', 100.2, high=100.25, low=99.95),
        _bar('2026-01-26 14:55:00', 100.1),
    ]

    result = run_t0_backtest(
        '688981.SH',
        bars,
        min_amplitude_pct=1.0,
    )

    assert result['round_trips'] == 0
    assert result['total_pnl'] == 0
    assert result['trades'] == []


def test_open_leg_is_forced_flat_at_day_close():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-01-26 09:35:00', 103.0, high=103.2, low=100.0),
        _bar('2026-01-26 14:55:00', 102.5),
    ]

    result = run_t0_backtest(
        '688981.SH',
        bars,
        min_amplitude_pct=1.0,
        take_profit_pct=2.0,
        stop_loss_pct=2.0,
        fee_bps=0.0,
        sell_tax_bps=0.0,
        slippage_bps=0.0,
    )

    assert result['round_trips'] == 1
    assert result['trades'][-1]['reason'] == 'forced_close'
    assert result['total_pnl'] == pytest.approx(250.0)


def test_sell_first_only_skips_low_buy_first_entry():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-01-26 09:35:00', 98.0, high=100.0, low=97.8),
        _bar('2026-01-26 14:55:00', 99.0),
    ]

    result = run_t0_backtest(
        '688981.SH',
        bars,
        allow_buy_first=False,
        allow_sell_first=True,
        min_amplitude_pct=1.0,
    )

    assert result['round_trips'] == 0
    assert result['trades'] == []


def test_max_round_trips_per_day_limits_overtrading():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-01-26 09:35:00', 103.0, high=103.2, low=100.0),
        _bar('2026-01-26 10:10:00', 101.0, high=103.2, low=100.8),
        _bar('2026-01-26 13:30:00', 103.5, high=103.8, low=100.8),
        _bar('2026-01-26 14:00:00', 101.5, high=103.8, low=100.8),
    ]

    result = run_t0_backtest(
        '688981.SH',
        bars,
        max_round_trips_per_day=1,
        min_amplitude_pct=1.0,
        take_profit_pct=1.0,
        fee_bps=0.0,
        sell_tax_bps=0.0,
        slippage_bps=0.0,
    )

    assert result['round_trips'] == 1
    assert [t['action'] for t in result['trades']] == ['sell_t', 'buy_back']


def test_latest_entry_time_prevents_late_new_leg():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-01-26 14:45:00', 103.0, high=103.2, low=100.0),
        _bar('2026-01-26 15:00:00', 102.8),
    ]

    result = run_t0_backtest(
        '688981.SH',
        bars,
        min_amplitude_pct=1.0,
        latest_entry_time='14:30',
    )

    assert result['round_trips'] == 0
    assert result['trades'] == []
