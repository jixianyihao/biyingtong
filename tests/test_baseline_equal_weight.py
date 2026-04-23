"""Equal-weight monthly rebalance baseline."""
from datetime import date, timedelta


def test_equal_weight_rebalances_monthly(monkeypatch, tmp_path):
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    bl = SQLiteBaselineResultStore(tmp_path=tmp_path); bl.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt); storage.set_baselines(bl)

    # 60 days spanning ~2 month boundaries
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(60)]
    prices = {
        'A.SH': [(d, 100.0 + i) for i, d in enumerate(days)],
        'B.SZ': [(d, 200.0 - i * 0.5) for i, d in enumerate(days)],
    }
    import backtest.baselines.equal_weight as mod
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(mod, '_load_prices',
                        lambda code, s, e: prices[code])

    result = mod.run_equal_weight(
        session_id='s1', start_date='2024-03-01', end_date='2024-04-29',
        initial_capital=1_000_000.0, universe=['A.SH', 'B.SZ'],
    )
    assert result.name == 'equal_weight'
    # Should rebalance at least twice (day 1 buy + at least one month-start)
    assert result.stats.trade_count >= 2


def test_equal_weight_single_stock_degenerate(monkeypatch, tmp_path):
    """With 1 stock, equal-weight is identical to buy-and-hold."""
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    bl = SQLiteBaselineResultStore(tmp_path=tmp_path); bl.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt); storage.set_baselines(bl)

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(10)]
    prices = {'X.SH': [(d, 100.0) for d in days]}
    import backtest.baselines.equal_weight as mod
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(mod, '_load_prices',
                        lambda code, s, e: prices[code])

    result = mod.run_equal_weight(
        session_id='s2', start_date='2024-03-01', end_date='2024-03-10',
        initial_capital=1_000_000.0, universe=['X.SH'],
    )
    # Trade count = 1 (no month boundary crossed within 10 days)
    assert result.stats.trade_count == 1
