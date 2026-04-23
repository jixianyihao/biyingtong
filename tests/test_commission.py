"""FeeModel — A-share buy/sell fees."""


def test_default_buy_fee():
    from backtest.commission import FeeModel
    m = FeeModel()
    # 100 shares @ 1000 = 100,000 notional; buy 0.03% = 30
    assert abs(m.fee(side='buy', shares=100, price=1000.0) - 30.0) < 1e-6


def test_default_sell_fee():
    from backtest.commission import FeeModel
    m = FeeModel()
    # 100 shares @ 1000 = 100,000 notional; sell 0.13% = 130
    assert abs(m.fee(side='sell', shares=100, price=1000.0) - 130.0) < 1e-6


def test_custom_rates():
    from backtest.commission import FeeModel
    m = FeeModel(buy_bps=5.0, sell_bps=20.0)
    assert abs(m.fee(side='buy', shares=1000, price=10.0) - 5.0) < 1e-6
    assert abs(m.fee(side='sell', shares=1000, price=10.0) - 20.0) < 1e-6


def test_zero_shares_is_zero_fee():
    from backtest.commission import FeeModel
    m = FeeModel()
    assert m.fee(side='buy', shares=0, price=100.0) == 0.0


def test_unknown_side_raises():
    import pytest
    from backtest.commission import FeeModel
    m = FeeModel()
    with pytest.raises(ValueError):
        m.fee(side='short', shares=100, price=10.0)
