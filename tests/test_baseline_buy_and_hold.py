"""Buy-and-hold baseline."""
from datetime import date, timedelta


def test_buy_and_hold_single_stock(monkeypatch, tmp_path):
    from backtest.baselines.buy_and_hold import run_buy_and_hold
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    bl = SQLiteBaselineResultStore(tmp_path=tmp_path); bl.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt); storage.set_baselines(bl)

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(10)]
    # Monotone +1%/day: 100 -> 100*1.01^9 ~ 109.37
    prices = {'X.SH': [(d, 100.0 * (1.01 ** i)) for i, d in enumerate(days)]}

    import backtest.baselines.buy_and_hold as mod
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(mod, '_load_prices',
                        lambda code, s, e: prices[code])

    result = run_buy_and_hold(
        session_id='s1', start_date='2024-03-01', end_date='2024-03-10',
        initial_capital=1_000_000.0, universe=['X.SH'],
    )
    assert result.name == 'buy_and_hold'
    assert result.stats.trade_count == 1  # day-1 buy
    # With +9% price move on full position, expect ~5-10% gross return minus fees
    assert 5.0 < result.stats.total_return_pct < 10.0


def test_buy_and_hold_equal_weight_multi_stock(monkeypatch, tmp_path):
    from backtest.baselines.buy_and_hold import run_buy_and_hold
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    bl = SQLiteBaselineResultStore(tmp_path=tmp_path); bl.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt); storage.set_baselines(bl)

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    prices = {
        'A.SH': [(d, 100.0) for d in days],
        'B.SZ': [(d, 100.0) for d in days],
    }
    import backtest.baselines.buy_and_hold as mod
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(mod, '_load_prices',
                        lambda code, s, e: prices[code])

    result = run_buy_and_hold(
        session_id='s2', start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0, universe=['A.SH', 'B.SZ'],
    )
    # trade_count should be 2 (one buy per stock on day 1)
    assert result.stats.trade_count == 2
