"""vnpy-independent portfolio dict builder for the validation engine."""


def test_empty_positions_equity_equals_cash():
    from backtest.portfolio_adapter import build_portfolio
    p = build_portfolio(cash=1_000_000.0, positions={}, mark_prices={})
    assert p['equity'] == 1_000_000.0
    assert p['cash'] == 1_000_000.0
    assert p['positions'] == {}


def test_equity_includes_position_mark_to_market():
    from backtest.portfolio_adapter import build_portfolio
    p = build_portfolio(
        cash=900_000.0,
        positions={'X.SH': {'shares': 500, 'avg_price': 180.0}},
        mark_prices={'X.SH': 200.0},
    )
    assert p['cash'] == 900_000.0
    assert p['equity'] == 1_000_000.0
    assert p['positions']['X.SH']['shares'] == 500
    assert p['positions']['X.SH']['avg_price'] == 180.0


def test_missing_mark_price_falls_back_to_avg():
    from backtest.portfolio_adapter import build_portfolio
    p = build_portfolio(
        cash=100_000.0,
        positions={'X.SH': {'shares': 100, 'avg_price': 10.0}},
        mark_prices={},
    )
    assert p['equity'] == 100_000.0 + 100 * 10.0


def test_zero_share_position_is_excluded():
    from backtest.portfolio_adapter import build_portfolio
    p = build_portfolio(
        cash=100_000.0,
        positions={'X.SH': {'shares': 0, 'avg_price': 10.0},
                   'Y.SZ': {'shares': 100, 'avg_price': 20.0}},
        mark_prices={'Y.SZ': 22.0},
    )
    assert 'X.SH' not in p['positions']
    assert p['positions']['Y.SZ']['shares'] == 100
