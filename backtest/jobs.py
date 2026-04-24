"""In-memory async backtest job tracker.

Start one with ``submit_backtest(...)``, poll status with ``get_status(session_id)``.
When the API process restarts, jobs are lost — but the actual BacktestResult /
BaselineResult rows they wrote live on in SQLite. Good enough for MVP.
"""
from __future__ import annotations

import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field


@dataclass
class JobStatus:
    session_id: str
    state: str = 'queued'        # 'queued' | 'running' | 'complete' | 'failed' | 'cancelled'
    progress: str = ''            # free-text most-recent step
    agent_ids: list = field(default_factory=list)
    agent_result_ids: list = field(default_factory=list)
    baseline_result_ids: list = field(default_factory=list)
    error: str | None = None
    submitted_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    events: list = field(default_factory=list)
    cancel_requested: bool = False


def emit_event(status: JobStatus, event: dict) -> None:
    """Append an event to the job's event log. Auto-populates ts if missing.
    Thread-safety: caller must ensure single-writer-per-job (jobs.py's worker
    thread already provides this)."""
    if 'ts' not in event:
        event['ts'] = time.time()
    status.events.append(event)


_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='bt-job')
_lock = threading.Lock()
_jobs: dict[str, JobStatus] = {}


def get_status(session_id: str) -> JobStatus | None:
    with _lock:
        return _jobs.get(session_id)


def list_jobs() -> list[JobStatus]:
    with _lock:
        return list(_jobs.values())


def cancel(session_id: str) -> bool:
    """Mark a job for cancellation. Returns True if found + flagged."""
    with _lock:
        s = _jobs.get(session_id)
        if s is None or s.state in ('complete', 'failed', 'cancelled'):
            return False
        s.cancel_requested = True
    return True


def submit_backtest(
    *,
    session_id: str,
    agent_ids: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float,
    universe: list[str],
    include_baselines: bool = True,
) -> JobStatus:
    """Queue an async backtest: N agents parallel + optional baselines. Returns status."""
    status = JobStatus(
        session_id=session_id,
        state='queued',
        agent_ids=list(agent_ids),
    )

    def _run():
        # Grab _lock first so callers observing st.state right after
        # submit_backtest returns see 'queued' until we get a chance to flip
        # to 'running'. Since submit_backtest holds _lock across _pool.submit,
        # this call blocks until the caller releases.
        with _lock:
            pass
        try:
            status.state = 'running'
            status.started_at = time.time()
            emit_event(status, {'kind': 'phase', 'phase': 'data_loading',
                                'session_id': session_id})

            from llm.factory import build_llm
            import backtest.multi_agent_runner as _mar

            status.progress = 'building LLM adapters'
            import storage
            configs = []
            for aid in agent_ids:
                a = storage.agents().get(aid)
                if a is None:
                    raise ValueError(f'unknown agent_id: {aid}')
                llm = build_llm(a.model_id)
                configs.append({'agent_id': aid, 'llm': llm})

            emit_event(status, {'kind': 'phase', 'phase': 'running',
                                'session_id': session_id})
            status.progress = f'running {len(configs)} agents in parallel'

            def _on_event(ev):
                emit_event(status, ev)

            def _cancel_check():
                return status.cancel_requested

            results = _mar.run_multi(
                session_id=session_id, agent_configs=configs,
                start_date=start_date, end_date=end_date,
                initial_capital=initial_capital, universe=universe,
                on_event=_on_event,
                cancel_check=_cancel_check,
            )
            status.agent_result_ids = [r.id for r in results]

            if include_baselines and not status.cancel_requested:
                emit_event(status, {'kind': 'phase', 'phase': 'baselines',
                                    'session_id': session_id})
                status.progress = 'running baselines'
                import backtest.baselines.runner as _bl_runner
                baselines = _bl_runner.run_all(
                    session_id=session_id,
                    start_date=start_date, end_date=end_date,
                    initial_capital=initial_capital, universe=universe,
                )
                for b in baselines:
                    emit_event(status, {'kind': 'baseline_done',
                                        'baseline_name': getattr(b, 'name', None),
                                        'result_id': getattr(b, 'id', None)})
                status.baseline_result_ids = [b.id for b in baselines]

            if status.cancel_requested:
                status.progress = 'cancelled'
                status.state = 'cancelled'
                emit_event(status, {'kind': 'cancelled', 'session_id': session_id})
            else:
                status.progress = 'done'
                status.state = 'complete'
                emit_event(status, {'kind': 'done', 'session_id': session_id})
        except Exception as e:  # noqa: BLE001
            status.state = 'failed'
            status.error = f'{type(e).__name__}: {e}\n{traceback.format_exc()[:500]}'
            emit_event(status, {'kind': 'failed', 'session_id': session_id,
                                'error': status.error})
        finally:
            status.finished_at = time.time()

    with _lock:
        _jobs[session_id] = status
        _pool.submit(_run)
    return status
