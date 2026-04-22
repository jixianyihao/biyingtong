"""Storage factory — returns singletons of the configured backend.

Usage:
    from storage import kline, financial, models, calendar
    bars = kline().get_recent('600519.SH', '1d', 30)

For tests, call storage.reset() in a fixture, then set_kline(FakeKlineStore())
to inject a mock.
"""
from __future__ import annotations

from .base import (
    Agent, AgentStore, CalendarStore, FinancialStore,
    KlineStore, ModelInfo, ModelStore, Persona, PersonaStore,
    PromptVersion, PromptVersionStore,
)

_kline: KlineStore | None = None
_financial: FinancialStore | None = None
_models: ModelStore | None = None
_calendar: CalendarStore | None = None
_personas: PersonaStore | None = None


def kline() -> KlineStore:
    global _kline
    if _kline is None:
        from .sqlite_kline import SQLiteKlineStore
        _kline = SQLiteKlineStore()
    return _kline


def financial() -> FinancialStore:
    global _financial
    if _financial is None:
        from .sqlite_financial import SQLiteFinancialStore
        _financial = SQLiteFinancialStore()
    return _financial


def models() -> ModelStore:
    global _models
    if _models is None:
        from .sqlite_models import SQLiteModelStore
        _models = SQLiteModelStore()
    return _models


def calendar() -> CalendarStore:
    global _calendar
    if _calendar is None:
        from .sqlite_calendar import SQLiteCalendarStore
        _calendar = SQLiteCalendarStore()
    return _calendar


def personas() -> PersonaStore:
    global _personas
    if _personas is None:
        from .sqlite_personas import SQLitePersonaStore
        _personas = SQLitePersonaStore()
    return _personas


def set_kline(impl: KlineStore) -> None:
    global _kline
    _kline = impl


def set_financial(impl: FinancialStore) -> None:
    global _financial
    _financial = impl


def set_models(impl: ModelStore) -> None:
    global _models
    _models = impl


def set_calendar(impl: CalendarStore) -> None:
    global _calendar
    _calendar = impl


def set_personas(impl: PersonaStore) -> None:
    global _personas
    _personas = impl


def reset() -> None:
    """Clear all singletons. Call this at the start of tests that mutate storage."""
    global _kline, _financial, _models, _calendar, _personas
    _kline = None
    _financial = None
    _models = None
    _calendar = None
    _personas = None
