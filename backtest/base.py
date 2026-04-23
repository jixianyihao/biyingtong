"""Core dataclasses for the P2c backtest pipeline."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestStats:
    """Aggregate stats over a window — feeds quality_gate."""
    sharpe: float
    max_drawdown_pct: float      # negative (e.g. -12.0 means -12%)
    trade_count: int
    win_rate: float              # 0-100
    max_daily_loss_pct: float    # negative
    total_return_pct: float
    final_equity: float


@dataclass(frozen=True)
class ZoneStats:
    """Stats restricted to one cross-cutoff zone."""
    zone: str                    # 'pollution' | 'buffer' | 'clean'
    days: int
    stats: dict                  # serialized stats or {} if days < 2


@dataclass
class BacktestResult:
    """One agent's outcome over a backtest window."""
    id: str
    session_id: str
    agent_id: str
    persona_id: str | None
    model_id: str | None
    start_date: str
    end_date: str
    initial_capital: float
    stats: BacktestStats
    zone_stats: list             # list[ZoneStats]
    quality_gate_label: str      # 'pass' | 'warn' | 'fail'
    quality_gate_criteria: dict
    final_equity: float | None = None
    daily_records: list = None   # list[dict] — per-day equity/cash/pnl_pct
    trades: list = None          # list[dict] — per-fill {date,code,action,shares,price,fee}
    thinking: list = None        # list[dict] — per-day LLM reasoning + tool_calls + decisions
    kind: str = 'agent'          # 'agent' | 'rule' (P3-C)

    def __post_init__(self):
        if self.daily_records is None:
            self.daily_records = []
        if self.trades is None:
            self.trades = []
        if self.thinking is None:
            self.thinking = []


@dataclass
class CachedDecision:
    """Replay entry for one decision-day."""
    agent_id: str
    date: str
    portfolio_hash: str
    prompt_hash: str
    decisions: list              # list[dict] of (possibly modified) decisions

    @property
    def cache_key(self) -> str:
        return self.build_key(self.agent_id, self.date,
                              self.portfolio_hash, self.prompt_hash)

    @staticmethod
    def build_key(agent_id: str, date: str,
                  portfolio_hash: str, prompt_hash: str) -> str:
        return f'{agent_id}|{date}|{portfolio_hash}|{prompt_hash}'
