"""SQLiteBaselineResultStore."""


def _make(id='b1', name='buy_and_hold'):
    from backtest.base import BacktestStats
    from backtest.baselines.base import BaselineResult
    stats = BacktestStats(
        sharpe=0.2, max_drawdown_pct=-8, trade_count=1,
        win_rate=100, max_daily_loss_pct=-2,
        total_return_pct=3, final_equity=1_030_000,
    )
    return BaselineResult(
        id=id, session_id='s1', name=name,
        start_date='2024-01-01', end_date='2024-03-01',
        initial_capital=1_000_000, stats=stats, final_equity=1_030_000,
    )


def test_insert_then_get(tmp_path):
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    s = SQLiteBaselineResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.insert(_make())
    got = s.get('b1')
    assert got is not None
    assert got.name == 'buy_and_hold'


def test_list_for_session(tmp_path):
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    s = SQLiteBaselineResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.insert(_make(id='b1', name='buy_and_hold'))
    s.insert(_make(id='b2', name='csi300'))
    rows = s.list_for_session('s1')
    assert {r.name for r in rows} == {'buy_and_hold', 'csi300'}


def test_protocol_exposed():
    from storage.base import BaselineResultStore
    for m in ('init_schema', 'insert', 'get', 'list_for_session'):
        assert hasattr(BaselineResultStore, m), f'missing {m}'
