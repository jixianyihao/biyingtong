"""P3-D SSE fine-grained events — Event shape, emitter, runner hooks."""
from __future__ import annotations

import pytest


def test_job_status_has_events_list():
    from backtest.jobs import JobStatus
    s = JobStatus(session_id='s1')
    assert hasattr(s, 'events')
    assert s.events == []


def test_emit_event_appends_to_status():
    from backtest.jobs import JobStatus, emit_event
    s = JobStatus(session_id='s1')
    emit_event(s, {'kind': 'phase', 'phase': 'running'})
    assert len(s.events) == 1
    e = s.events[0]
    assert e['kind'] == 'phase'
    assert e['phase'] == 'running'
    assert 'ts' in e


def test_emit_event_preserves_explicit_ts():
    from backtest.jobs import JobStatus, emit_event
    s = JobStatus(session_id='s1')
    emit_event(s, {'kind': 'progress', 'ts': 12345.67, 'date': '2025-01-02'})
    assert s.events[0]['ts'] == 12345.67
