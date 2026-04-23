"""Cross-cutoff divergence detector.

Fires when pollution-zone returns materially exceed clean-zone returns
(classic training-data-memorization signature). Requires >=10 days in each zone.
"""
from __future__ import annotations

_MIN_DAYS = 10
_DEFAULT_THRESHOLD = 0.5  # 50% relative distance


def compute_divergence(zone_stats: list, threshold: float = _DEFAULT_THRESHOLD):
    """Return (flag, metric).

    flag=True when |pollution_return - clean_return| / (|p|+|c|+eps) > threshold
    and both zones have >= _MIN_DAYS of data. Otherwise fail-open.
    """
    by_zone = {z.zone: z for z in zone_stats}
    pollution = by_zone.get('pollution')
    clean = by_zone.get('clean')
    if pollution is None or clean is None:
        return False, None
    if pollution.days < _MIN_DAYS or clean.days < _MIN_DAYS:
        return False, None
    if not pollution.stats or not clean.stats:
        return False, None
    p = float(pollution.stats.get('total_return_pct', 0.0))
    c = float(clean.stats.get('total_return_pct', 0.0))
    denom = abs(p) + abs(c) + 1e-6
    metric = abs(p - c) / denom
    return (metric > threshold), metric
