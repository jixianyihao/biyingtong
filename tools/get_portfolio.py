"""get_portfolio — current positions + cash.

P1 returns a static placeholder (zero-state). P2 will wire this to:
- Backtest: vnpy BacktestingEngine state
- Live: tdx_service.get_positions()
"""
from __future__ import annotations

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_portfolio',
    description='Get current portfolio state: cash + positions.',
    input_schema={'type': 'object', 'properties': {}},
)


def call(input: dict) -> dict:
    return {
        'cash': 0,
        'total_value': 0,
        'positions': [],
        '_note': 'P1 placeholder; P2 wires to vnpy / tdx_service state',
    }
