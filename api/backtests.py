"""GET /api/backtests — list + detail + per-session aggregated view."""
from __future__ import annotations

from dataclasses import asdict

from flask import jsonify, request

from . import api_bp


def _result_to_dict(r) -> dict:
    from backtest.divergence import compute_divergence
    flag, metric = compute_divergence(r.zone_stats)
    return {
        'id': r.id,
        'session_id': r.session_id,
        'agent_id': r.agent_id,
        'persona_id': r.persona_id,
        'model_id': r.model_id,
        'start_date': r.start_date,
        'end_date': r.end_date,
        'initial_capital': r.initial_capital,
        'final_equity': r.final_equity,
        'stats': asdict(r.stats),
        'zone_stats': [asdict(z) for z in r.zone_stats],
        'quality_gate_label': r.quality_gate_label,
        'quality_gate_criteria': r.quality_gate_criteria,
        'divergence_flag': flag,
        'divergence_metric': metric,
        'kind': getattr(r, 'kind', 'agent'),
    }


@api_bp.route('/backtests')
def list_backtests():
    """List backtests. Without agent_id -> global most-recent list."""
    import storage
    agent_id = request.args.get('agent_id')
    limit = int(request.args.get('limit', '50'))
    if agent_id:
        rows = storage.backtests().list_for_agent(agent_id, limit=limit)
    else:
        rows = storage.backtests().list_all(limit=limit)
    return jsonify([_result_to_dict(r) for r in rows])


@api_bp.route('/backtests/sessions')
def list_backtest_sessions():
    """Distinct sessions ordered by most recent, with aggregate info.

    Returns:
      [
        {
          session_id: str,
          start_date: str, end_date: str,
          agent_ids: list[str],
          agent_count: int,
          baseline_count: int,
          created_at: str,
          notes: str | null,
        },
        ...
      ]
    """
    limit = int(request.args.get('limit', '50'))
    import storage
    return jsonify(storage.backtests().list_sessions(limit))


@api_bp.route('/backtests/<result_id>')
def get_backtest(result_id):
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify(_result_to_dict(r))


@api_bp.route('/backtests/session/<session_id>')
def get_session(session_id):
    """Composite view: all agent backtests + baselines under one session."""
    import storage
    from backtest.baselines.base import BaselineResult  # noqa: F401

    agent_results = storage.backtests().list_for_session(session_id)
    baseline_results = storage.baselines().list_for_session(session_id)

    def _baseline_to_dict(b) -> dict:
        return {
            'id': b.id,
            'session_id': b.session_id,
            'name': b.name,
            'start_date': b.start_date,
            'end_date': b.end_date,
            'initial_capital': b.initial_capital,
            'final_equity': b.final_equity,
            'stats': asdict(b.stats),
        }

    return jsonify({
        'session_id': session_id,
        'agents': [_result_to_dict(r) for r in agent_results],
        'baselines': [_baseline_to_dict(b) for b in baseline_results],
    })


@api_bp.route('/backtests', methods=['POST'])
def start_backtest():
    """Kick off an async backtest.

    Body: {
      agent_ids: [str, ...],
      start_date: 'YYYY-MM-DD',
      end_date: 'YYYY-MM-DD',
      initial_capital: float,
      universe: [str, ...],
      include_baselines: bool (default True),
      session_id: str (optional — generated if absent)
    }

    Returns 202 + {session_id, state}.
    """
    import uuid
    body = request.get_json(silent=True) or {}
    agent_ids = body.get('agent_ids')
    start_date = body.get('start_date')
    end_date = body.get('end_date')
    initial_capital = body.get('initial_capital')
    universe = body.get('universe')
    if not (isinstance(agent_ids, list) and agent_ids
            and start_date and end_date
            and isinstance(universe, list) and universe
            and initial_capital is not None):
        return jsonify({'error': 'agent_ids, start_date, end_date, '
                                 'initial_capital, universe required'}), 400

    # Sanity: agents must exist
    import storage
    for aid in agent_ids:
        if storage.agents().get(aid) is None:
            return jsonify({'error': f'unknown agent_id: {aid}'}), 404

    session_id = body.get('session_id') or f'session-{uuid.uuid4().hex[:12]}'
    include_baselines = bool(body.get('include_baselines', True))

    from backtest.jobs import submit_backtest
    status = submit_backtest(
        session_id=session_id, agent_ids=agent_ids,
        start_date=start_date, end_date=end_date,
        initial_capital=float(initial_capital), universe=universe,
        include_baselines=include_baselines,
    )
    return jsonify({
        'session_id': session_id,
        'state': status.state,
    }), 202


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


@api_bp.route('/backtests/<result_id>/monthly_returns')
def get_backtest_monthly_returns(result_id):
    """Returns {result_id, monthly_returns: [{year, month, return_pct, days}]}."""
    import storage
    from backtest.stats import compute_monthly_returns
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'result_id': result_id,
        'monthly_returns': compute_monthly_returns(r.daily_records or []),
    })


@api_bp.route('/backtests/<result_id>', methods=['DELETE'])
def delete_backtest(result_id):
    import storage
    if storage.backtests().get(result_id) is None:
        return jsonify({'error': 'not_found'}), 404
    storage.backtests().delete(result_id)
    return '', 204


@api_bp.route('/backtests/<result_id>/rating')
def get_backtest_rating(result_id):
    """Compute + return 5-sub-score strategy rating for a backtest result."""
    import storage
    from dataclasses import asdict
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    from rating.strategy_rating import compute_strategy_rating
    rating = compute_strategy_rating(r)
    return jsonify({
        **asdict(rating),
        'notes': list(rating.notes),
    })


@api_bp.route('/backtests/<result_id>/nav')
def get_backtest_nav(result_id):
    """Daily equity curve for one backtest + same-session baselines.

    Response: {
      'result_id': str,
      'agent': [{date, equity, cash, pnl_pct}, ...],
      'baselines': [{name, curve: [{date, equity}, ...]}, ...]
    }

    Baselines don't persist per-day equity yet (P3-A Task 6 / future).
    Return empty curves for now; frontend tolerates.
    """
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    agent_curve = [
        {'date': rec.get('date'),
         'equity': rec.get('equity'),
         'cash': rec.get('cash'),
         'pnl_pct': rec.get('pnl_pct')}
        for rec in (r.daily_records or [])
    ]
    baselines_payload = []
    for b in storage.baselines().list_for_session(r.session_id):
        b_records = getattr(b, 'daily_records', None) or []
        b_curve = [{'date': rec.get('date'), 'equity': rec.get('equity')}
                   for rec in b_records]
        baselines_payload.append({'name': b.name, 'curve': b_curve})
    return jsonify({
        'result_id': result_id,
        'agent': agent_curve,
        'baselines': baselines_payload,
    })


@api_bp.route('/backtests/<result_id>/trades')
def get_backtest_trades(result_id):
    """Ordered list of fills for a backtest.

    Response: {result_id, trades: [{date, code, action, shares, price, fee}, ...]}
    """
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'result_id': result_id,
        'trades': list(r.trades or []),
    })


@api_bp.route('/backtests/<result_id>/thinking')
def get_backtest_thinking(result_id):
    """Per-day LLM reasoning + tool_calls + decisions for a backtest.

    Response: {result_id, thinking: [{date, reasoning, tool_calls, decisions}, ...]}
    """
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'result_id': result_id,
        'thinking': list(r.thinking or []),
    })


@api_bp.route('/backtests/rule', methods=['POST'])
def start_rule_backtest():
    """Synchronous rule-strategy backtest. Can join an existing session."""
    import uuid
    body = request.get_json(silent=True) or {}
    strategy_name = body.get('strategy_name')
    params = body.get('params') or {}
    start_date = body.get('start_date')
    end_date = body.get('end_date')
    universe = body.get('universe')
    initial_capital = body.get('initial_capital')
    if not (strategy_name and start_date and end_date
            and isinstance(universe, list) and universe
            and initial_capital is not None):
        return jsonify({'error': 'strategy_name, start_date, end_date, '
                                  'universe, initial_capital required'}), 400

    from backtest.strategies import get as get_strategy, build
    if get_strategy(strategy_name) is None:
        return jsonify({'error': f'unknown strategy: {strategy_name!r}'}), 400

    try:
        strategy = build(strategy_name, params=params)
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': f'strategy build failed: {e}'}), 400

    session_id = body.get('session_id') or f'session-{uuid.uuid4().hex[:12]}'

    from backtest.rule_runner import RuleRunner
    try:
        result = RuleRunner(strategy=strategy).run(
            session_id=session_id,
            start_date=start_date, end_date=end_date,
            initial_capital=float(initial_capital),
            universe=universe,
        )
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': f'run failed: {e}'}), 500

    return jsonify({
        'session_id': session_id,
        'result_id': result.id,
        'state': 'complete',
    }), 202
