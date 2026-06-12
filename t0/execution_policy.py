from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class T0Intent:
    kind: str
    side: str
    reason: str = ''


@dataclass(frozen=True)
class T0PendingIntent:
    intent: T0Intent


@dataclass(frozen=True)
class T0ExecutionPlan:
    execute: T0Intent | None = None
    pending: T0PendingIntent | None = None


class T0ExecutionPolicy:
    style = 'market'

    def plan_open(self, intent: T0Intent, *, is_last_bar: bool) -> T0ExecutionPlan:
        return T0ExecutionPlan(execute=intent)

    def plan_close(self, intent: T0Intent, *, is_last_bar: bool) -> T0ExecutionPlan:
        return T0ExecutionPlan(execute=intent)

    def execute_pending(self, pending: T0PendingIntent | None) -> T0Intent | None:
        return pending.intent if pending is not None else None


class NextBarExecutionPolicy(T0ExecutionPolicy):
    style = 'next_bar'

    def plan_open(self, intent: T0Intent, *, is_last_bar: bool) -> T0ExecutionPlan:
        if is_last_bar:
            return T0ExecutionPlan()
        return T0ExecutionPlan(pending=T0PendingIntent(intent=intent))

    def plan_close(self, intent: T0Intent, *, is_last_bar: bool) -> T0ExecutionPlan:
        if is_last_bar:
            return T0ExecutionPlan(execute=intent)
        return T0ExecutionPlan(pending=T0PendingIntent(intent=intent))


def build_execution_policy(style: str | None) -> T0ExecutionPolicy:
    normalized = (style or 'market').strip().lower()
    if normalized == 'next_bar':
        return NextBarExecutionPolicy()
    return T0ExecutionPolicy()

