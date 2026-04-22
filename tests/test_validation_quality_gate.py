"""Post-backtest quality gate — soft-label pass/warn/fail."""


def _stats(**overrides):
    base = {
        'sharpe':              1.2,
        'max_drawdown_pct':   -12.0,
        'trade_count':         30,
        'win_rate':            55.0,
        'max_daily_loss_pct': -2.5,
        'clean_zone_days':     120,
        'divergence_flag':     False,
    }
    base.update(overrides)
    return base


def test_all_green_is_pass():
    from validation.quality_gate import evaluate_quality_gate
    r = evaluate_quality_gate(_stats())
    assert r.label == 'pass'
    assert all(c['ok'] for c in r.criteria.values())


def test_low_sharpe_fails():
    from validation.quality_gate import evaluate_quality_gate
    r = evaluate_quality_gate(_stats(sharpe=0.1))
    assert r.label == 'fail'
    assert r.criteria['min_sharpe']['ok'] is False


def test_drawdown_too_deep_fails():
    from validation.quality_gate import evaluate_quality_gate
    r = evaluate_quality_gate(_stats(max_drawdown_pct=-30.0))
    assert r.label == 'fail'


def test_too_few_trades_fails():
    from validation.quality_gate import evaluate_quality_gate
    r = evaluate_quality_gate(_stats(trade_count=3))
    assert r.label == 'fail'


def test_divergence_flag_fails():
    from validation.quality_gate import evaluate_quality_gate
    r = evaluate_quality_gate(_stats(divergence_flag=True))
    assert r.label == 'fail'


def test_borderline_clean_zone_is_warn():
    from validation.quality_gate import evaluate_quality_gate
    # clean_zone_days=70 >= 60 min but < 60*1.5=90
    r = evaluate_quality_gate(_stats(clean_zone_days=70))
    assert r.label == 'warn'


def test_custom_thresholds_override_defaults():
    from validation.quality_gate import evaluate_quality_gate
    strict = {'min_sharpe': 2.0}
    r = evaluate_quality_gate(_stats(sharpe=1.5), thresholds=strict)
    assert r.label == 'fail'
    assert 'min_sharpe' in r.criteria


def test_missing_stats_key_records_fail_on_that_criterion():
    from validation.quality_gate import evaluate_quality_gate
    stats = _stats()
    del stats['sharpe']
    r = evaluate_quality_gate(stats)
    assert r.label == 'fail'
    assert r.criteria['min_sharpe']['ok'] is False
    assert 'missing' in r.criteria['min_sharpe']['reason']
