"""Run all three MVP baselines concurrently under a shared session."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

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
    jobs = [
        (run_buy_and_hold, dict(universe=universe, **common)),
        (run_equal_weight, dict(universe=universe, **common)),
        (run_csi300, dict(**common)),
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(fn, **kw) for fn, kw in jobs]
        results = [f.result() for f in futures]
    return results
