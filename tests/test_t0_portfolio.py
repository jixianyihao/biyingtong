from __future__ import annotations

import pytest

from t0.portfolio import run_t0_portfolio_backtest


def _bar(ts: str, price: float, high: float | None = None, low: float | None = None):
    return {
        'date': ts,
        'open': price,
        'high': price if high is None else high,
        'low': price if low is None else low,
        'close': price,
        'vol': 100_000,
    }


def test_portfolio_starts_with_base_position_and_reserved_cash():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-01-26 15:00:00', 110.0, high=110.0, low=100.0),
    ]

    result = run_t0_portfolio_backtest(
        '688981.SH',
        bars,
        initial_capital=1_000_000,
        base_position_pct=0.75,
        min_amplitude_pct=99.0,
        fee_bps=0.0,
        sell_tax_bps=0.0,
        slippage_bps=0.0,
    )

    assert result['base_shares'] == 7500
    assert result['t_shares'] == 1500
    assert result['initial_cash'] == pytest.approx(250_000)
    assert result['final_equity'] == pytest.approx(1_075_000)
    assert result['t_pnl'] == 0


def test_portfolio_buy_first_uses_reserved_cash_and_sells_old_shares():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-01-26 09:35:00', 98.0, high=100.0, low=97.8),
        _bar('2026-01-26 10:05:00', 101.0, high=101.2, low=97.8),
        _bar('2026-01-26 15:00:00', 101.0),
    ]

    result = run_t0_portfolio_backtest(
        '688981.SH',
        bars,
        initial_capital=1_000_000,
        base_position_pct=0.75,
        t_shares_pct=0.20,
        min_amplitude_pct=1.0,
        high_band=0.80,
        low_band=0.25,
        take_profit_pct=1.0,
        fee_bps=0.0,
        sell_tax_bps=0.0,
        slippage_bps=0.0,
    )

    assert result['round_trips'] == 1
    assert result['base_shares'] == 7500
    assert result['final_shares'] == 7500
    assert result['t_pnl'] == pytest.approx(4_500)
    assert result['alpha_vs_base_hold'] == pytest.approx(4_500)
    assert [t['action'] for t in result['trades']] == ['buy_t', 'sell_back']


def test_all_in_position_disables_buy_first_when_cash_is_insufficient():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-01-26 09:35:00', 98.0, high=100.0, low=97.8),
        _bar('2026-01-26 10:05:00', 101.0, high=101.2, low=97.8),
        _bar('2026-01-26 15:00:00', 101.0),
    ]

    result = run_t0_portfolio_backtest(
        '688981.SH',
        bars,
        initial_capital=1_000_000,
        base_position_pct=1.0,
        allow_sell_first=False,
        allow_buy_first=True,
        min_amplitude_pct=1.0,
        high_band=0.80,
        low_band=0.25,
        fee_bps=0.0,
        sell_tax_bps=0.0,
        slippage_bps=0.0,
    )

    assert result['initial_cash'] == 0
    assert result['round_trips'] == 0
    assert result['t_pnl'] == 0


def test_sellable_old_shares_reset_next_day_not_after_same_day_buyback():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-01-26 09:35:00', 103.0, high=103.2, low=100.0),
        _bar('2026-01-26 10:00:00', 101.0, high=103.2, low=100.8),
        _bar('2026-01-26 10:30:00', 103.5, high=103.8, low=100.8),
        _bar('2026-01-26 11:00:00', 101.5, high=103.8, low=100.8),
        _bar('2026-01-27 09:31:00', 100.0),
        _bar('2026-01-27 09:35:00', 103.0, high=103.2, low=100.0),
        _bar('2026-01-27 10:00:00', 101.0, high=103.2, low=100.8),
    ]

    result = run_t0_portfolio_backtest(
        '688981.SH',
        bars,
        initial_capital=100_000,
        base_position_pct=1.0,
        t_shares_pct=0.5,
        max_round_trips_per_day=3,
        min_amplitude_pct=1.0,
        take_profit_pct=1.0,
        fee_bps=0.0,
        sell_tax_bps=0.0,
        slippage_bps=0.0,
    )

    assert result['base_shares'] == 1000
    # Day 1 can sell 500 twice, then same-day buybacks are locked. Day 2 resets
    # sellable shares and can sell 500 again.
    assert result['round_trips'] == 3
