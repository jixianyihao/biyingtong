"""Zone divergence metric."""


def _zone(zone, days, total_return):
    from backtest.base import ZoneStats
    return ZoneStats(
        zone=zone, days=days,
        stats={'total_return_pct': total_return, 'sharpe': 1.0,
               'max_drawdown_pct': -5, 'trade_count': 5,
               'win_rate': 50, 'max_daily_loss_pct': -1,
               'final_equity': 100_000},
    )


def test_flag_false_when_pollution_and_clean_match():
    from backtest.divergence import compute_divergence
    zones = [_zone('pollution', 60, 10.0),
             _zone('buffer', 10, 5.0),
             _zone('clean', 60, 10.5)]
    flag, metric = compute_divergence(zones)
    assert flag is False


def test_flag_true_when_pollution_far_exceeds_clean():
    """Classic memorization pattern: 20% in pollution, -5% in clean."""
    from backtest.divergence import compute_divergence
    zones = [_zone('pollution', 60, 20.0),
             _zone('buffer', 10, 0.0),
             _zone('clean', 60, -5.0)]
    flag, metric = compute_divergence(zones)
    assert flag is True
    assert metric is not None and metric > 0.5


def test_insufficient_clean_days_fails_open():
    from backtest.divergence import compute_divergence
    zones = [_zone('pollution', 60, 20.0),
             _zone('buffer', 5, 0.0),
             _zone('clean', 5, -5.0)]  # only 5 clean days
    flag, metric = compute_divergence(zones)
    assert flag is False
    assert metric is None


def test_missing_zone_fails_open():
    from backtest.divergence import compute_divergence
    from backtest.base import ZoneStats
    zones = [ZoneStats('pollution', 60, {}),
             ZoneStats('buffer', 10, {}),
             ZoneStats('clean', 0, {})]
    flag, _ = compute_divergence(zones)
    assert flag is False


def test_custom_threshold():
    from backtest.divergence import compute_divergence
    zones = [_zone('pollution', 60, 10.0),
             _zone('buffer', 10, 5.0),
             _zone('clean', 60, 5.0)]
    # p=10, c=5 → metric = 5/15 = 0.333. Below 0.5 default → False
    flag_default, metric = compute_divergence(zones)
    assert flag_default is False
    # With tighter threshold 0.2 → True
    flag_strict, _ = compute_divergence(zones, threshold=0.2)
    assert flag_strict is True
