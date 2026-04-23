"""Head-to-head multi-agent GLM smoke test — 3 personas in parallel.

Validates:
- Multi-agent parallel execution (3 threads)
- Shared snapshot pre-loading (eliminates tool-loop roundtrips)
- Baseline parallel (3 threads)

Cache expected: since we wipe before running, first pass is N×M API calls.
Rerun with WIPE_CACHE=0 is ~seconds.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date

from scripts.setup.vnpy_config import configure as _configure_vnpy
_configure_vnpy()


_GLM_MODEL_ID = 'glm-5-turbo'
_GLM_TRAINING_CUTOFF = '2025-06-01'


def _require_env():
    token = os.environ.get('ANTHROPIC_AUTH_TOKEN')
    base_url = os.environ.get('ANTHROPIC_BASE_URL')
    if not (token and base_url):
        print('ERROR: set ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL',
              file=sys.stderr)
        sys.exit(2)
    return token, base_url


def _bring_up_stores():
    import storage
    for name in ('redline', 'stock_status', 'audit', 'llm_cache',
                 'personas', 'agents', 'prompt_versions', 'models',
                 'backtests', 'baselines'):
        getattr(storage, name)().init_schema()
    storage.models().seed()


def _register_handlers():
    from validation import rules
    rules.reset()
    from validation.handlers.position_max_pct import Handler as H1
    from validation.handlers.ban_st import Handler as H2
    from validation.handlers.max_holdings import Handler as H3
    from validation.handlers.daily_loss_limit_pct import Handler as H4
    for h in (H1(), H2(), H3(), H4()):
        rules.register(h)


def _register_glm_model():
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


def _get_or_create(persona_id, display):
    import storage
    for a in storage.agents().list_all():
        if a.persona_id == persona_id and a.model_id == _GLM_MODEL_ID:
            return a
    return storage.agents().create_from_persona(
        persona_id=persona_id, model_id=_GLM_MODEL_ID,
        display_name=display,
    )


def main():
    print('=' * 70)
    print('P2 smoke — multi-agent head-to-head')
    print('=' * 70)

    token, base_url = _require_env()
    _bring_up_stores()
    _register_handlers()
    _register_glm_model()
    from personas import seed as seed_personas
    seed_personas()

    import storage
    agents = []
    for persona in ('linyuan', 'buffet', 'fuyou'):
        a = _get_or_create(persona, f'HeadToHead-{persona}')
        agents.append(a)

    if os.environ.get('WIPE_CACHE', '1') != '0':
        import sqlite3
        from pathlib import Path
        db = Path(__file__).resolve().parents[2] / 'data' / 'agent_state.db'
        con = sqlite3.connect(db)
        try:
            for a in agents:
                con.execute('DELETE FROM llm_decision_cache WHERE agent_id=?',
                            (a.id,))
            con.commit()
        finally:
            con.close()
        print('wiped stale cache')

    start_date = '2025-11-17'
    end_date = '2025-11-28'
    universe = ['600519.SH', '601318.SH', '000858.SZ']
    initial_capital = 1_000_000.0
    session_id = f'smoke-multi-{int(time.time())}'

    days = storage.calendar().get_trading_days(
        date.fromisoformat(start_date), date.fromisoformat(end_date),
    )
    print(f'trading days: {len(days)}  window: {start_date}..{end_date}')

    from llm.claude import ClaudeLLM
    configs = [{
        'agent_id': a.id,
        'llm': ClaudeLLM(model_id=_GLM_MODEL_ID, auth_token=token,
                         base_url=base_url,
                         training_cutoff=_GLM_TRAINING_CUTOFF),
    } for a in agents]

    print(f'\n--- running 3 agents in parallel (session={session_id}) ---')
    from backtest.multi_agent_runner import run_multi
    t0 = time.time()
    results = run_multi(
        session_id=session_id, agent_configs=configs,
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital, universe=universe,
    )
    t_agents = time.time() - t0

    by_agent = {r.agent_id: r for r in results}
    for a in agents:
        r = by_agent[a.id]
        print(f'  {a.display_name:24s}  final={r.final_equity:>12,.2f}'
              f'  return={r.stats.total_return_pct:+6.2f}%'
              f'  trades={r.stats.trade_count:>3d}'
              f'  label={r.quality_gate_label}')
    print(f'  agents wall time: {t_agents:.2f}s')

    print(f'\n--- running 3 baselines in parallel ---')
    from backtest.baselines.runner import run_all
    t1 = time.time()
    baselines = run_all(
        session_id=session_id,
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital, universe=universe,
    )
    t_baselines = time.time() - t1
    for b in sorted(baselines, key=lambda x: x.name):
        print(f'  {b.name:20s}  final={b.final_equity:>12,.2f}'
              f'  return={b.stats.total_return_pct:+6.2f}%')
    print(f'  baselines wall time: {t_baselines:.2f}s')

    print(f'\n--- TOTAL wall time: {t_agents + t_baselines:.2f}s ---')
    print('=' * 70)
    print(f'SMOKE OK  session_id={session_id}')
    print('=' * 70)


if __name__ == '__main__':
    main()
