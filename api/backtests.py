"""GET /api/backtests — list + detail + per-session aggregated view."""
from __future__ import annotations

from dataclasses import asdict

from flask import jsonify, request

from . import api_bp


def _result_to_dict(r) -> dict:
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
    }


@api_bp.route('/backtests')
def list_backtests():
    """List recent backtests. Optional filter: ?agent_id=..."""
    import storage
    agent_id = request.args.get('agent_id')
    limit = int(request.args.get('limit', '50'))
    if agent_id:
        rows = storage.backtests().list_for_agent(agent_id, limit=limit)
    else:
        # No global list method on store; caller should filter by agent_id
        return jsonify({'error': 'agent_id query param required'}), 400
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
    import json as _json
    import sqlite3
    import storage
    from flask import request as req

    limit = int(req.args.get('limit', '50'))
    # Use the configured store's db path so tests with tmp_path work.
    db_path = storage.backtests()._db_path
    con = sqlite3.connect(db_path)
    try:
        try:
            rows = con.execute(
                '''SELECT s.id, s.start_date, s.end_date, s.agent_ids,
                          s.notes, s.created_at,
                          (SELECT COUNT(*) FROM backtest_results
                               WHERE session_id=s.id) AS agent_ct,
                          (SELECT COUNT(*) FROM baseline_results
                               WHERE session_id=s.id) AS baseline_ct
                   FROM backtest_sessions s
                   ORDER BY s.created_at DESC LIMIT ?''',
                (limit,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
    finally:
        con.close()
    return jsonify([
        {
            'session_id': r[0],
            'start_date': r[1],
            'end_date': r[2],
            'agent_ids': _json.loads(r[3]) if r[3] else [],
            'notes': r[4],
            'created_at': r[5],
            'agent_count': r[6],
            'baseline_count': r[7],
        }
        for r in rows
    ])


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
