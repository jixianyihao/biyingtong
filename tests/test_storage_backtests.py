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
        persona_id=kw.get('persona_id', 'quant_neutral'),
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


def test_backtest_result_persists_persona_and_model_ids(tmp_path):
    """Phase 2.5 regression — persona_id + model_id must round-trip cleanly.

    Earlier production rows had NULL persona_id/model_id even though the
    runner passed them through; lock the storage layer down here so silent
    NULL persistence cannot recur.
    """
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    s.init_schema()
    s.create_session('s-pm', '2024-01-01', '2024-03-01', ['ag-1'])

    result = _result(
        id='r-pm-1', session_id='s-pm', agent_id='ag-1',
        persona_id='quant_neutral', model_id='hunyuan-hy3',
    )
    s.insert(result)

    got = s.get('r-pm-1')
    assert got is not None
    assert got.persona_id == 'quant_neutral'
    assert got.model_id == 'hunyuan-hy3'

    # list_for_agent / list_all should also surface the IDs.
    for row in s.list_for_agent('ag-1'):
        if row.id == 'r-pm-1':
            assert row.persona_id == 'quant_neutral'
            assert row.model_id == 'hunyuan-hy3'
            break
    else:
        raise AssertionError('result missing from list_for_agent')

    for row in s.list_all():
        if row.id == 'r-pm-1':
            assert row.persona_id == 'quant_neutral'
            assert row.model_id == 'hunyuan-hy3'
            break
    else:
        raise AssertionError('result missing from list_all')


def test_legacy_table_missing_persona_model_columns_is_repaired(tmp_path):
    """Pre-P2c databases lack persona_id/model_id columns. init_schema must
    add them via idempotent ALTER so subsequent inserts persist the IDs."""
    import sqlite3
    from pathlib import Path
    from storage.sqlite_backtests import SQLiteBacktestResultStore

    # Hand-roll a legacy-shape table without persona_id/model_id columns.
    db_path = Path(tmp_path) / 'agent_state.db'
    con = sqlite3.connect(db_path)
    try:
        con.execute('''
            CREATE TABLE backtest_results (
                id                   TEXT PRIMARY KEY,
                session_id           TEXT NOT NULL,
                agent_id             TEXT NOT NULL,
                start_date           TEXT NOT NULL,
                end_date             TEXT NOT NULL,
                initial_capital      REAL NOT NULL,
                final_equity         REAL,
                stats_json           TEXT NOT NULL,
                zone_stats_json      TEXT NOT NULL,
                quality_gate_label   TEXT NOT NULL,
                quality_gate_json    TEXT NOT NULL,
                created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        con.commit()
    finally:
        con.close()

    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    s.init_schema()  # must repair the legacy table.

    s.create_session('s-legacy', '2024-01-01', '2024-03-01', ['ag-1'])
    s.insert(_result(
        id='r-legacy-1', session_id='s-legacy', agent_id='ag-1',
        persona_id='quant_neutral', model_id='claude-opus-4-7',
    ))
    got = s.get('r-legacy-1')
    assert got.persona_id == 'quant_neutral'
    assert got.model_id == 'claude-opus-4-7'
