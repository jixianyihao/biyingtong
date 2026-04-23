"""BaselineResult dataclass + shared signatures."""
from __future__ import annotations

from dataclasses import dataclass

from backtest.base import BacktestStats


@dataclass
class BaselineResult:
    id: str
    session_id: str
    name: str                    # 'buy_and_hold' | 'equal_weight' | 'csi300'
    start_date: str
    end_date: str
    initial_capital: float
    stats: BacktestStats
    final_equity: float | None = None
