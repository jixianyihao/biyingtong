"""RuleHandler Protocol + module-level registry.

Handlers declare a string RULE_ID and implement check(req) -> Violation | None.
Registration is side-effectful: each handler module calls register() on import.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .base import ValidationRequest, Violation


@runtime_checkable
class RuleHandler(Protocol):
    RULE_ID: str

    def check(self, req: ValidationRequest) -> Violation | None: ...


_registry: dict[str, RuleHandler] = {}


def register(handler: RuleHandler) -> None:
    rule_id = getattr(handler, 'RULE_ID', None)
    if not rule_id:
        raise TypeError(f'{type(handler).__name__} must declare RULE_ID')
    _registry[rule_id] = handler


def get(rule_id: str) -> RuleHandler | None:
    return _registry.get(rule_id)


def list_all() -> list[RuleHandler]:
    return list(_registry.values())


def reset() -> None:
    """Clear registry — for tests only."""
    _registry.clear()
