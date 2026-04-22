"""Backtest core dataclasses."""


def test_backtest_stats_fields():
    from backtest.base import BacktestStats
    s = BacktestStats(
        sharpe=1.2, max_drawdown_pct=-12.0, trade_count=30,
        win_rate=55.0, max_daily_loss_pct=-2.0,
        total_return_pct=18.0, final_equity=1_180_000.0,
    )
    assert s.sharpe == 1.2
    assert s.final_equity == 1_180_000.0


def test_zone_stats_default_zone_labels():
    from backtest.base import ZoneStats
    z = ZoneStats(zone='pollution', days=100, stats={})
    assert z.zone == 'pollution'
    assert z.days == 100


def test_backtest_result_fields():
    from backtest.base import BacktestResult, BacktestStats
    stats = BacktestStats(sharpe=0.5, max_drawdown_pct=-5,
                          trade_count=10, win_rate=60,
                          max_daily_loss_pct=-1,
                          total_return_pct=5, final_equity=105)
    r = BacktestResult(
        id='r1', session_id='s1', agent_id='a1',
        persona_id='linyuan', model_id='claude-opus-4-7',
        start_date='2024-01-01', end_date='2024-02-01',
        initial_capital=100.0, stats=stats, zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
    )
    assert r.quality_gate_label == 'pass'
    assert r.stats.sharpe == 0.5


def test_cached_decision_roundtrip_to_dict():
    from backtest.base import CachedDecision
    d = CachedDecision(
        agent_id='a1', date='2024-01-15',
        portfolio_hash='abc', prompt_hash='xyz',
        decisions=[{'action': 'buy', 'code': 'X', 'shares': 100, 'price': 10.0}],
    )
    assert d.decisions[0]['action'] == 'buy'
    assert d.cache_key == CachedDecision.build_key(
        'a1', '2024-01-15', 'abc', 'xyz',
    )
