"""BaselineResult dataclass shape."""


def test_baseline_result_fields():
    from backtest.baselines.base import BaselineResult
    from backtest.base import BacktestStats
    stats = BacktestStats(
        sharpe=0.2, max_drawdown_pct=-8, trade_count=1,
        win_rate=100, max_daily_loss_pct=-2,
        total_return_pct=3, final_equity=1_030_000,
    )
    r = BaselineResult(
        id='b1', session_id='s1', name='buy_and_hold',
        start_date='2024-01-01', end_date='2024-03-01',
        initial_capital=1_000_000, stats=stats, final_equity=1_030_000,
    )
    assert r.name == 'buy_and_hold'
    assert r.stats.total_return_pct == 3
