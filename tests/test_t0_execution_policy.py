from __future__ import annotations

from t0.execution_policy import (
    T0Intent,
    T0PendingIntent,
    build_execution_policy,
)


def test_market_execution_runs_open_and_close_intents_immediately():
    policy = build_execution_policy('market')
    open_intent = T0Intent(kind='open', side='buy_first')
    close_intent = T0Intent(kind='close', side='buy_first', reason='take_profit')

    open_plan = policy.plan_open(open_intent, is_last_bar=False)
    close_plan = policy.plan_close(close_intent, is_last_bar=False)

    assert open_plan.execute == open_intent
    assert open_plan.pending is None
    assert close_plan.execute == close_intent
    assert close_plan.pending is None


def test_next_bar_execution_defers_open_until_following_bar_and_drops_last_bar_open():
    policy = build_execution_policy('next_bar')
    intent = T0Intent(kind='open', side='sell_first')

    plan = policy.plan_open(intent, is_last_bar=False)
    last_bar_plan = policy.plan_open(intent, is_last_bar=True)

    assert plan.execute is None
    assert plan.pending == T0PendingIntent(intent=intent)
    assert policy.execute_pending(plan.pending) == intent
    assert last_bar_plan.execute is None
    assert last_bar_plan.pending is None


def test_next_bar_execution_defers_close_but_forces_last_bar_close():
    policy = build_execution_policy('next_bar')
    intent = T0Intent(kind='close', side='sell_first', reason='take_profit')

    plan = policy.plan_close(intent, is_last_bar=False)
    last_bar_plan = policy.plan_close(intent, is_last_bar=True)

    assert plan.execute is None
    assert plan.pending == T0PendingIntent(intent=intent)
    assert policy.execute_pending(plan.pending) == intent
    assert last_bar_plan.execute == intent
    assert last_bar_plan.pending is None

