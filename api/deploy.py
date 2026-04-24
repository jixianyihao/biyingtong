"""Deploy / stop / status endpoints for agent subprocesses (P3-F Phase 1).

Phase 1 guarantee: the spawned subprocess emits proposals for user approval.
NO real-money execution happens here — approve/reject are DB-only state
changes (see api/proposals.py).
"""
from __future__ import annotations

from flask import jsonify, request

from . import api_bp


def _spawn_subprocess(agent_id: str, flask_url: str):
    """Spawn the per-agent subprocess. Extracted for test monkeypatching."""
    import subprocess
    import sys
    kwargs = {}
    if sys.platform == 'win32':
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs['start_new_session'] = True
    return subprocess.Popen(
        [sys.executable, '-m', 'runner.agent_process',
         '--agent-id', agent_id, '--flask-url', flask_url],
        **kwargs,
    )


def _terminate_subprocess(pid: int):
    """Send a stop signal. Extracted for test monkeypatching."""
    import os
    import signal
    import sys
    if sys.platform == 'win32':
        try:
            os.kill(pid, signal.CTRL_BREAK_EVENT)
        except (OSError, ValueError):
            pass
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


@api_bp.route('/agents/<agent_id>/deploy', methods=['POST'])
def deploy_agent(agent_id):
    """Spawn a subprocess for the agent. No real trades will ever happen —
    the subprocess only emits proposals for user approval.

    Body (optional): {"schedule": "daily"|"weekly"|"intraday_5m"} to override
    the persona's default_schedule.
    """
    import storage
    agent = storage.agents().get(agent_id)
    if agent is None:
        return jsonify({'error': 'not_found'}), 404

    existing = storage.deployed_agents().get(agent_id)
    if existing and existing.status == 'running':
        return jsonify({'error': 'already deployed',
                        'pid': existing.pid}), 409

    body = request.get_json(silent=True) or {}
    persona = storage.personas().get(agent.persona_id)
    schedule = body.get('schedule') or (
        persona.default_schedule if persona else 'daily')

    flask_url = request.host_url.rstrip('/')  # e.g. http://127.0.0.1:5000
    proc = _spawn_subprocess(agent_id, flask_url)
    storage.deployed_agents().upsert(agent_id, pid=proc.pid, schedule=schedule)
    return jsonify({
        'agent_id': agent_id,
        'pid': proc.pid,
        'schedule': schedule,
        'status': 'running',
    }), 202


@api_bp.route('/agents/<agent_id>/stop', methods=['POST'])
def stop_agent(agent_id):
    """Send SIGTERM/CTRL_BREAK_EVENT to the agent's subprocess and mark
    the deployment as stopped in the DB."""
    import storage
    d = storage.deployed_agents().get(agent_id)
    if d is None or d.status != 'running':
        return jsonify({'error': 'not deployed'}), 404
    _terminate_subprocess(d.pid)
    storage.deployed_agents().mark_stopped(agent_id)
    return jsonify({'agent_id': agent_id, 'status': 'stopped'})


@api_bp.route('/agents/<agent_id>/deploy_status')
def deploy_status(agent_id):
    """Return the deployment row for an agent, or 404 if never deployed."""
    import storage
    d = storage.deployed_agents().get(agent_id)
    if d is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'agent_id': d.agent_id,
        'pid': d.pid,
        'started_at': d.started_at,
        'status': d.status,
        'schedule': d.schedule,
    })
