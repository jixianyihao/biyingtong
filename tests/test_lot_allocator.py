"""Iterative lot allocator — the A-share-correct replacement for *0.995 hacks."""


def test_exact_fit_100_shares():
    from backtest.lot_allocator import allocate_lot
    from backtest.commission import FeeModel
    # 100 shares × 100 price + 0.03% fee = 10_003. Need cash >= 10_003.
    shares = allocate_lot(cash=10_003.0, price=100.0, fee_model=FeeModel())
    assert shares == 100


def test_insufficient_for_one_lot_returns_zero():
    from backtest.lot_allocator import allocate_lot
    from backtest.commission import FeeModel
    # 100 shares × 100 = 10000 but fee pushes to 10003. Only 10000 cash
    # → can't afford, returns 0.
    shares = allocate_lot(cash=10_000.0, price=100.0, fee_model=FeeModel())
    assert shares == 0


def test_decrements_by_lot_when_naive_overflows():
    from backtest.lot_allocator import allocate_lot
    from backtest.commission import FeeModel
    # 1M cash, price 100 → naive 10000 shares, cost 1_000_000 + 300 fee
    # = 1_000_300 > cash. Decrement to 9900 → 990_000 + 297 = 990_297 ≤ 1M. ✓
    shares = allocate_lot(cash=1_000_000.0, price=100.0, fee_model=FeeModel())
    assert shares == 9_900


def test_under_naive_stays_at_naive():
    from backtest.lot_allocator import allocate_lot
    from backtest.commission import FeeModel
    # 500k cash, price 100 → naive 5000 shares, cost 500_000 + 150 = 500_150
    # > 500k. Decrement to 4900 → 490_000 + 147 = 490_147 ≤ 500k. ✓
    shares = allocate_lot(cash=500_000.0, price=100.0, fee_model=FeeModel())
    assert shares == 4_900


def test_price_zero_returns_zero():
    from backtest.lot_allocator import allocate_lot
    from backtest.commission import FeeModel
    assert allocate_lot(cash=1_000_000, price=0.0, fee_model=FeeModel()) == 0


def test_cash_zero_returns_zero():
    from backtest.lot_allocator import allocate_lot
    from backtest.commission import FeeModel
    assert allocate_lot(cash=0.0, price=100.0, fee_model=FeeModel()) == 0


def test_already_lot_aligned_naive():
    from backtest.lot_allocator import allocate_lot
    from backtest.commission import FeeModel
    # 200k cash, price 100, fee 0.03% → 200 shares = 20_000 + 6 fee = 20_006
    # 2000 shares naive = 200_000 + 60 = 200_060 > 200k. 1900 → 190_057 OK.
    shares = allocate_lot(cash=200_000.0, price=100.0, fee_model=FeeModel())
    assert shares == 1_900


def test_zero_fee_model_uses_full_budget():
    from backtest.lot_allocator import allocate_lot
    from backtest.commission import FeeModel
    m = FeeModel(buy_bps=0.0, sell_bps=0.0)
    # 1M cash, price 100, zero fee → exactly 10000 shares fit.
    assert allocate_lot(cash=1_000_000.0, price=100.0, fee_model=m) == 10_000
