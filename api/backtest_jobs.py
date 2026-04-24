"""Async backtest job lifecycle: status, list, SSE stream, cancel."""
from __future__ import annotations

from flask import jsonify

from . import api_bp


@api_bp.route('/backtests/jobs/<session_id>')
def get_backtest_job(session_id):
    """Poll an async backtest job's status."""
    from backtest.jobs import get_status
    status = get_status(session_id)
    if status is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'session_id': status.session_id,
        'state': status.state,
        'progress': status.progress,
        'agent_ids': status.agent_ids,
        'agent_result_ids': status.agent_result_ids,
        'baseline_result_ids': status.baseline_result_ids,
        'error': status.error,
        'submitted_at': status.submitted_at,
        'started_at': status.started_at,
        'finished_at': status.finished_at,
    })


@api_bp.route('/backtests/jobs')
def list_backtest_jobs():
    from backtest.jobs import list_jobs
    return jsonify([
        {
            'session_id': s.session_id,
            'state': s.state,
            'progress': s.progress,
            'agent_ids': s.agent_ids,
            'submitted_at': s.submitted_at,
            'finished_at': s.finished_at,
        }
        for s in list_jobs()
    ])


@api_bp.route('/backtests/jobs/<session_id>/stream')
def stream_backtest_job(session_id):
    """SSE stream: status snapshots + fine-grained events (P3-D §15.6).

    Default channel: status snapshot (only on change).
    Named channels: phase / progress / tool_call / decision / blocked /
                    baseline_done — emitted as `event: <kind>\\ndata: {json}\\n\\n`.
    Stream-level: notfound, timeout, done.
    """
    import json
    import time
    from flask import Response
    from backtest.jobs import get_status

    def _status_snapshot(status) -> str:
        payload = {
            'session_id': status.session_id,
            'state': status.state,
            'progress': status.progress,
            'agent_ids': status.agent_ids,
            'agent_result_ids': status.agent_result_ids,
            'baseline_result_ids': status.baseline_result_ids,
            'error': status.error,
            'submitted_at': status.submitted_at,
            'started_at': status.started_at,
            'finished_at': status.finished_at,
        }
        return f'data: {json.dumps(payload, ensure_ascii=False)}\n\n'

    def _event_line(ev: dict) -> str:
        kind = ev.get('kind', 'unknown')
        return (f'event: {kind}\n'
                f'data: {json.dumps(ev, ensure_ascii=False)}\n\n')

    def generate():
        last_snapshot = None
        last_event_idx = 0
        iterations = 0
        while iterations < 3600:
            status = get_status(session_id)
            if status is None:
                yield 'event: notfound\ndata: {}\n\n'
                return

            snapshot = _status_snapshot(status)
            if snapshot != last_snapshot:
                yield snapshot
                last_snapshot = snapshot

            # Drain new events since last poll
            new_events = status.events[last_event_idx:]
            for ev in new_events:
                yield _event_line(ev)
            last_event_idx = len(status.events)

            if status.state in ('complete', 'failed'):
                yield 'event: done\ndata: {}\n\n'
                return

            time.sleep(0.5)
            iterations += 1
        yield 'event: timeout\ndata: {}\n\n'

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
    })


@api_bp.route('/backtests/jobs/<session_id>/cancel', methods=['POST'])
def cancel_backtest_job(session_id):
    """Mark a running job for cancellation."""
    from backtest.jobs import cancel
    if cancel(session_id):
        return jsonify({'session_id': session_id, 'state': 'cancelling'})
    return jsonify({'error': 'job not found or already terminal'}), 404
