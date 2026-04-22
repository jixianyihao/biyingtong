"""Post-backtest quality gate — soft labels based on DEFAULT_QUALITY_GATE."""
from __future__ import annotations

from .base import DEFAULT_QUALITY_GATE, QualityGateResult


# (threshold_key, stats_key, direction)
# direction = 'ge' : stats_value must be >= threshold
#             'le' : stats_value must be <= threshold (threshold is negative)
#             'eq_false' : stats_value equals threshold (for divergence_flag: False means ok)
_CRITERIA = [
    ('min_sharpe',           'sharpe',              'ge'),
    ('max_drawdown_pct',     'max_drawdown_pct',    'ge'),
    ('min_trade_count',      'trade_count',         'ge'),
    ('min_win_rate',         'win_rate',            'ge'),
    ('max_daily_loss_pct',   'max_daily_loss_pct',  'ge'),
    ('min_clean_zone_days',  'clean_zone_days',     'ge'),
    ('max_divergence_flag',  'divergence_flag',     'eq_false'),
]


_WARN_BORDER_MULT = 1.5  # clean_zone_days < min*1.5 → warn


def evaluate_quality_gate(
    stats: dict, thresholds: dict | None = None,
) -> QualityGateResult:
    t = dict(DEFAULT_QUALITY_GATE)
    if thresholds:
        t.update(thresholds)

    criteria = {}
    any_fail = False
    any_borderline = False

    for thresh_key, stat_key, direction in _CRITERIA:
        if thresh_key not in t:
            continue
        threshold = t[thresh_key]
        actual = stats.get(stat_key)
        if actual is None:
            criteria[thresh_key] = {
                'ok': False, 'actual': None, 'threshold': threshold,
                'reason': f'missing stats[{stat_key!r}]',
            }
            any_fail = True
            continue

        if direction == 'ge':
            ok = actual >= threshold
            if ok and thresh_key == 'min_clean_zone_days':
                if actual < threshold * _WARN_BORDER_MULT:
                    any_borderline = True
        elif direction == 'le':
            ok = actual <= threshold
        elif direction == 'eq_false':
            ok = bool(actual) == bool(threshold)
        else:
            ok = False

        criteria[thresh_key] = {
            'ok': ok, 'actual': actual, 'threshold': threshold,
            'reason': '' if ok else f'{stat_key}={actual} fails vs {threshold}',
        }
        if not ok:
            any_fail = True

    if any_fail:
        label = 'fail'
    elif any_borderline:
        label = 'warn'
    else:
        label = 'pass'
    return QualityGateResult(label=label, criteria=criteria)
