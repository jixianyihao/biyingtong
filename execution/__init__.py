"""Execution adapters — abstraction over order submission.

Default mode: dry_run (MockExecutionAdapter). Set BIYINGTONG_EXECUTION_MODE=live
to engage TDXExecutionAdapter. See plan 2026-04-24-p3f-phase2-execution.md.
"""
from __future__ import annotations

import os

from .adapter import ExecutionAdapter, ExecutionResult
from .mock import MockExecutionAdapter
from .tdx import TDXExecutionAdapter

__all__ = [
    'ExecutionAdapter', 'ExecutionResult',
    'MockExecutionAdapter', 'TDXExecutionAdapter',
    'get_adapter',
]


_VALID_MODES = ('dry_run', 'live')


def get_adapter() -> ExecutionAdapter:
    """Factory reading BIYINGTONG_EXECUTION_MODE.

    Safe fallback: unknown / unset / empty values resolve to dry_run.
    Typos MUST NOT silently escalate to live execution.
    """
    raw = (os.environ.get('BIYINGTONG_EXECUTION_MODE') or 'dry_run').strip().lower()
    if raw not in _VALID_MODES:
        print(f'[execution] WARNING: unknown BIYINGTONG_EXECUTION_MODE={raw!r}; '
              f'falling back to dry_run')
        return MockExecutionAdapter()
    if raw == 'live':
        return TDXExecutionAdapter()
    return MockExecutionAdapter()
