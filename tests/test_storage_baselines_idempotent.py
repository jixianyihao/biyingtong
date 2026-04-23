"""Baselines insert should logically upsert by (session_id, name)."""


def _make(result_id, session_id='s1', name='buy_and_hold'):
    from backtest.base import BacktestStats
    from backtest.baselines.base import BaselineResult
    stats = BacktestStats(
        sharpe=0.2, max_drawdown_pct=-8, trade_count=1,
        win_rate=100, max_daily_loss_pct=-2,
        total_return_pct=3, final_equity=1_030_000,
    )
    return BaselineResult(
        id=result_id, session_id=session_id, name=name,
        start_date='2024-01-01', end_date='2024-03-01',
        initial_capital=1_000_000, stats=stats, final_equity=1_030_000,
    )


def test_rerun_same_session_name_does_not_duplicate(tmp_path):
    """Running baselines twice under same session_id should leave one row per name."""
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    s = SQLiteBaselineResultStore(tmp_path=tmp_path)
    s.init_schema()
    # First "run": buy_and_hold + csi300
    s.insert(_make('uuid-1-bh', name='buy_and_hold'))
    s.insert(_make('uuid-1-cs', name='csi300'))
    assert len(s.list_for_session('s1')) == 2
    # Second "run": fresh uuids but SAME session_id + name
    s.insert(_make('uuid-2-bh', name='buy_and_hold'))
    s.insert(_make('uuid-2-cs', name='csi300'))
    # Should still be 2, not 4
    rows = s.list_for_session('s1')
    assert len(rows) == 2
    # The second-run uuids should be the ones present (fresher)
    ids = {r.id for r in rows}
    assert ids == {'uuid-2-bh', 'uuid-2-cs'}


def test_insert_by_same_id_still_replaces(tmp_path):
    """The old INSERT OR REPLACE by id semantics must still work."""
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    s = SQLiteBaselineResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.insert(_make('same-id', name='buy_and_hold'))
    r2 = _make('same-id', name='buy_and_hold')
    r2.final_equity = 9_999_999.0
    s.insert(r2)
    rows = s.list_for_session('s1')
    assert len(rows) == 1
    assert rows[0].final_equity == 9_999_999.0


def test_different_sessions_isolated(tmp_path):
    """Only same session_id should trigger the dedup."""
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    s = SQLiteBaselineResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.insert(_make('a', session_id='s1', name='buy_and_hold'))
    s.insert(_make('b', session_id='s2', name='buy_and_hold'))
    assert len(s.list_for_session('s1')) == 1
    assert len(s.list_for_session('s2')) == 1
