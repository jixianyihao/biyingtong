"""Run N agents in parallel over the same window + universe.

Each agent runs in its own thread with its own BacktestRunner + Book. SQLite
WAL mode handles concurrent writes to agent_state.db. API latency is the
dominant cost; parallelizing agents gives linear speedup up to ~4 threads.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .runner import BacktestRunner


def run_multi(*, session_id: str,
              agent_configs: list[dict],
              start_date: str, end_date: str,
              initial_capital: float,
              universe: list[str],
              max_workers: int = 4) -> list:
    """agent_configs: [{'agent_id': str, 'llm': LLMBase}, ...]

    Returns list of BacktestResult in the order the futures complete.
    """
    import storage
    agent_ids = [c['agent_id'] for c in agent_configs]
    storage.backtests().create_session(
        session_id, start_date, end_date, agent_ids,
    )

    def _one(cfg):
        runner = BacktestRunner(llm=cfg['llm'])
        return runner.run(
            session_id=session_id, agent_id=cfg['agent_id'],
            start_date=start_date, end_date=end_date,
            initial_capital=initial_capital, universe=universe,
        )

    with ThreadPoolExecutor(max_workers=min(max_workers, len(agent_configs))) as pool:
        futures = [pool.submit(_one, cfg) for cfg in agent_configs]
        return [f.result() for f in futures]
