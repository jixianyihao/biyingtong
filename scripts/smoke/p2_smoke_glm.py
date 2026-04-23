"""P2 smoke test: end-to-end backtest with REAL LLM (GLM-5-turbo via 智谱 Anthropic-compatible API).

Iteration 2 of the smoke sequence. Same data path as ``p2_smoke_mock.py`` but
uses a real LLM backend. First run costs real API credits; subsequent runs
hit the LLM decision cache and are free.

Requires env vars:
    ANTHROPIC_AUTH_TOKEN  — GLM bearer token
    ANTHROPIC_BASE_URL    — https://open.bigmodel.cn/api/anthropic

Run:
    ANTHROPIC_AUTH_TOKEN=... ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic \
        python -m scripts.smoke.p2_smoke_glm
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date

from scripts.setup.vnpy_config import configure as _configure_vnpy
_configure_vnpy()


_GLM_MODEL_ID = 'glm-5-turbo'
# Rough guess — 智谱 doesn't publish an official cutoff. Tune later.
_GLM_TRAINING_CUTOFF = '2025-06-01'


def _require_env():
    token = os.environ.get('ANTHROPIC_AUTH_TOKEN')
    base_url = os.environ.get('ANTHROPIC_BASE_URL')
    if not token or not base_url:
        print('ERROR: set ANTHROPIC_AUTH_TOKEN and ANTHROPIC_BASE_URL env vars.',
              file=sys.stderr)
        sys.exit(2)
    return token, base_url


def _bring_up_stores() -> None:
    import storage
    storage.redline().init_schema()
    storage.stock_status().init_schema()
    storage.audit().init_schema()
    storage.llm_cache().init_schema()
    storage.personas().init_schema()
    storage.agents().init_schema()
    storage.prompt_versions().init_schema()
    storage.models().init_schema()
    storage.backtests().init_schema()
    storage.baselines().init_schema()
    storage.models().seed()


def _register_handlers() -> None:
    from validation import rules
    rules.reset()
    from validation.handlers.position_max_pct import Handler as H1
    from validation.handlers.ban_st import Handler as H2
    from validation.handlers.max_holdings import Handler as H3
    from validation.handlers.daily_loss_limit_pct import Handler as H4
    rules.register(H1())
    rules.register(H2())
    rules.register(H3())
    rules.register(H4())


def _register_glm_model() -> None:
    """Upsert glm-5-turbo into the models table so zone-tagging works."""
    import sqlite3
    from pathlib import Path
    db = Path(__file__).resolve().parents[2] / 'data' / 'agent_state.db'
    con = sqlite3.connect(db)
    try:
        con.execute(
            '''INSERT OR REPLACE INTO llm_models
               (id, provider, display_name, api_model_id, training_cutoff,
                supports_tool_use, max_tokens_out, enabled)
               VALUES (?,?,?,?,?,?,?,?)''',
            (_GLM_MODEL_ID, 'anthropic_compatible', 'GLM-5 Turbo (智谱)',
             _GLM_MODEL_ID, _GLM_TRAINING_CUTOFF, 1, 4096, 1),
        )
        con.commit()
    finally:
        con.close()


def _get_or_create_agent(persona_id: str, model_id: str, display_name: str):
    import storage
    for a in storage.agents().list_all():
        if a.persona_id == persona_id and a.model_id == model_id:
            return a
    return storage.agents().create_from_persona(
        persona_id=persona_id, model_id=model_id, display_name=display_name,
    )


def main():
    print('=' * 70)
    print('P2 smoke (real GLM + real kline data)')
    print('=' * 70)

    token, base_url = _require_env()
    _bring_up_stores()
    _register_handlers()
    _register_glm_model()

    from personas import seed as seed_personas
    seed_personas()

    import storage
    agent = _get_or_create_agent(
        'linyuan', _GLM_MODEL_ID, 'Smoke-GLM',
    )
    print(f'agent: {agent.id} ({agent.display_name})')

    # Start small — a single week, 3 stocks, to keep API spend tiny on first run
    start_date = '2025-11-17'
    end_date = '2025-11-21'
    universe = ['600519.SH', '601318.SH', '000858.SZ']
    initial_capital = 1_000_000.0
    session_id = f'smoke-glm-{int(time.time())}'

    days = storage.calendar().get_trading_days(
        date.fromisoformat(start_date), date.fromisoformat(end_date),
    )
    print(f'trading days in window: {len(days)}')

    from llm.claude import ClaudeLLM
    llm = ClaudeLLM(
        model_id=_GLM_MODEL_ID,
        auth_token=token,
        base_url=base_url,
        training_cutoff=_GLM_TRAINING_CUTOFF,
    )

    from backtest.runner import BacktestRunner
    print(f'\n--- running agent backtest (session={session_id}) ---')
    try:
        result = BacktestRunner(llm=llm).run(
            session_id=session_id, agent_id=agent.id,
            start_date=start_date, end_date=end_date,
            initial_capital=initial_capital, universe=universe,
        )
    except Exception as e:  # noqa: BLE001
        print(f'\nBACKTEST FAILED: {type(e).__name__}: {e}')
        print('\n--- partial audit trail (last 20) ---')
        rows = storage.audit().query_by_agent(agent.id, limit=20)
        for r in rows[:10]:
            print(f'  {r["kind"]}: {r.get("details", {}).get("outcome") or r.get("details")}')
        raise

    print(f'  id                    : {result.id}')
    print(f'  final_equity          : {result.final_equity:.2f}')
    print(f'  total_return_pct      : {result.stats.total_return_pct:.2f}')
    print(f'  trade_count           : {result.stats.trade_count}')
    print(f'  max_drawdown_pct      : {result.stats.max_drawdown_pct:.2f}')
    print(f'  sharpe                : {result.stats.sharpe:.2f}')
    print(f'  quality_gate_label    : {result.quality_gate_label}')
    print(f'  zone_stats            :')
    for z in result.zone_stats:
        print(f'    {z.zone}: {z.days} days')

    # Audit trail breakdown
    print(f'\n--- audit trail ---')
    audit_rows = storage.audit().query_by_agent(agent.id, limit=50)
    kinds: dict = {}
    for r in audit_rows:
        kinds[r['kind']] = kinds.get(r['kind'], 0) + 1
    for k, n in sorted(kinds.items()):
        print(f'  {k}: {n}')

    # Show latest 3 validation outcomes with the LLM's actual decisions
    print(f'\n--- latest 3 validations (what GLM actually decided) ---')
    val_rows = [r for r in audit_rows if r['kind'] == 'validation'][:3]
    for r in val_rows:
        d = r.get('details', {})
        dec = d.get('decision_in', {})
        print(f'  outcome={d.get("outcome")}  action={dec.get("action")}  '
              f'code={dec.get("code")}  qty={dec.get("qty") or dec.get("shares")}')
        reason = dec.get('reason', '')
        if reason:
            print(f'    reason: {reason[:100]}')

    # Rating
    from agents.rating import compute_health, classify_rating
    health = compute_health(agent.id)
    rating = classify_rating(health)
    storage.agents().update_health(agent.id, health=health, rating=rating)
    print(f'\nagent health={health} rating={rating}')

    print('=' * 70)
    print(f'SMOKE OK  session_id={session_id}')
    print('=' * 70)


if __name__ == '__main__':
    main()
