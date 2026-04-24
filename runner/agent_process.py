"""Per-agent subprocess — loads agent, ticks on schedule, emits proposals.

Usage: python -m runner.agent_process --agent-id AGENT --flask-url URL

Phase 1: NEVER places real TDX trades. Emits proposals for user approval only.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from datetime import datetime


_LOG = logging.getLogger(__name__)


def _configure_vnpy_if_needed():
    """Best-effort vnpy configure — ignored if unavailable (e.g. in tests)."""
    try:
        from scripts.setup.vnpy_config import configure
        configure()
    except Exception:
        pass


class _ShutdownFlag:
    """Global flag so SIGTERM handler can signal the main loop."""
    stop = False


def _handle_sigterm(signum, frame):  # noqa: ARG001
    _ShutdownFlag.stop = True


def run(agent_id: str, flask_url: str, max_ticks: int | None = None) -> int:
    """Run the per-agent loop. Returns process exit code.

    max_ticks caps the loop for testability; None = infinite until SIGTERM.
    """
    _configure_vnpy_if_needed()

    signal.signal(signal.SIGTERM, _handle_sigterm)
    if hasattr(signal, 'SIGBREAK'):  # Windows
        signal.signal(signal.SIGBREAK, _handle_sigterm)

    import storage
    from agents.runner import AgentRunner
    from llm.factory import build_llm
    from runner.scheduler import next_tick
    from runner.proposal_emitter import emit_proposal

    agent = storage.agents().get(agent_id)
    if agent is None:
        _LOG.error('agent %s not found', agent_id)
        return 2
    persona = storage.personas().get(agent.persona_id)
    if persona is None:
        _LOG.error('persona %s not found', agent.persona_id)
        return 2
    schedule = persona.default_schedule

    llm = build_llm(agent.model_id)
    runner = AgentRunner(llm=llm)

    tick_count = 0
    while not _ShutdownFlag.stop:
        now = datetime.now()
        target = next_tick(schedule, now)
        seconds_to_wait = max(0, (target - now).total_seconds())

        # Sleep in 1-second slices so SIGTERM is responsive
        slept = 0.0
        while slept < seconds_to_wait and not _ShutdownFlag.stop:
            time.sleep(min(1.0, seconds_to_wait - slept))
            slept += 1.0

        if _ShutdownFlag.stop:
            break

        # Fire the tick — build a minimal portfolio (Phase 1 stub: all cash)
        portfolio = {
            'cash': float(agent.initial_capital),
            'equity': float(agent.initial_capital),
            'positions': {},
        }
        decisions = runner.run_day(
            agent_id=agent_id,
            date=datetime.now().strftime('%Y-%m-%d'),
            portfolio=portfolio,
            market_context={},
            mark_prices={},
        )
        for decision in decisions:
            try:
                emit_proposal(flask_url, agent_id, decision)
            except Exception as exc:  # noqa: BLE001
                _LOG.error('proposal emit failed: %s', exc)

        tick_count += 1
        if max_ticks is not None and tick_count >= max_ticks:
            break

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Per-agent subprocess (P3-F Phase 1, no real trades)')
    parser.add_argument('--agent-id', required=True)
    parser.add_argument(
        '--flask-url', default='http://127.0.0.1:5000',
        help='Flask base URL for proposal POSTs')
    parser.add_argument('--max-ticks', type=int, default=None,
                        help='Stop after N ticks (for testing)')
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    return run(args.agent_id, args.flask_url, args.max_ticks)


if __name__ == '__main__':
    sys.exit(main())
