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
    def delete(self, persona_id: str) -> bool:
        """Delete by id. Caller must check dependent agents first — store
        does NOT enforce that constraint. Returns True if a row was removed."""
        ...


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
    def update_health(self, agent_id: str, health: int,
                      rating: str) -> None:
        """Persist health_score + trust_rating on the agent row."""
        ...

    def update(self, agent_id: str, *,
               display_name: str | None = None,
               rules_override: dict | None = None) -> None:
        """Partial update. None means don't change. Noop if agent missing."""
        ...

    def delete(self, agent_id: str) -> bool:
        """Hard delete the agent + its prompt_versions. Returns True if
        a row was removed. backtest_results for this agent are preserved
        (they reference agent_id by value, not FK)."""
        ...

    def set_current_prompt_version(self, agent_id: str, version_id: int) -> None:
        """Point agents.current_prompt_version_id at version_id. Noop if
        agent not found."""
        ...


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
    def get_by_id(self, version_id: int) -> PromptVersion | None:
        """Lookup by PK. Used when honoring agents.current_prompt_version_id."""
        ...
    def list_for_agent(self, agent_id: str) -> list[PromptVersion]:
        """Ascending by version_number."""
        ...

    def rollback(self, agent_id: str, version_id: int) -> 'PromptVersion':
        """Copy an older version's prompt to a NEW version at max+1.
        Returns the fresh PromptVersion. Does NOT mutate agents table —
        caller updates current_prompt_version_id."""
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
    def list_all(self, limit: int = 50) -> list:
        """All backtest results across all agents, most recent first."""
        ...
    def create_session(self, session_id: str, start_date: str,
                       end_date: str, agent_ids: list[str],
                       notes: str | None = None) -> None:
        """Idempotent by id."""
        ...

    def list_sessions(self, limit: int = 50) -> list:
        """Return recent sessions with aggregate counts.

        Each entry: {
          session_id, start_date, end_date, agent_ids (list),
          notes, created_at, agent_count, baseline_count
        }
        Most recent first.
        """
        ...

    def delete(self, result_id: str) -> bool:
        """Delete by id. Returns True if removed. Does NOT cascade to baselines
        or sessions — those are independent rows."""
        ...

    def purge_all(self) -> int:
        """Delete all backtest history rows and return total deleted rows."""
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


# --- Added in P3-F Phase 1 ---


@dataclass
class TradeProposal:
    """A trade proposal emitted by a deployed agent. Awaits user approval.

    Phase 1: approve/reject are DB-only.
    Phase 2: approve dispatches to an ExecutionAdapter; the 6 execution fields
    below record the outcome. They remain None until an approval has been
    processed, and stay None forever on rejected/expired proposals."""
    id: str
    agent_id: str
    decision_at: str          # ISO datetime when agent made the decision
    action: str               # 'buy' | 'sell' | 'hold'
    status: str               # 'pending' | 'approved' | 'rejected' | 'expired'
    code: str | None = None
    shares: int | None = None
    price: float | None = None
    reason: str | None = None
    thinking: str | None = None
    created_at: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None
    # Phase 2 execution fields — populated when approve dispatches to an
    # ExecutionAdapter. None on rejected/expired/pending proposals.
    execution_mode: str | None = None       # 'dry_run' | 'live'
    execution_order_id: str | None = None   # TDX order id or 'mock-...'
    execution_error: str | None = None      # human-readable error, None on success
    executed_at: str | None = None          # ISO timestamp of adapter dispatch
    filled_qty: int | None = None
    filled_price: float | None = None


@dataclass
class DeployedAgent:
    """An agent currently/previously running as a subprocess."""
    agent_id: str
    pid: int
    started_at: str
    status: str               # 'running' | 'stopped' | 'crashed'
    schedule: str


@runtime_checkable
class TradeProposalStore(Protocol):
    def init_schema(self) -> None: ...
    def insert(self, proposal: TradeProposal) -> None: ...
    def get(self, proposal_id: str) -> TradeProposal | None: ...
    def list_pending(self, agent_id: str | None = None,
                     limit: int = 100) -> list:
        """Pending proposals only. Optionally filter by agent."""
        ...
    def list_for_agent(self, agent_id: str, limit: int = 100) -> list: ...
    def update_status(self, proposal_id: str, status: str,
                      decided_by: str | None = None) -> bool:
        """Returns True if a row was updated. Sets decided_at to now."""
        ...
    def update_execution(self, proposal_id: str, *,
                         execution_mode: str,
                         execution_order_id: str | None,
                         execution_error: str | None,
                         filled_qty: int | None,
                         filled_price: float | None,
                         executed_at: str) -> bool:
        """Write Phase 2 execution result fields for a proposal.

        Returns True if a row matched. Intended to be called once per
        proposal immediately after adapter.place_order returns."""
        ...


@runtime_checkable
class DeployedAgentStore(Protocol):
    def init_schema(self) -> None: ...
    def upsert(self, agent_id: str, pid: int, schedule: str) -> None:
        """Insert or replace. Always sets status='running'."""
        ...
    def get(self, agent_id: str) -> DeployedAgent | None: ...
    def list_running(self) -> list:
        """Currently-running deployments only."""
        ...
    def mark_stopped(self, agent_id: str) -> None: ...
    def mark_crashed(self, agent_id: str) -> None: ...
