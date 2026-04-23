"""Cross-cutoff zone classification.

A model's training_cutoff splits backtest time into three zones:
  pollution — date < cutoff: model may have memorized outcomes
  buffer    — [cutoff, cutoff + buffer_days): partial leakage possible
  clean     — date >= cutoff + buffer_days: genuinely out-of-sample

Default buffer = 60 days (DEFAULT_QUALITY_GATE['min_clean_zone_days']).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta


_DEFAULT_BUFFER_DAYS = 60


def _parse_cutoff(cutoff: str | date) -> date:
    if isinstance(cutoff, date) and not isinstance(cutoff, datetime):
        return cutoff
    if isinstance(cutoff, datetime):
        return cutoff.date()
    return datetime.strptime(cutoff, '%Y-%m-%d').date()


def classify_date(d: date, cutoff: str | date,
                  buffer_days: int = _DEFAULT_BUFFER_DAYS) -> str:
    c = _parse_cutoff(cutoff)
    clean_start = c + timedelta(days=buffer_days)
    if d < c:
        return 'pollution'
    if d < clean_start:
        return 'buffer'
    return 'clean'


def zone_windows(days: list, cutoff: str | date,
                 buffer_days: int = _DEFAULT_BUFFER_DAYS) -> dict:
    out = {'pollution': [], 'buffer': [], 'clean': []}
    for d in days:
        out[classify_date(d, cutoff, buffer_days)].append(d)
    return out
