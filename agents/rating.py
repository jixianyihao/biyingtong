"""Trust rating classifier (Spec § 8.2)."""
from __future__ import annotations


def classify_rating(health: int) -> str:
    h = max(0, int(health))
    if h >= 90:
        return 'A+'
    if h >= 80:
        return 'A'
    if h >= 60:
        return 'B'
    return 'C'
