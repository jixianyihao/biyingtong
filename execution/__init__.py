"""Execution adapters — abstraction over order submission.

Default mode: dry_run (MockExecutionAdapter). Set BIYINGTONG_EXECUTION_MODE=live
to engage TDXExecutionAdapter. See plan 2026-04-24-p3f-phase2-execution.md.
"""
from .adapter import ExecutionAdapter, ExecutionResult

__all__ = ['ExecutionAdapter', 'ExecutionResult', 'get_adapter']


def get_adapter():
    """Factory — populated in Task 4."""
    raise NotImplementedError('populated in Task 4')
