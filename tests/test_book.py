"""Book — tranche positions + T+1 + commission."""
from datetime import date


def _book(cash=1_000_000.0):
    from backtest.book import Book
    from backtest.commission import FeeModel
    return Book(cash=cash, fee_model=FeeModel())


def test_buy_deducts_cash_plus_fee():
    b = _book()
    fill = b.execute_buy('X.SH', shares=100, price=1000.0, d=date(2024, 3, 1))
    assert fill is not None
    # cost 100k + fee 30 (0.03%) = 100_030
    assert abs(b.cash - (1_000_000 - 100_030)) < 1e-6
    assert b.total_fees == 30.0


def test_buy_with_insufficient_cash_returns_none():
    b = _book(cash=1000.0)
    fill = b.execute_buy('X.SH', shares=100, price=1000.0, d=date(2024, 3, 1))
    assert fill is None
    assert b.cash == 1000.0


def test_sell_same_day_rejected_t_plus_1():
    """T+1: cannot sell shares bought today."""
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    fill = b.execute_sell('X.SH', shares=100, price=110.0, d=date(2024, 3, 1))
    assert fill is None  # same-day sell rejected


def test_sell_next_day_allowed():
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    fill = b.execute_sell('X.SH', shares=100, price=110.0, d=date(2024, 3, 2))
    assert fill is not None
    # proceeds = 100 * 110 = 11,000; sell fee 0.13% = 14.3; net 10,985.7
    expected_cash = 1_000_000 - (100 * 100 + 3.0) + (11_000 - 14.3)
    assert abs(b.cash - expected_cash) < 0.01


def test_sell_fifo_tranches():
    """Multiple buys create multiple tranches; sell consumes oldest first."""
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    b.execute_buy('X.SH', shares=100, price=120.0, d=date(2024, 3, 2))
    # Day 3: sell 100 — should consume the 100@100 tranche (FIFO)
    b.execute_sell('X.SH', shares=100, price=130.0, d=date(2024, 3, 3))
    view = b.positions_view()
    assert view['X.SH']['shares'] == 100
    assert abs(view['X.SH']['avg_price'] - 120.0) < 1e-6


def test_sell_over_shares_sells_what_it_can():
    """Requesting more than owned sells available qty; rejection is for 0."""
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    fill = b.execute_sell('X.SH', shares=500, price=110.0, d=date(2024, 3, 2))
    assert fill is not None
    assert fill.shares == 100
    assert b.positions_view().get('X.SH', {}).get('shares', 0) == 0


def test_positions_view_excludes_empty():
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    b.execute_sell('X.SH', shares=100, price=110.0, d=date(2024, 3, 2))
    assert 'X.SH' not in b.positions_view()


def test_equity_marks_to_market():
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    # mark @ 150 → cash (1M - 10_003 after buy cost+fee) + 100*150 = 1_004_997
    eq = b.equity(mark_prices={'X.SH': 150.0})
    assert abs(eq - (1_000_000 - 10_003 + 100 * 150)) < 1e-6


def test_cost_weighted_avg_price_across_tranches():
    b = _book()
    b.execute_buy('X.SH', shares=100, price=100.0, d=date(2024, 3, 1))
    b.execute_buy('X.SH', shares=300, price=200.0, d=date(2024, 3, 2))
    # avg = (100*100 + 300*200) / 400 = 70_000 / 400 = 175
    view = b.positions_view()
    assert abs(view['X.SH']['avg_price'] - 175.0) < 1e-6
    assert view['X.SH']['shares'] == 400
