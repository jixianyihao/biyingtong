"""Built-in rule strategies registry."""
from __future__ import annotations

from .base import Strategy, StrategyDescriptor
from .ma_crossover import MACrossover
from .rsi_breakout import RSIBreakout
from .macd_divergence import MACDDivergence


_REGISTRY: dict[str, tuple[type, StrategyDescriptor]] = {}


def register(cls, descriptor: StrategyDescriptor) -> None:
    _REGISTRY[descriptor.name] = (cls, descriptor)


def get(name: str):
    """Return (cls, descriptor) or None."""
    return _REGISTRY.get(name)


def list_all() -> list[StrategyDescriptor]:
    return [desc for _, desc in _REGISTRY.values()]


def build(name: str, params: dict | None = None):
    """Instantiate a strategy by name."""
    entry = _REGISTRY.get(name)
    if entry is None:
        raise ValueError(f'unknown strategy: {name!r}')
    cls, desc = entry
    return cls(params=params or dict(desc.default_params))


# Register built-ins
register(MACrossover, StrategyDescriptor(
    name='ma_crossover',
    display_name='均线金叉死叉',
    description='快速均线上穿慢速均线买入；下穿卖出。默认 10/30 日。',
    default_params={'fast': 10, 'slow': 30, 'position_pct': 0.3},
))

register(RSIBreakout, StrategyDescriptor(
    name='rsi_breakout',
    display_name='RSI 超买超卖',
    description='RSI ≤ 30 买入（超卖反弹），RSI ≥ 70 卖出（超买）',
    default_params={'period': 14, 'oversold': 30.0, 'overbought': 70.0,
                    'position_pct': 0.3},
))

register(MACDDivergence, StrategyDescriptor(
    name='macd_divergence',
    display_name='MACD 趋势',
    description='MACD 线高于零轴买入（强势），低于零轴卖出（弱势）',
    default_params={'fast': 12, 'slow': 26, 'signal': 9, 'position_pct': 0.3},
))
