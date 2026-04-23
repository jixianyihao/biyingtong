"""P2 smoke test: end-to-end backtest on REAL kline data with MockLLM.

Iteration 1 of the smoke sequence — validates that the data path (kline →
BacktestRunner → Book → stats → BacktestResult persistence) works on genuine
loaded bars, not just on mock bars from unit tests.

MockLLM is deterministic: scripted to BUY 600519 on day 1, then HOLD.
Skips the CSI 300 baseline (000300 not yet loaded); other two baselines run.

Run:
    python -m scripts.smoke.p2_smoke_mock

Expected output: a BacktestResult row + 2 baseline rows under session
``smoke-p2-mock-<timestamp>``, plus a printed summary.
"""
from __future__ import annotations

import time
from datetime import date, datetime

# Configure vnpy first (binds sqlite to data/vnpy_data.db)
from scripts.setup.vnpy_config import configure as _configure_vnpy
_configure_vnpy()


def _bring_up_stores() -> None:
    """Wire every store to its default SQLite-backed singleton + ensure schemas."""
    import storage
    # Touching each factory materializes the singleton against data/agent_state.db
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
    # kline() + calendar() have no own schema (delegate to vnpy_sqlite)
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


def _ensure_personas() -> None:
    from personas import seed as seed_personas
    seed_personas()


def _get_or_create_agent(persona_id: str, model_id: str, display_name: str):
    import storage
    for a in storage.agents().list_all():
        if a.persona_id == persona_id and a.model_id == model_id:
            return a
    return storage.agents().create_from_persona(
        persona_id=persona_id, model_id=model_id, display_name=display_name,
    )


def _scripted_mock_llm(n_days: int, buy_on_day: int = 0):
    """Script: BUY 600519 on day buy_on_day (default: day 0), HOLD otherwise."""
    from llm.mock import MockLLM
    script = []
    for i in range(n_days):
        if i == buy_on_day:
            script.append({
                'tool_calls': [{
                    'id': f'c{i}', 'name': 'place_decision',
                    'input': {
                        'action': 'buy', 'code': '600519.SH', 'qty': 100,
                        'reason': 'entering a core long-term quality position in kweichow moutai',
                        'thinking': 'classic value anchor; trim later if overextended',
                    },
                }],
                'stop_reason': 'tool_use',
            })
        else:
            script.append({
                'tool_calls': [{
                    'id': f'c{i}', 'name': 'place_decision',
                    'input': {
                        'action': 'hold',
                        'reason': 'staying with the thesis, no new signal today to act on',
                        'thinking': 'market drift within expected range',
                    },
                }],
                'stop_reason': 'tool_use',
            })
    return MockLLM(script)


def main():
    print('=' * 70)
    print('P2 smoke (mock LLM + real kline data)')
    print('=' * 70)

    _bring_up_stores()
    _register_handlers()
    _ensure_personas()

    import storage
    agent = _get_or_create_agent('linyuan', 'claude-opus-4-7', 'Smoke-Mock')
    print(f'agent: {agent.id} ({agent.display_name})')

    # Window: 2 weeks within loaded range (2025-04-01..2026-04-01)
    start_date = '2025-11-17'
    end_date = '2025-11-28'
    universe = ['600519.SH', '601318.SH', '000858.SZ']
    initial_capital = 1_000_000.0
    session_id = f'smoke-mock-{int(time.time())}'

    # How many trading days? Peek via calendar fallback (kline.distinct_dates).
    days = storage.calendar().get_trading_days(
        date.fromisoformat(start_date), date.fromisoformat(end_date),
    )
    print(f'trading days in window: {len(days)} ({days[0]} .. {days[-1]})')

    # --- Agent backtest -----------------------------------------------------
    from backtest.runner import BacktestRunner
    llm = _scripted_mock_llm(n_days=len(days) + 4, buy_on_day=0)
    print(f'\n--- running agent backtest (session={session_id}) ---')
    result = BacktestRunner(llm=llm).run(
        session_id=session_id, agent_id=agent.id,
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital, universe=universe,
    )
    print(f'  id                    : {result.id}')
    print(f'  final_equity          : {result.final_equity:.2f}')
    print(f'  total_return_pct      : {result.stats.total_return_pct:.2f}')
    print(f'  trade_count           : {result.stats.trade_count}')
    print(f'  max_drawdown_pct      : {result.stats.max_drawdown_pct:.2f}')
    print(f'  sharpe                : {result.stats.sharpe:.2f}')
    print(f'  quality_gate_label    : {result.quality_gate_label}')
    print(f'  zone_stats            :')
    for z in result.zone_stats:
        print(f'    {z.zone}: {z.days} days'
              + (f' return={z.stats.get("total_return_pct", 0):.2f}%'
                 if z.stats else ''))

    # --- Baselines (skipping CSI 300; 000300 not loaded) -------------------
    print(f'\n--- running baselines (no CSI 300 for now) ---')
    from backtest.baselines.buy_and_hold import run_buy_and_hold
    from backtest.baselines.equal_weight import run_equal_weight
    bh = run_buy_and_hold(
        session_id=session_id,
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital, universe=universe,
    )
    ew = run_equal_weight(
        session_id=session_id,
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital, universe=universe,
    )
    for b in (bh, ew):
        print(f'  {b.name:20s}  final={b.final_equity:.2f}'
              f'  return={b.stats.total_return_pct:+.2f}%'
              f'  trades={b.stats.trade_count}')

    # --- Audit sanity ------------------------------------------------------
    print(f'\n--- audit trail ---')
    audit_rows = storage.audit().query_by_agent(agent.id, limit=50)
    kinds: dict = {}
    for r in audit_rows:
        kinds[r['kind']] = kinds.get(r['kind'], 0) + 1
    for k, n in sorted(kinds.items()):
        print(f'  {k}: {n}')

    # Validation outcome distribution for this session's validations
    outcomes: dict = {}
    for r in audit_rows:
        if r['kind'] == 'validation':
            o = r.get('details', {}).get('outcome', 'unknown')
            outcomes[o] = outcomes.get(o, 0) + 1
    print(f'  (validation outcomes: {outcomes})')

    # --- Rating ------------------------------------------------------------
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
