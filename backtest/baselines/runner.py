"""Run all three MVP baselines under a shared session."""
from __future__ import annotations

from .buy_and_hold import run_buy_and_hold
from .csi300 import run_csi300
from .equal_weight import run_equal_weight


def run_all(*, session_id: str, start_date: str, end_date: str,
            initial_capital: float, universe: list[str]) -> list:
    common = dict(
        session_id=session_id,
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital,
    )
    results = []
    # Buy and hold
    results.append(run_buy_and_hold(universe=universe, **common))
    # Equal weight
    results.append(run_equal_weight(universe=universe, **common))
    # CSI 300 (index-only, no universe arg)
    results.append(run_csi300(**common))
    return results
