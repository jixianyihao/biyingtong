"""Trust rating classifier (Spec § 8.2)."""
from __future__ import annotations

from datetime import datetime, timedelta


def classify_rating(health: int) -> str:
    h = max(0, int(health))
    if h >= 90:
        return 'A+'
    if h >= 80:
        return 'A'
    if h >= 60:
        return 'B'
    return 'C'


def compute_health(agent_id: str,
                   *, live_deviation_pts: int = 0,
                   window_days: int = 7) -> int:
    """Health score per Spec § 8.1.

    violations_7d + parse_failures_7d come from audit_log. live_deviation_pts
    is a caller-supplied measure (0 in MVP since live mode is not wired).
    """
    import storage
    audit = storage.audit()
    rows = audit.query_by_agent(agent_id, limit=10_000)
    # Filter by timestamp within window (keeps the store interface simple)
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    violations = 0
    parse_failures = 0
    for r in rows:
        ts = r.get('timestamp')
        try:
            dt = datetime.strptime(ts[:19], '%Y-%m-%d %H:%M:%S')
        except Exception:
            dt = datetime.utcnow()  # fall back to now (include)
        if dt < cutoff:
            continue
        if r['kind'] == 'validation' and r.get('details', {}).get('outcome') \
                in ('rejected', 'modified'):
            violations += 1
        elif r['kind'] == 'parse_failure':
            parse_failures += 1
    raw = 100 - violations * 3 - live_deviation_pts * 2 - parse_failures
    return max(0, raw)
