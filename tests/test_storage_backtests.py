"""SQLiteBacktestResultStore — sessions + results persistence."""


def _result(id='r1', session_id='s1', agent_id='a1',
            label='pass', **kw):
    from backtest.base import BacktestStats, BacktestResult
    stats = BacktestStats(
        sharpe=1.0, max_drawdown_pct=-10.0, trade_count=20,
        win_rate=50.0, max_daily_loss_pct=-3.0,
        total_return_pct=15.0, final_equity=1_150_000.0,
    )
    return BacktestResult(
        id=id, session_id=session_id, agent_id=agent_id,
        persona_id=kw.get('persona_id', 'linyuan'),
        model_id=kw.get('model_id', 'claude-opus-4-7'),
        start_date='2024-01-01', end_date='2024-03-01',
        initial_capital=1_000_000.0, stats=stats, zone_stats=[],
        quality_gate_label=label, quality_gate_criteria={},
        final_equity=1_150_000.0,
    )


def test_create_session_idempotent(tmp_path):
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.create_session('s1', '2024-01-01', '2024-03-01', ['a1', 'a2'])
    s.create_session('s1', '2024-01-01', '2024-03-01', ['a1', 'a2'])


def test_insert_then_get(tmp_path):
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.create_session('s1', '2024-01-01', '2024-03-01', ['a1'])
    s.insert(_result())
    got = s.get('r1')
    assert got is not None
    assert got.agent_id == 'a1'
    assert got.quality_gate_label == 'pass'
    assert got.stats.sharpe == 1.0


def test_list_for_session_groups_results(tmp_path):
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.create_session('s1', '2024-01-01', '2024-03-01', ['a1', 'a2'])
    s.insert(_result(id='r1', session_id='s1', agent_id='a2'))
    s.insert(_result(id='r2', session_id='s1', agent_id='a1'))
    s.insert(_result(id='r3', session_id='s2', agent_id='a1'))
    results = s.list_for_session('s1')
    assert {r.id for r in results} == {'r1', 'r2'}


def test_list_for_agent_recent_first(tmp_path):
    import time
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.create_session('s1', '2024-01-01', '2024-03-01', ['a1'])
    s.insert(_result(id='r1', agent_id='a1'))
    time.sleep(0.02)
    s.insert(_result(id='r2', agent_id='a1'))
    lst = s.list_for_agent('a1')
    assert [r.id for r in lst] == ['r2', 'r1']


def test_zone_stats_roundtrips(tmp_path):
    from backtest.base import ZoneStats
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.create_session('s1', '2024-01-01', '2024-03-01', ['a1'])
    r = _result()
    r.zone_stats = [ZoneStats(zone='pollution', days=60, stats={'sharpe': 1.0}),
                    ZoneStats(zone='clean', days=30, stats={'sharpe': 0.5})]
    s.insert(r)
    got = s.get(r.id)
    assert len(got.zone_stats) == 2
    assert got.zone_stats[0].zone == 'pollution'
