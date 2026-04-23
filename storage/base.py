"""Storage layer Protocols — consumers import these, not implementations.

Swapping the SQLite backend for Redis/Postgres/Parquet later means adding
new implementation classes (e.g. RedisKlineStore) and updating the factory
in storage/__init__.py. No consumer code changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, runtime_checkable


@dataclass
class ModelInfo:
    """LLM model metadata — no pricing (cost tracking out of scope)."""
    id: str
    provider: str
    display_name: str
    api_model_id: str
    training_cutoff: str
    supports_tool_use: bool
    max_tokens_out: int
    enabled: bool


@runtime_checkable
class KlineStore(Protocol):
    """K-line (OHLCV) persistence. Backed by vnpy_sqlite in MVP."""
    def save_bars(self, bars: list) -> int:
        """Persist a list of vnpy BarData objects. Returns count written."""
        ...

    def get_recent(self, code: str, period: str, count: int) -> list:
        """Most recent N bars for a stock at the given period ('1d'/'1w'/'1M')."""
        ...

    def load_range(self, code: str, period: str,
                   start: datetime, end: datetime) -> list:
        """All bars in [start, end]."""
        ...

    def get_closes(self, code: str, count: int) -> list[float]:
        """Convenience: last N close prices (daily). For indicators."""
        ...

    def distinct_dates(self, start: date, end: date) -> list[date]:
        """Unique dates with at least one bar. Used by CalendarStore fallback."""
        ...


@runtime_checkable
class FinancialStore(Protocol):
    """PE/PB/ROE/margins/growth cache."""
    def init_schema(self) -> None:
        """Create tables if they don't exist. Idempotent."""
        ...

    def upsert(self, rows: list[dict]) -> int:
        """UPSERT by (stock_code, date). Returns count of rows written."""
        ...

    def get_latest(self, code: str) -> dict | None:
        """Most recent row for a stock, or None if no data."""
        ...


@runtime_checkable
class ModelStore(Protocol):
    """LLM model registry."""
    def init_schema(self) -> None: ...
    def seed(self) -> None:
        """Insert default models. Idempotent."""
        ...
    def get(self, model_id: str) -> ModelInfo | None: ...
    def list_enabled(self) -> list[ModelInfo]: ...


@runtime_checkable
class CalendarStore(Protocol):
    """A-share trading calendar."""
    def get_trading_days(self, start: date, end: date) -> list[date]:
        """Ascending list of trading days in [start, end]."""
        ...


# --- Added in P2a ---

@dataclass
class Persona:
    """Reusable investment-philosophy definition. See Spec § 4.3 for the 5 built-ins."""
    id: str
    name: str
    style_desc: str
    system_prompt: str
    default_pool: list[str]
    pool_filter: dict | None
    default_schedule: str
    default_rules: dict
    allowed_tools: list[str]
    is_builtin: bool
    created_at: str | None = None


@dataclass
class Agent:
    """An agent instance = persona × model × rules_override.

    Multiple instances can share a persona, differing only by model_id or
    rules_override, enabling head-to-head comparison (Spec § 4.2).
    """
    id: str
    persona_id: str
    model_id: str
    display_name: str
    rules_override: dict
    initial_capital: float
    status: str
    subprocess_pid: int | None
    health_score: int
    trust_rating: str
    current_prompt_version_id: int | None
    created_at: str | None = None


@dataclass
class PromptVersion:
    """Immutable snapshot of an agent's system_prompt at a point in time."""
    id: int
    agent_id: str
    version_number: int
    system_prompt: str
    created_at: str | None
    note: str | None = None


@runtime_checkable
class PersonaStore(Protocol):
    """Reads/writes the personas table."""
    def init_schema(self) -> None: ...
    def upsert(self, persona: Persona) -> None:
        """Insert or replace by id. Idempotent."""
        ...
    def get(self, persona_id: str) -> Persona | None: ...
    def list_all(self) -> list[Persona]: ...


@runtime_checkable
class AgentStore(Protocol):
    """Reads/writes the agents table + coordinates initial prompt version creation."""
    def init_schema(self) -> None: ...
    def create_from_persona(
        self,
        persona_id: str,
        model_id: str,
        display_name: str,
        rules_override: dict | None = None,
        initial_capital: float = 1_000_000,
    ) -> Agent:
        """Atomically: insert new Agent row + PromptVersion v1 snapshotting
        the persona's current system_prompt. Returns the fresh Agent."""
        ...
    def get(self, agent_id: str) -> Agent | None: ...
    def list_all(self) -> list[Agent]: ...
    def update_status(self, agent_id: str, status: str) -> None: ...


@runtime_checkable
class PromptVersionStore(Protocol):
    """Reads/writes the prompt_versions table."""
    def init_schema(self) -> None: ...
    def insert(
        self, agent_id: str, system_prompt: str, note: str | None = None,
    ) -> PromptVersion:
        """Insert a new version; version_number = max(existing) + 1. Returns the row."""
        ...
    def get_latest(self, agent_id: str) -> PromptVersion | None: ...
    def list_for_agent(self, agent_id: str) -> list[PromptVersion]:
        """Ascending by version_number."""
        ...


# --- Added in P2b ---


@dataclass
class StockStatusRow:
    """Per-stock tradability flags refreshed daily from TDX snapshot."""
    code: str
    name: str | None
    is_st: bool
    is_suspended: bool
    is_delisted: bool
    listing_date: str | None = None
    updated_at: str | None = None


@runtime_checkable
class RedLineStore(Protocol):
    """Single-row global RedLine config."""
    def init_schema(self) -> None: ...
    def get(self) -> dict:
        """Return current RedLine. Must return DEFAULT_REDLINES if table empty."""
        ...
    def set(self, values: dict) -> None:
        """Atomically replace the single row. Records a 'redline_changed'
        audit entry is the engine's responsibility, not this store's."""
        ...


@runtime_checkable
class StockStatusStore(Protocol):
    """Per-stock tradability flags (ST / suspended / delisted)."""
    def init_schema(self) -> None: ...
    def upsert(self, row: StockStatusRow) -> None: ...
    def bulk_upsert(self, rows: list[StockStatusRow]) -> int:
        """Returns count written."""
        ...
    def get(self, code: str) -> StockStatusRow | None: ...
    def is_st(self, code: str) -> bool:
        """Missing row -> False (trade allowed until proven otherwise)."""
        ...
    def is_suspended(self, code: str) -> bool: ...


@runtime_checkable
class AuditStore(Protocol):
    """Append-only audit log; never truncated in MVP."""
    def init_schema(self) -> None: ...
    def log(self, entry) -> int:
        """Insert an AuditEntry. Returns the new row id."""
        ...
    def query_by_agent(self, agent_id: str, limit: int = 100) -> list[dict]:
        """Most recent first."""
        ...
    def query_by_kind(self, kind: str, limit: int = 100) -> list[dict]: ...


# --- Added in P2c ---


@runtime_checkable
class BacktestResultStore(Protocol):
    """backtest_sessions + backtest_results tables."""
    def init_schema(self) -> None: ...
    def insert(self, result) -> None:
        """Persist a BacktestResult. Idempotent by id."""
        ...
    def get(self, result_id: str):
        """Returns a BacktestResult or None."""
        ...
    def list_for_agent(self, agent_id: str, limit: int = 50) -> list:
        """Most recent first."""
        ...
    def list_for_session(self, session_id: str) -> list:
        """All results under one session, agent_id ASC."""
        ...
    def create_session(self, session_id: str, start_date: str,
                       end_date: str, agent_ids: list[str],
                       notes: str | None = None) -> None:
        """Idempotent by id."""
        ...


@runtime_checkable
class LLMDecisionCacheStore(Protocol):
    """Per-(agent, date, state) decision replay cache."""
    def init_schema(self) -> None: ...
    def has(self, cache_key: str) -> bool: ...
    def get(self, cache_key: str):
        """Returns CachedDecision or None."""
        ...
    def put(self, entry) -> None:
        """Upsert a CachedDecision."""
        ...


# --- Added in P2d ---


@runtime_checkable
class BaselineResultStore(Protocol):
    """baseline_results table."""
    def init_schema(self) -> None: ...
    def insert(self, result) -> None:
        """Persist a BaselineResult. Idempotent by id."""
        ...
    def get(self, result_id: str): ...
    def list_for_session(self, session_id: str) -> list: ...
