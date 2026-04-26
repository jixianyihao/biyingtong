"""GET /api/backtests — list + detail + per-session aggregated view."""
from __future__ import annotations

from dataclasses import asdict

from flask import jsonify, request

from . import api_bp


def _result_to_dict(r) -> dict:
    from backtest.divergence import compute_divergence
    flag, metric = compute_divergence(r.zone_stats)
    # Agent display_name lookup — keeps SessionsHistoryList readable
    # ("林园-Hunyuan" instead of "linyuan_3780f689"). None if agent has
    # been deleted; UI falls back to agent_id.
    display_name = None
    if r.agent_id:
        try:
            import storage
            ag = storage.agents().get(r.agent_id)
            display_name = ag.display_name if ag else None
        except Exception:  # noqa: BLE001
            display_name = None
    return {
        'id': r.id,
        'session_id': r.session_id,
        'agent_id': r.agent_id,
        'agent_display_name': display_name,
        'persona_id': r.persona_id,
        'model_id': r.model_id,
        'start_date': r.start_date,
        'end_date': r.end_date,
        'initial_capital': r.initial_capital,
        'final_equity': r.final_equity,
        'stats': asdict(r.stats),
        'zone_stats': [asdict(z) for z in r.zone_stats],
        'quality_gate_label': r.quality_gate_label,
        'quality_gate_criteria': r.quality_gate_criteria,
        'divergence_flag': flag,
        'divergence_metric': metric,
        'universe': list(getattr(r, 'universe', None) or []),
        'kind': getattr(r, 'kind', 'agent'),
    }


@api_bp.route('/backtests')
def list_backtests():
    """List backtests. Without agent_id -> global most-recent list."""
    import storage
    agent_id = request.args.get('agent_id')
    limit = int(request.args.get('limit', '50'))
    if agent_id:
        rows = storage.backtests().list_for_agent(agent_id, limit=limit)
    else:
        rows = storage.backtests().list_all(limit=limit)
    return jsonify([_result_to_dict(r) for r in rows])


@api_bp.route('/backtests/sessions')
def list_backtest_sessions():
    """Distinct sessions ordered by most recent, with aggregate info.

    Returns:
      [
        {
          session_id: str,
          start_date: str, end_date: str,
          agent_ids: list[str],
          agent_count: int,
          baseline_count: int,
          created_at: str,
          notes: str | null,
        },
        ...
      ]
    """
    limit = int(request.args.get('limit', '50'))
    import storage
    return jsonify(storage.backtests().list_sessions(limit))


@api_bp.route('/backtests/<result_id>')
def get_backtest(result_id):
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify(_result_to_dict(r))


@api_bp.route('/backtests/session/<session_id>')
def get_session(session_id):
    """Composite view: all agent backtests + baselines under one session."""
    import storage
    from backtest.baselines.base import BaselineResult  # noqa: F401

    agent_results = storage.backtests().list_for_session(session_id)
    baseline_results = storage.baselines().list_for_session(session_id)

    def _baseline_to_dict(b) -> dict:
        return {
            'id': b.id,
            'session_id': b.session_id,
            'name': b.name,
            'start_date': b.start_date,
            'end_date': b.end_date,
            'initial_capital': b.initial_capital,
            'final_equity': b.final_equity,
            'stats': asdict(b.stats),
        }

    return jsonify({
        'session_id': session_id,
        'agents': [_result_to_dict(r) for r in agent_results],
        'baselines': [_baseline_to_dict(b) for b in baseline_results],
    })


@api_bp.route('/backtests', methods=['POST'])
def start_backtest():
    """Kick off an async backtest.

    Body: {
      agent_ids: [str, ...],
      start_date: 'YYYY-MM-DD',
      end_date: 'YYYY-MM-DD',
      initial_capital: float,
      universe: [str, ...],
      include_baselines: bool (default True),
      session_id: str (optional — generated if absent),
      engine: 'legacy' | 'vnpy' (default 'legacy')
    }

    Returns 202 + {session_id, state}.
    """
    import uuid
    body = request.get_json(silent=True) or {}
    agent_ids = body.get('agent_ids')
    start_date = body.get('start_date')
    end_date = body.get('end_date')
    initial_capital = body.get('initial_capital')
    universe = body.get('universe')
    if not (isinstance(agent_ids, list) and agent_ids
            and start_date and end_date
            and isinstance(universe, list) and universe
            and initial_capital is not None):
        return jsonify({'error': 'agent_ids, start_date, end_date, '
                                 'initial_capital, universe required'}), 400

    engine = body.get('engine', 'legacy')
    if engine not in ('legacy', 'vnpy'):
        return jsonify({'error': f'unknown engine: {engine}'}), 400

    # Sanity: agents must exist
    import storage
    for aid in agent_ids:
        if storage.agents().get(aid) is None:
            return jsonify({'error': f'unknown agent_id: {aid}'}), 404

    session_id = body.get('session_id') or f'session-{uuid.uuid4().hex[:12]}'
    include_baselines = bool(body.get('include_baselines', True))

    from backtest.jobs import submit_backtest
    status = submit_backtest(
        session_id=session_id, agent_ids=agent_ids,
        start_date=start_date, end_date=end_date,
        initial_capital=float(initial_capital), universe=universe,
        include_baselines=include_baselines,
        engine=engine,
    )
    return jsonify({
        'session_id': session_id,
        'state': status.state,
    }), 202


@api_bp.route('/backtests/<result_id>/monthly_returns')
def get_backtest_monthly_returns(result_id):
    """Returns {result_id, monthly_returns: [{year, month, return_pct, days}]}."""
    import storage
    from backtest.stats import compute_monthly_returns
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'result_id': result_id,
        'monthly_returns': compute_monthly_returns(r.daily_records or []),
    })


@api_bp.route('/backtests/<result_id>', methods=['DELETE'])
def delete_backtest(result_id):
    import storage
    if storage.backtests().get(result_id) is None:
        return jsonify({'error': 'not_found'}), 404
    storage.backtests().delete(result_id)
    return '', 204


@api_bp.route('/backtests/<result_id>/nav')
def get_backtest_nav(result_id):
    """Daily equity curve for one backtest + same-session baselines.

    Response: {
      'result_id': str,
      'agent': [{date, equity, cash, pnl_pct}, ...],
      'baselines': [{name, curve: [{date, equity}, ...]}, ...]
    }

    Baselines don't persist per-day equity yet (P3-A Task 6 / future).
    Return empty curves for now; frontend tolerates.
    """
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    agent_curve = [
        {'date': rec.get('date'),
         'equity': rec.get('equity'),
         'cash': rec.get('cash'),
         'pnl_pct': rec.get('pnl_pct')}
        for rec in (r.daily_records or [])
    ]
    baselines_payload = []
    for b in storage.baselines().list_for_session(r.session_id):
        b_records = getattr(b, 'daily_records', None) or []
        b_curve = [{'date': rec.get('date'), 'equity': rec.get('equity')}
                   for rec in b_records]
        baselines_payload.append({'name': b.name, 'curve': b_curve})
    return jsonify({
        'result_id': result_id,
        'agent': agent_curve,
        'baselines': baselines_payload,
    })


@api_bp.route('/backtests/<result_id>/trades')
def get_backtest_trades(result_id):
    """Ordered list of fills for a backtest.

    Response: {result_id, trades: [{date, code, action, shares, price, fee}, ...]}
    """
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'result_id': result_id,
        'trades': list(r.trades or []),
    })


@api_bp.route('/backtests/<result_id>/thinking')
def get_backtest_thinking(result_id):
    """Per-day LLM reasoning + tool_calls + decisions for a backtest.

    Response: {result_id, thinking: [{date, reasoning, tool_calls, decisions}, ...]}
    """
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'result_id': result_id,
        'thinking': list(r.thinking or []),
    })


@api_bp.route('/backtests/<result_id>/ledger')
def get_backtest_ledger(result_id):
    """Joined per-decision audit trail: thinking → validation → fill.

    Returns a flat list ordered by date ascending. Each entry covers ONE
    LLM decision (one place_decision call) with its complete lineage.

    Response: {
      result_id, ledger: [{
        date,                       # 'YYYY-MM-DD'
        action,                     # 'buy'/'sell'/'hold'
        code,                       # may be null for 'hold'
        requested_shares,           # what LLM asked for
        requested_price,            # at decision time
        outcome,                    # 'ok' | 'modified' | 'rejected' | 'cached' | 'hold'
        rejection_reasons,          # list[str], empty unless rejected
        executed_shares,            # what actually filled, 0 if rejected/hold
        executed_price,             # actual fill price
        executed_fee,               # commission
        reasoning,                  # short reason from the LLM
        tool_calls_count,           # how many tools the LLM used that day
      }, ...]
    }
    """
    import storage
    r = storage.backtests().get(result_id)
    if r is None:
        return jsonify({'error': 'not_found'}), 404

    # Index unconsumed trades by (code, action) → list of fills sorted by
    # date. The legacy runner records a decision on day D but the fill on
    # D+1 (next-bar) so a strict (date, code, action) join would miss every
    # trade. We instead match each decision to its earliest fill on
    # decision_date or after; once consumed, the fill won't match a later
    # decision. Same-day-close runs still work — first fill is on the same
    # date.
    from collections import defaultdict
    trades_by_action: dict[tuple, list[dict]] = defaultdict(list)
    for t in (r.trades or []):
        code_t = t.get('code')
        action_t = t.get('action')
        if code_t and action_t:
            trades_by_action[(code_t, action_t)].append(t)
    for v in trades_by_action.values():
        v.sort(key=lambda t: t.get('date') or '')
    # Track first-unconsumed index per (code, action) so we don't match the
    # same fill to two decisions.
    consumed_idx: dict[tuple, int] = defaultdict(int)

    def _take_fill(decision_date: str, code: str, action: str) -> dict | None:
        if not (code and action and decision_date):
            return None
        key = (code, action)
        i = consumed_idx[key]
        fills = trades_by_action.get(key) or []
        # Skip fills strictly before decision_date (shouldn't normally happen
        # with sorted fills, but be defensive).
        while i < len(fills) and (fills[i].get('date') or '') < decision_date:
            i += 1
        if i >= len(fills):
            consumed_idx[key] = i
            return None
        consumed_idx[key] = i + 1
        return fills[i]

    out: list[dict] = []
    for day in (r.thinking or []):
        date = day.get('date')
        tc_count = len(day.get('tool_calls') or [])
        decisions = day.get('decisions') or []
        if not decisions:
            # Day with no place_decision call — represent as a "hold" row so
            # the analyst can see the LLM ran but produced no actionable
            # output (often: only screening tool_calls).
            out.append({
                'date': date, 'action': 'hold', 'code': None,
                'requested_shares': None, 'requested_price': None,
                'outcome': 'hold', 'rejection_reasons': [],
                'executed_shares': 0, 'executed_price': None, 'executed_fee': None,
                'reasoning': day.get('reasoning') or '',
                'tool_calls_count': tc_count,
            })
            continue
        for dec in decisions:
            action = dec.get('action')
            code = dec.get('code')
            req_shares_raw = dec.get('shares')
            requested_shares = (
                int(req_shares_raw) if req_shares_raw not in (None, '') else None
            )
            req_price = dec.get('price')
            outcome = dec.get('outcome') or 'ok'
            reasoning = dec.get('reasoning') or ''
            # Match fill (only buy/sell — 'hold' decisions never produce fills).
            # Uses next-available-fill-on-or-after logic to handle the legacy
            # runner's D-decision / D+1-fill convention.
            t = _take_fill(date, code, action) if code and action != 'hold' else None
            executed_shares = int(t['shares']) if t else 0
            executed_price = t.get('price') if t else None
            executed_fee = t.get('fee') if t else None
            # Rejection reasons — for v1 we have outcome but not the violation
            # strings in the thinking record; leave a placeholder. Future
            # extension can join the audit log for full reasons.
            rejection_reasons = (
                [] if outcome != 'rejected' else ['rejected by validation']
            )
            out.append({
                'date': date, 'action': action, 'code': code,
                'requested_shares': requested_shares,
                'requested_price': req_price,
                'outcome': outcome, 'rejection_reasons': rejection_reasons,
                'executed_shares': executed_shares,
                'executed_price': executed_price,
                'executed_fee': executed_fee,
                'reasoning': reasoning, 'tool_calls_count': tc_count,
            })
    return jsonify({'result_id': result_id, 'ledger': out})


@api_bp.route('/backtests/rule', methods=['POST'])
def start_rule_backtest():
    """Synchronous rule-strategy backtest. Can join an existing session."""
    import uuid
    body = request.get_json(silent=True) or {}
    strategy_name = body.get('strategy_name')
    params = body.get('params') or {}
    start_date = body.get('start_date')
    end_date = body.get('end_date')
    universe = body.get('universe')
    initial_capital = body.get('initial_capital')
    if not (strategy_name and start_date and end_date
            and isinstance(universe, list) and universe
            and initial_capital is not None):
        return jsonify({'error': 'strategy_name, start_date, end_date, '
                                  'universe, initial_capital required'}), 400

    from backtest.strategies import get as get_strategy, build
    if get_strategy(strategy_name) is None:
        return jsonify({'error': f'unknown strategy: {strategy_name!r}'}), 400

    try:
        strategy = build(strategy_name, params=params)
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': f'strategy build failed: {e}'}), 400

    session_id = body.get('session_id') or f'session-{uuid.uuid4().hex[:12]}'

    from backtest.rule_runner import RuleRunner
    try:
        result = RuleRunner(strategy=strategy).run(
            session_id=session_id,
            start_date=start_date, end_date=end_date,
            initial_capital=float(initial_capital),
            universe=universe,
        )
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': f'run failed: {e}'}), 500

    return jsonify({
        'session_id': session_id,
        'result_id': result.id,
        'state': 'complete',
    }), 202
