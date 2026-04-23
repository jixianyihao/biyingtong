"""Baselines run in parallel so total wall time ≈ max(individual), not sum."""
import time


def test_baselines_run_in_parallel(monkeypatch, tmp_path):
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    bl = SQLiteBaselineResultStore(tmp_path=tmp_path); bl.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt); storage.set_baselines(bl)

    # Inject a 200ms sleep into each baseline's data load to make parallel
    # vs serial distinguishable.
    import backtest.baselines.buy_and_hold as bh
    import backtest.baselines.equal_weight as ew
    import backtest.baselines.csi300 as csi
    from datetime import date, timedelta

    days = [date(2025, 3, 1) + timedelta(days=i) for i in range(3)]

    def slow_prices(*a, **k):
        time.sleep(0.2)
        return [(d, 100.0) for d in days]

    def slow_index(*a, **k):
        time.sleep(0.2)
        return [(d, 1000.0) for d in days]

    monkeypatch.setattr(bh, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(bh, '_load_prices', slow_prices)
    monkeypatch.setattr(ew, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(ew, '_load_prices', slow_prices)
    monkeypatch.setattr(csi, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(csi, '_load_index_series', slow_index)

    from backtest.baselines.runner import run_all
    t0 = time.time()
    results = run_all(session_id='s', start_date='2025-03-01',
                      end_date='2025-03-03',
                      initial_capital=1_000_000.0, universe=['X.SH'])
    elapsed = time.time() - t0

    assert len(results) == 3
    # 3 × 200ms serial = 600ms. Parallel should be well under 500ms.
    assert elapsed < 0.5, f'expected parallel, took {elapsed:.2f}s'
