from __future__ import annotations

import pytest

from t0.fill_simulator import MarketFillSimulator, T0FillConfig


def test_open_sell_first_applies_sell_slippage_fee_and_cash_delta():
    sim = MarketFillSimulator(
        T0FillConfig(fee_bps=2.5, sell_tax_bps=5.0, slippage_bps=10.0),
    )

    fill = sim.open_leg('sell_first', price=100.0, shares=1000, ts='2026-01-26 09:35:00')

    assert fill.leg.side == 'sell_first'
    assert fill.leg.price == pytest.approx(99.9)
    assert fill.cash_delta == pytest.approx(99_825.075)
    assert fill.trade == {
        'ts': '2026-01-26 09:35:00',
        'action': 'sell_t',
        'shares': 1000,
        'price': 99.9,
        'fee': 74.925,
    }


def test_close_sell_first_buyback_returns_negative_cash_delta_and_pnl():
    sim = MarketFillSimulator(
        T0FillConfig(fee_bps=0.0, sell_tax_bps=0.0, slippage_bps=0.0),
    )
    opened = sim.open_leg('sell_first', price=103.0, shares=500, ts='2026-01-26 09:35:00')

    close = sim.close_leg(opened.leg, price=101.0, ts='2026-01-26 10:05:00', reason='take_profit')

    assert close.cash_delta == pytest.approx(-50_500.0)
    assert close.pnl == pytest.approx(1_000.0)
    assert close.trade == {
        'ts': '2026-01-26 10:05:00',
        'action': 'buy_back',
        'shares': 500,
        'price': 101.0,
        'fee': 0.0,
        'pnl': 1000.0,
        'reason': 'take_profit',
    }


def test_buy_first_round_trip_accounts_for_both_fees():
    sim = MarketFillSimulator(
        T0FillConfig(fee_bps=2.5, sell_tax_bps=5.0, slippage_bps=0.0),
    )
    opened = sim.open_leg('buy_first', price=100.0, shares=1000, ts='2026-01-26 09:35:00')

    close = sim.close_leg(opened.leg, price=102.0, ts='2026-01-26 10:05:00', reason='take_profit')

    assert opened.cash_delta == pytest.approx(-100_025.0)
    assert close.cash_delta == pytest.approx(101_923.5)
    assert close.pnl == pytest.approx(1_898.5)
    assert close.trade['action'] == 'sell_back'
    assert close.trade['fee'] == pytest.approx(76.5)
