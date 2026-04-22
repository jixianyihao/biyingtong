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
