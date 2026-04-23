"""Daily P&L list → BacktestStats + ZoneStats."""
from datetime import date


def _day(d, pnl=0.1, equity=100.0, trades=0, won=0):
    return {'date': d, 'pnl_pct': pnl, 'equity': equity,
            'trade_count': trades, 'won': won}


def test_empty_returns_zero_stats():
    from backtest.stats import aggregate
    stats, zones = aggregate([], cutoff='2024-06-01',
                             initial_capital=1_000_000.0)
    assert stats.trade_count == 0
    assert stats.final_equity == 1_000_000.0


def test_monotonic_positive_gives_positive_return():
    from backtest.stats import aggregate
    days = [_day(date(2024, 1, i), pnl=1.0, equity=100 + i)
            for i in range(1, 11)]
    stats, _ = aggregate(days, cutoff='2024-06-01',
                         initial_capital=100.0)
    assert stats.total_return_pct > 0
    assert stats.max_drawdown_pct <= 0
    assert stats.max_daily_loss_pct >= -1.0


def test_drawdown_computed():
    from backtest.stats import aggregate
    # equity: 110 → 90 → 95 (peak 110, trough 90, dd = (90-110)/110 = -18.18%)
    days = [
        _day(date(2024, 1, 1), pnl=10.0, equity=110),
        _day(date(2024, 1, 2), pnl=-18.18, equity=90),
        _day(date(2024, 1, 3), pnl=5.56, equity=95),
    ]
    stats, _ = aggregate(days, cutoff='2024-06-01', initial_capital=100.0)
    assert round(stats.max_drawdown_pct, 1) == -18.2


def test_win_rate():
    from backtest.stats import aggregate
    days = [
        _day(date(2024, 1, 1), trades=2, won=1),
        _day(date(2024, 1, 2), trades=3, won=2),
    ]
    stats, _ = aggregate(days, cutoff='2024-06-01',
                         initial_capital=100.0)
    assert stats.trade_count == 5
    assert round(stats.win_rate, 1) == 60.0


def test_zones_split_correctly():
    from backtest.stats import aggregate
    days = [
        _day(date(2024, 5, 15), pnl=1.0, equity=101),  # pollution
        _day(date(2024, 6, 15), pnl=0.5, equity=101.5),  # buffer
        _day(date(2024, 9, 1), pnl=0.5, equity=102),   # clean
    ]
    stats, zones = aggregate(days, cutoff='2024-06-01',
                             initial_capital=100.0)
    z_by_zone = {z.zone: z for z in zones}
    assert z_by_zone['pollution'].days == 1
    assert z_by_zone['buffer'].days == 1
    assert z_by_zone['clean'].days == 1


def test_single_day_zone_has_empty_stats():
    """A single day can't produce Sharpe — zone.stats should be {} when days<2."""
    from backtest.stats import aggregate
    days = [_day(date(2024, 9, 1), pnl=1.0, equity=101)]
    stats, zones = aggregate(days, cutoff='2024-06-01',
                             initial_capital=100.0)
    clean = [z for z in zones if z.zone == 'clean'][0]
    assert clean.stats == {}
