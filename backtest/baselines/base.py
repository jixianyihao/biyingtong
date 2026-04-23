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
    daily_records: list = None   # list[dict] — {date, equity, pnl_pct, trade_count, won}

    def __post_init__(self):
        if self.daily_records is None:
            self.daily_records = []


def serialize_daily_records(records: list) -> list:
    """Turn internal {date: date, ...} records into JSON-safe {date: str, ...}.

    Shared by the 3 baseline runners; keeps the per-day shape in ONE place so
    any future key changes (e.g., adding 'cash') stay synchronized.
    """
    return [
        {'date': rec['date'].isoformat(),
         'equity': rec['equity'],
         'pnl_pct': rec['pnl_pct'],
         'trade_count': rec['trade_count'],
         'won': rec['won']}
        for rec in records
    ]
