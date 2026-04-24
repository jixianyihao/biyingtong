"""Strategy Protocol + Decision shape for rule-mode backtests."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass
class StrategyDescriptor:
    """Metadata for the /api/strategies listing."""
    name: str             # identifier, e.g. 'ma_crossover'
    display_name: str     # '均线金叉死叉'
    description: str
    default_params: dict = field(default_factory=dict)


@runtime_checkable
class Strategy(Protocol):
    """Per-day decision emitter for rule-mode backtests.

    close_history values are ascending [(date, close), ...] tuples including
    today's close. Strategy returns zero or more decisions; the Book + RuleRunner
    handle T+1, fees, lot-rounding, and mark-to-market.
    """
    name: str
    params: dict

    def on_day(self, date: date, close_history: dict, portfolio: dict) -> list[dict]:
        ...
