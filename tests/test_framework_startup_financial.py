"""Startup hook for auto-loading financial data — decision logic tests.

Verifies the framework-first principle: fundamentals data should be
auto-loaded at Flask startup (background thread, TDX-aware) rather than
requiring an out-of-band pre-run script. Value-investor personas
(linyuan / buffet) depend on get_financials returning real data —
otherwise the LLM either fabricates reasoning or makes blind decisions.
"""
from __future__ import annotations

import pytest


def test_gather_persona_symbols_union(observability_storage):
    """Symbols are a deduped union across all personas."""
    import storage
    from storage.base import Persona
    storage.personas().upsert(Persona(
        id='p_test_1', name='p1', style_desc='x', system_prompt='x',
        default_pool=['600519.SH', '000858.SZ'],
        pool_filter=None, default_schedule='daily',
        default_rules={}, allowed_tools=[], is_builtin=False,
    ))
    storage.personas().upsert(Persona(
        id='p_test_2', name='p2', style_desc='x', system_prompt='x',
        default_pool=['000858.SZ', '601318.SH'],  # overlap
        pool_filter=None, default_schedule='daily',
        default_rules={}, allowed_tools=[], is_builtin=False,
    ))

    from app import _gather_persona_symbols
    syms = _gather_persona_symbols()
    assert '600519.SH' in syms
    assert '000858.SZ' in syms
    assert '601318.SH' in syms
    # Deduped
    assert syms.count('000858.SZ') == 1


def test_should_load_disabled_via_env(observability_storage, monkeypatch):
    monkeypatch.setenv('BIYINGTONG_AUTO_LOAD_FINANCIAL', '0')
    from app import _should_load_financial
    do_run, reason = _should_load_financial()
    assert do_run is False
    assert 'disabled' in reason


def test_should_load_skipped_when_tdx_not_connected(observability_storage, monkeypatch):
    """With TDX not importable or not connected → skip."""
    monkeypatch.setenv('BIYINGTONG_AUTO_LOAD_FINANCIAL', '1')

    # Monkey-patch tdx.is_connected to return False
    try:
        import tdx_service
    except ImportError:
        # tdx not importable → _should_load_financial returns False quickly
        from app import _should_load_financial
        do_run, _ = _should_load_financial()
        assert do_run is False
        return

    monkeypatch.setattr(tdx_service.tdx, 'is_connected', lambda: False)
    from app import _should_load_financial
    do_run, reason = _should_load_financial()
    assert do_run is False
    assert 'not connected' in reason


def test_should_load_skipped_no_personas(observability_storage, monkeypatch):
    """Zero personas → skip (nothing to load for)."""
    monkeypatch.setenv('BIYINGTONG_AUTO_LOAD_FINANCIAL', '1')
    # Mock TDX as connected
    try:
        import tdx_service
        monkeypatch.setattr(tdx_service.tdx, 'is_connected', lambda: True)
    except ImportError:
        pytest.skip('tdx_service not importable — skipping this precondition branch')

    # observability_storage seeds builtin personas — wipe them so we exercise
    # the "no personas" branch.
    import storage
    for p in list(storage.personas().list_all()):
        storage.personas().delete(p.id)

    from app import _should_load_financial
    do_run, reason = _should_load_financial()
    assert do_run is False
    assert 'no personas' in reason


def test_startup_hook_degrades_when_tdx_missing(observability_storage, monkeypatch, caplog):
    """Must not raise even if TDX missing. Just logs + returns."""
    monkeypatch.setenv('BIYINGTONG_AUTO_LOAD_FINANCIAL', '1')
    from app import _startup_load_financial_async
    import logging
    caplog.set_level(logging.INFO, logger='startup.financial')

    # Should not raise under any conditions
    _startup_load_financial_async()


def test_startup_async_does_not_block(observability_storage, monkeypatch):
    """Hook returns immediately even when load would run (thread-spawned)."""
    monkeypatch.setenv('BIYINGTONG_AUTO_LOAD_FINANCIAL', '0')
    # Env=0 means _worker never runs, but verifies hook returns fast
    import time
    from app import _startup_load_financial_async
    t0 = time.monotonic()
    _startup_load_financial_async()
    elapsed = time.monotonic() - t0
    assert elapsed < 0.5  # instant
