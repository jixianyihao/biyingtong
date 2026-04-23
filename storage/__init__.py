"""Storage factory — returns singletons of the configured backend."""
from __future__ import annotations

from .base import (
    Agent, AgentStore, AuditStore, BacktestResultStore, BaselineResultStore,
    CalendarStore, FinancialStore, KlineStore, LLMDecisionCacheStore,
    ModelInfo, ModelStore, Persona, PersonaStore, PromptVersion,
    PromptVersionStore, RedLineStore, StockStatusStore,
)

_kline: KlineStore | None = None
_financial: FinancialStore | None = None
_models: ModelStore | None = None
_calendar: CalendarStore | None = None
_personas: PersonaStore | None = None
_agents: AgentStore | None = None
_prompt_versions: PromptVersionStore | None = None
_redline: RedLineStore | None = None
_stock_status: StockStatusStore | None = None
_audit: AuditStore | None = None
_backtests: BacktestResultStore | None = None
_llm_cache: LLMDecisionCacheStore | None = None
_baselines: BaselineResultStore | None = None


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


def agents() -> AgentStore:
    global _agents
    if _agents is None:
        from .sqlite_agents import SQLiteAgentStore
        _agents = SQLiteAgentStore()
    return _agents


def prompt_versions() -> PromptVersionStore:
    global _prompt_versions
    if _prompt_versions is None:
        from .sqlite_prompt_versions import SQLitePromptVersionStore
        _prompt_versions = SQLitePromptVersionStore()
    return _prompt_versions


def redline() -> RedLineStore:
    global _redline
    if _redline is None:
        from .sqlite_redline import SQLiteRedLineStore
        _redline = SQLiteRedLineStore()
    return _redline


def stock_status() -> StockStatusStore:
    global _stock_status
    if _stock_status is None:
        from .sqlite_stock_status import SQLiteStockStatusStore
        _stock_status = SQLiteStockStatusStore()
    return _stock_status


def audit() -> AuditStore:
    global _audit
    if _audit is None:
        from .sqlite_audit import SQLiteAuditStore
        _audit = SQLiteAuditStore()
    return _audit


def backtests() -> BacktestResultStore:
    global _backtests
    if _backtests is None:
        from .sqlite_backtests import SQLiteBacktestResultStore
        _backtests = SQLiteBacktestResultStore()
    return _backtests


def llm_cache() -> LLMDecisionCacheStore:
    global _llm_cache
    if _llm_cache is None:
        from .sqlite_llm_cache import SQLiteLLMDecisionCache
        _llm_cache = SQLiteLLMDecisionCache()
    return _llm_cache


def baselines() -> BaselineResultStore:
    global _baselines
    if _baselines is None:
        from .sqlite_baselines import SQLiteBaselineResultStore
        _baselines = SQLiteBaselineResultStore()
    return _baselines


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


def set_agents(impl: AgentStore) -> None:
    global _agents
    _agents = impl


def set_prompt_versions(impl: PromptVersionStore) -> None:
    global _prompt_versions
    _prompt_versions = impl


def set_redline(impl: RedLineStore) -> None:
    global _redline
    _redline = impl


def set_stock_status(impl: StockStatusStore) -> None:
    global _stock_status
    _stock_status = impl


def set_audit(impl: AuditStore) -> None:
    global _audit
    _audit = impl


def set_backtests(impl: BacktestResultStore) -> None:
    global _backtests
    _backtests = impl


def set_llm_cache(impl: LLMDecisionCacheStore) -> None:
    global _llm_cache
    _llm_cache = impl


def set_baselines(impl: BaselineResultStore) -> None:
    global _baselines
    _baselines = impl


def reset() -> None:
    global _kline, _financial, _models, _calendar
    global _personas, _agents, _prompt_versions
    global _redline, _stock_status, _audit
    global _backtests, _llm_cache, _baselines
    _kline = None
    _financial = None
    _models = None
    _calendar = None
    _personas = None
    _agents = None
    _prompt_versions = None
    _redline = None
    _stock_status = None
    _audit = None
    _backtests = None
    _llm_cache = None
    _baselines = None
