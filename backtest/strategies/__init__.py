"""Built-in rule strategies registry."""
from __future__ import annotations

from .base import Strategy, StrategyDescriptor
from .ma_crossover import MACrossover


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
