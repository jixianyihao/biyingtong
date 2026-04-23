"""BaselineRunner orchestrator."""
from datetime import date, timedelta


def test_run_all_three_baselines(monkeypatch, tmp_path):
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    bl = SQLiteBaselineResultStore(tmp_path=tmp_path); bl.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt); storage.set_baselines(bl)

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    stock_prices = [(d, 100.0 + i) for i, d in enumerate(days)]
    index_prices = [(d, 1000.0 + i * 2) for i, d in enumerate(days)]

    import backtest.baselines.buy_and_hold as bh_mod
    import backtest.baselines.equal_weight as ew_mod
    import backtest.baselines.csi300 as csi_mod
    monkeypatch.setattr(bh_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(bh_mod, '_load_prices', lambda c, s, e: stock_prices)
    monkeypatch.setattr(ew_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(ew_mod, '_load_prices', lambda c, s, e: stock_prices)
    monkeypatch.setattr(csi_mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(csi_mod, '_load_index_series', lambda s, e: index_prices)

    from backtest.baselines.runner import run_all
    results = run_all(
        session_id='s1', start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0, universe=['X.SH'],
    )
    assert {r.name for r in results} == {'buy_and_hold', 'equal_weight',
                                          'csi300'}

    # All persisted under session
    stored = storage.baselines().list_for_session('s1')
    assert len(stored) == 3
