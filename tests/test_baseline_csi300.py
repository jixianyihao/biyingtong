"""CSI 300 index baseline."""
from datetime import date, timedelta


def test_csi300_tracks_index(monkeypatch, tmp_path):
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    bl = SQLiteBaselineResultStore(tmp_path=tmp_path); bl.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt); storage.set_baselines(bl)

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    # Index 1000 → 1020 over 4 days = +2% total
    prices = [(d, 1000.0 * (1 + 0.005 * i)) for i, d in enumerate(days)]

    import backtest.baselines.csi300 as mod
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: days)
    monkeypatch.setattr(mod, '_load_index_series', lambda s, e: prices)

    result = mod.run_csi300(
        session_id='s1', start_date='2024-03-01', end_date='2024-03-05',
        initial_capital=1_000_000.0,
    )
    assert result.name == 'csi300'
    assert result.stats.trade_count == 0  # passive
    # +2% gross return on 1M = 1_020_000 final
    assert abs(result.stats.final_equity - 1_020_000) < 10.0


def test_csi300_empty_days_raises(monkeypatch, tmp_path):
    import pytest
    import storage
    from storage.sqlite_calendar import SQLiteCalendarStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    cal = SQLiteCalendarStore(tmp_path=tmp_path); cal.init_schema()
    bt = SQLiteBacktestResultStore(tmp_path=tmp_path); bt.init_schema()
    bl = SQLiteBaselineResultStore(tmp_path=tmp_path); bl.init_schema()
    storage.set_calendar(cal); storage.set_backtests(bt); storage.set_baselines(bl)

    import backtest.baselines.csi300 as mod
    monkeypatch.setattr(mod, '_trading_days', lambda s, e: [])
    monkeypatch.setattr(mod, '_load_index_series', lambda s, e: [])
    with pytest.raises(ValueError):
        mod.run_csi300(session_id='s', start_date='2024-03-01',
                       end_date='2024-03-05', initial_capital=1_000_000.0)
