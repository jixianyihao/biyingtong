from __future__ import annotations

from datetime import date, datetime

from flask import jsonify, request

from t0.scorer import score_minute_bars, score_snapshot
from t0.allocator import choose_t0_allocation
from t0.grid import run_grid_search
from t0.local_lc1 import load_lc1_bars_for_code, scan_lc1_candidates
from t0.portfolio import run_t0_portfolio_backtest
from t0.strategy_selector import choose_best_t0_result, t0_strategy_variants
from tdx_service import tdx

from . import api_bp


def _float_arg(name: str, default: float):
    raw = request.args.get(name)
    if raw is None or raw == '':
        return default, None
    try:
        return float(raw), None
    except ValueError:
        return default, f'{name} must be numeric'


def _bar_day(bar: dict) -> date | None:
    raw = str(bar.get('date') or '').strip()
    if not raw:
        return None
    token = raw[:10]
    try:
        return datetime.strptime(token, '%Y-%m-%d').date()
    except ValueError:
        return None


def _latest_bar_day(bars: list[dict]) -> date | None:
    days = [_bar_day(b) for b in bars]
    days = [d for d in days if d is not None]
    return max(days) if days else None


def _coverage(bars: list[dict]) -> tuple[date | None, date | None]:
    days = [_bar_day(b) for b in bars]
    days = [d for d in days if d is not None]
    if not days:
        return None, None
    return min(days), max(days)


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    return datetime.strptime(raw, '%Y-%m-%d').date()


def _as_of_date() -> date:
    raw = (request.args.get('as_of') or '').strip()
    if raw:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    return date.today()


def _body_float(body: dict, name: str, default: float) -> float:
    try:
        return float(body.get(name, default))
    except (TypeError, ValueError):
        return default


def _body_int(body: dict, name: str, default: int) -> int:
    try:
        return int(body.get(name, default))
    except (TypeError, ValueError):
        return default


def _body_bool(body: dict, name: str, default: bool) -> bool:
    raw = body.get(name)
    if raw is None or raw == '':
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {'1', 'true', 'yes', 'y', 'on'}
    return bool(raw)


def _has_body_value(body: dict, name: str) -> bool:
    return name in body and body.get(name) not in (None, '')


def _preview_sort_key(
    row: dict,
) -> tuple[float, float, float, float, float, float, float, float, float, int]:
    """Rank candidates by out-of-sample outcome when available.

    If walk-forward preview fields are present, validation cost-reduction is
    the primary objective. Otherwise use full-period cost-reduction. Returns
    and alpha remain tie-breakers instead of the main goal.
    """
    primary_cost_reduction = row.get(
        'preview_validation_cost_reduction_pct',
        row.get('preview_cost_reduction_pct'),
    )
    primary_return = row.get(
        'preview_validation_total_return_pct',
        row.get('preview_total_return_pct'),
    )
    primary_alpha = row.get(
        'preview_validation_alpha_vs_all_in',
        row.get('preview_alpha_vs_all_in'),
    )
    primary_min_cost_reduction = row.get(
        'preview_validation_min_cost_reduction_pct',
        row.get('preview_min_cost_reduction_pct'),
    )
    primary_positive_days = row.get(
        'preview_validation_cost_reduction_positive_days_pct',
        row.get('preview_cost_reduction_positive_days_pct'),
    )
    return (
        float(primary_cost_reduction or 0.0),
        float(primary_min_cost_reduction or 0.0),
        float(primary_positive_days or 0.0),
        float(primary_return or 0.0),
        float(primary_alpha or 0.0),
        float(row.get('preview_cost_reduction_pct') or 0.0),
        float(row.get('preview_min_cost_reduction_pct') or 0.0),
        float(row.get('preview_cost_reduction_positive_days_pct') or 0.0),
        float(row.get('preview_total_return_pct') or 0.0),
        int(row.get('preview_round_trips') or 0),
    )


def _preview_drawdown_allowed(drawdown_pct: float, max_abs_pct: float) -> bool:
    if max_abs_pct == float('inf'):
        return True
    return float(drawdown_pct or 0.0) >= -abs(float(max_abs_pct))


def _preview_win_rate_allowed(win_rate: float, min_pct: float) -> bool:
    return float(win_rate or 0.0) >= float(min_pct or 0.0)


def _preview_cost_path_allowed(
    min_cost_reduction_pct: float,
    positive_days_pct: float,
    min_floor_pct: float,
    min_positive_days_pct: float,
) -> bool:
    return (
        float(min_cost_reduction_pct or 0.0) >= float(min_floor_pct) and
        float(positive_days_pct or 0.0) >= float(min_positive_days_pct or 0.0)
    )


def _split_bars_for_validation(
    bars: list[dict],
    validation_ratio: float,
) -> tuple[list[dict], list[dict]]:
    ratio = max(0.0, min(0.8, validation_ratio))
    if ratio <= 0.0:
        return bars, []

    ordered_days: list[date] = []
    seen: set[date] = set()
    for bar in bars:
        day = _bar_day(bar)
        if day is None or day in seen:
            continue
        seen.add(day)
        ordered_days.append(day)

    if len(ordered_days) < 2:
        return bars, []

    validation_days = max(1, round(len(ordered_days) * ratio))
    validation_days = min(validation_days, len(ordered_days) - 1)
    validation_day_set = set(ordered_days[-validation_days:])
    train = [bar for bar in bars if _bar_day(bar) not in validation_day_set]
    validation = [bar for bar in bars if _bar_day(bar) in validation_day_set]
    if not train or not validation:
        return bars, []
    return train, validation


def _count_bar_days(bars: list[dict]) -> int:
    return len({d for d in (_bar_day(bar) for bar in bars) if d is not None})


def _run_t0_portfolio_with_strategy(
    code: str,
    bars: list[dict],
    *,
    allocation: dict,
    initial_capital: float,
    strategy_params: dict,
    base_position_pct: float | None = None,
    t_shares_pct: float | None = None,
) -> dict:
    result = run_t0_portfolio_backtest(
        code,
        bars,
        initial_capital=initial_capital,
        base_position_pct=(
            float(base_position_pct)
            if base_position_pct is not None
            else float(allocation['base_position_pct'])
        ),
        t_shares_pct=(
            float(t_shares_pct)
            if t_shares_pct is not None
            else float(allocation['t_shares_pct'])
        ),
        min_amplitude_pct=float(strategy_params.get('min_amplitude_pct', 1.0)),
        high_band=float(strategy_params.get('high_band', 0.82)),
        low_band=float(strategy_params.get('low_band', 0.25)),
        take_profit_pct=float(strategy_params.get('take_profit_pct', 0.8)),
        stop_loss_pct=float(strategy_params.get('stop_loss_pct', 1.2)),
        fee_bps=float(strategy_params.get('fee_bps', 2.5)),
        sell_tax_bps=float(strategy_params.get('sell_tax_bps', 5.0)),
        slippage_bps=float(strategy_params.get('slippage_bps', 2.0)),
        allow_sell_first=bool(strategy_params.get('allow_sell_first', True)),
        allow_buy_first=bool(strategy_params.get('allow_buy_first', True)),
        max_round_trips_per_day=int(strategy_params.get('max_round_trips_per_day', 1)),
        stop_after_daily_loss=bool(strategy_params.get('stop_after_daily_loss', False)),
        stop_after_cost_floor_pct=(
            float(strategy_params['stop_after_cost_floor_pct'])
            if strategy_params.get('stop_after_cost_floor_pct') is not None
            else None
        ),
        earliest_entry_time=str(strategy_params.get('earliest_entry_time', '09:35')),
        latest_entry_time=str(strategy_params.get('latest_entry_time', '14:00')),
    )
    result['selected_variant'] = strategy_params.get('selected_variant', 'default')
    return result


@api_bp.route('/t0/signal')
def t0_signal():
    code = (request.args.get('code') or '').strip().upper()
    if not code:
        return jsonify({'error': 'code required'}), 400

    min_amplitude_pct, err = _float_arg('min_amplitude_pct', 1.0)
    if err:
        return jsonify({'error': err}), 400

    count_raw = request.args.get('count', '60')
    try:
        count = max(1, min(240, int(count_raw)))
    except ValueError:
        return jsonify({'error': 'count must be integer'}), 400

    snapshot = tdx.get_snapshot(code) or {}
    bars = tdx.get_kline(code, period='1m', count=count, dividend_type='front')
    bars = bars if isinstance(bars, list) else []
    latest_day = _latest_bar_day(bars)
    as_of = _as_of_date()
    minute_stale = latest_day is None or (as_of - latest_day).days > 7
    if minute_stale:
        scored = score_snapshot(snapshot, min_amplitude_pct=3.0)
        scored['data_mode'] = 'snapshot_fallback'
        scored['reasons'].insert(
            0,
            '1m bars stale/unavailable; using current snapshot high/low range',
        )
    else:
        scored = score_minute_bars(
            code,
            bars,
            last_close=snapshot.get('lastClose'),
            name=snapshot.get('name') or '',
            min_amplitude_pct=min_amplitude_pct,
        )
        scored['data_mode'] = 'minute_1m'
    scored['source'] = 'tdx_get_market_data'
    scored['minute_stale'] = minute_stale
    scored['minute_latest_date'] = latest_day.isoformat() if latest_day else None
    return jsonify(scored)


@api_bp.route('/t0/grid', methods=['POST'])
def t0_grid():
    body = request.get_json(silent=True) or {}
    code = str(body.get('code') or '688981.SH').strip().upper()
    top = int(body.get('top') or 20)
    count = int(body.get('count') or -1)
    min_last_date = _parse_date(body.get('min_last_date'))
    bars = tdx.get_kline(code, period='1m', count=count, dividend_type='front')
    bars = bars if isinstance(bars, list) else []
    first, last = _coverage(bars)
    stale = False
    stale_reason = None
    if min_last_date and (last is None or last < min_last_date):
        stale = True
        latest_text = last.isoformat() if last else 'none'
        stale_reason = (
            f'latest 1m bar {latest_text} < required {min_last_date.isoformat()}'
        )

    rows = run_grid_search(code, bars, top_n=max(1, min(100, top))) if bars else []
    return jsonify({
        'code': code,
        'coverage': {
            'first': first.isoformat() if first else None,
            'last': last.isoformat() if last else None,
            'bar_count': len(bars),
            'is_stale': stale,
            'stale_reason': stale_reason,
        },
        'rows': rows,
    })


@api_bp.route('/t0/candidates', methods=['POST'])
def t0_candidates():
    body = request.get_json(silent=True) or {}
    roots = body.get('roots')
    if roots is not None and not isinstance(roots, list):
        return jsonify({'error': 'roots must be a list of minline directories'}), 400
    top = max(1, min(100, _body_int(body, 'top', 30)))
    max_files = max(1, min(20_000, _body_int(body, 'max_files', 2_000)))
    with_backtest = _body_bool(body, 'with_backtest', False)
    preview_pool = max(top, min(800, _body_int(body, 'preview_pool', top * 5)))
    rows = scan_lc1_candidates(
        roots,
        top_n=preview_pool if with_backtest else top,
        max_files=max_files,
        score_profile=str(body.get('score_profile') or 'stable_t'),
        min_days=_body_int(body, 'min_days', 50),
        min_avg_amp_pct=_body_float(body, 'min_avg_amp_pct', 3.0),
        max_avg_amp_pct=_body_float(body, 'max_avg_amp_pct', 15.0),
        min_return_pct=_body_float(body, 'min_return_pct', -30.0),
        max_return_pct=_body_float(body, 'max_return_pct', 120.0),
    )
    if with_backtest:
        min_preview_trips = max(0, _body_int(body, 'min_preview_trips', 1))
        min_preview_return_pct = _body_float(
            body, 'min_preview_return_pct', float('-inf'),
        )
        min_preview_alpha_vs_all_in = _body_float(
            body, 'min_preview_alpha_vs_all_in', float('-inf'),
        )
        min_preview_cost_reduction_pct = _body_float(
            body, 'min_preview_cost_reduction_pct', float('-inf'),
        )
        min_preview_min_cost_reduction_pct = _body_float(
            body, 'min_preview_min_cost_reduction_pct', float('-inf'),
        )
        min_preview_cost_reduction_positive_days_pct = _body_float(
            body, 'min_preview_cost_reduction_positive_days_pct', 0.0,
        )
        min_preview_win_rate = _body_float(body, 'min_preview_win_rate', 0.0)
        max_preview_drawdown_pct = _body_float(
            body, 'max_preview_drawdown_pct', float('inf'),
        )
        validation_ratio = _body_float(body, 'preview_validation_ratio', 0.0)
        min_preview_validation_trips = max(
            0, _body_int(body, 'min_preview_validation_trips', 0),
        )
        min_preview_validation_win_rate = _body_float(
            body, 'min_preview_validation_win_rate', 0.0,
        )
        min_preview_validation_return_pct = _body_float(
            body, 'min_preview_validation_return_pct', float('-inf'),
        )
        min_preview_validation_alpha_vs_all_in = _body_float(
            body, 'min_preview_validation_alpha_vs_all_in', float('-inf'),
        )
        min_preview_validation_cost_reduction_pct = _body_float(
            body, 'min_preview_validation_cost_reduction_pct', float('-inf'),
        )
        min_preview_validation_min_cost_reduction_pct = _body_float(
            body, 'min_preview_validation_min_cost_reduction_pct',
            float('-inf'),
        )
        min_preview_validation_cost_reduction_positive_days_pct = _body_float(
            body, 'min_preview_validation_cost_reduction_positive_days_pct',
            0.0,
        )
        max_preview_validation_drawdown_pct = _body_float(
            body, 'max_preview_validation_drawdown_pct', float('inf'),
        )
        previewed = []
        for row in rows:
            bars = load_lc1_bars_for_code(str(row['code']), roots)
            if not bars:
                continue
            train_bars, validation_bars = _split_bars_for_validation(
                bars, validation_ratio,
            )
            selection_bars = train_bars if validation_bars else bars
            allocation = choose_t0_allocation(selection_bars)
            variants = t0_strategy_variants(allocation)
            selected = choose_best_t0_result(
                _run_t0_portfolio_with_strategy(
                    str(row['code']),
                    selection_bars,
                    allocation=allocation,
                    initial_capital=1_000_000.0,
                    strategy_params=params,
                )
                for params in variants
            )
            selected_variant = selected['selected_variant']
            selected_params = next(
                p for p in variants if p['selected_variant'] == selected_variant
            )
            result = _run_t0_portfolio_with_strategy(
                str(row['code']),
                bars,
                allocation=allocation,
                initial_capital=1_000_000.0,
                strategy_params=selected_params,
            )
            row = dict(row)
            row.update({
                'preview_total_return_pct': result['total_return_pct'],
                'preview_final_equity': result['final_equity'],
                'preview_alpha_vs_all_in': result['alpha_vs_all_in_hold'],
                'preview_alpha_vs_base': result['alpha_vs_base_hold'],
                'preview_round_trips': result['round_trips'],
                'preview_win_rate': result['win_rate'],
                'preview_max_drawdown_pct': result['max_drawdown_pct'],
                'preview_selected_variant': result['selected_variant'],
                'preview_cost_reduction_pct': result['cost_reduction_pct'],
                'preview_cost_reduction_per_share': (
                    result['cost_reduction_per_share']
                ),
                'preview_min_cost_reduction_pct': (
                    result['min_cost_reduction_pct']
                ),
                'preview_cost_reduction_positive_days_pct': (
                    result['cost_reduction_positive_days_pct']
                ),
            })
            validation_pass = True
            if validation_bars:
                validation_result = _run_t0_portfolio_with_strategy(
                    str(row['code']),
                    validation_bars,
                    allocation=allocation,
                    initial_capital=1_000_000.0,
                    strategy_params=selected_params,
                )
                row.update({
                    'preview_train_total_return_pct': selected['total_return_pct'],
                    'preview_train_alpha_vs_all_in': selected['alpha_vs_all_in_hold'],
                    'preview_train_cost_reduction_pct': (
                        selected['cost_reduction_pct']
                    ),
                    'preview_train_min_cost_reduction_pct': (
                        selected['min_cost_reduction_pct']
                    ),
                    'preview_train_cost_reduction_positive_days_pct': (
                        selected['cost_reduction_positive_days_pct']
                    ),
                    'preview_validation_total_return_pct': (
                        validation_result['total_return_pct']
                    ),
                    'preview_validation_alpha_vs_all_in': (
                        validation_result['alpha_vs_all_in_hold']
                    ),
                    'preview_validation_round_trips': validation_result['round_trips'],
                    'preview_validation_win_rate': validation_result['win_rate'],
                    'preview_validation_max_drawdown_pct': (
                        validation_result['max_drawdown_pct']
                    ),
                    'preview_validation_cost_reduction_pct': (
                        validation_result['cost_reduction_pct']
                    ),
                    'preview_validation_cost_reduction_per_share': (
                        validation_result['cost_reduction_per_share']
                    ),
                    'preview_validation_min_cost_reduction_pct': (
                        validation_result['min_cost_reduction_pct']
                    ),
                    'preview_validation_cost_reduction_positive_days_pct': (
                        validation_result[
                            'cost_reduction_positive_days_pct'
                        ]
                    ),
                })
                validation_pass = (
                    validation_result['round_trips'] >=
                    min_preview_validation_trips and
                    _preview_win_rate_allowed(
                        validation_result['win_rate'],
                        min_preview_validation_win_rate,
                    ) and
                    validation_result['total_return_pct'] >=
                    min_preview_validation_return_pct and
                    validation_result['alpha_vs_all_in_hold'] >=
                    min_preview_validation_alpha_vs_all_in and
                    validation_result['cost_reduction_pct'] >=
                    min_preview_validation_cost_reduction_pct and
                    _preview_cost_path_allowed(
                        validation_result['min_cost_reduction_pct'],
                        validation_result[
                            'cost_reduction_positive_days_pct'
                        ],
                        min_preview_validation_min_cost_reduction_pct,
                        (
                            min_preview_validation_cost_reduction_positive_days_pct
                        ),
                    ) and
                    _preview_drawdown_allowed(
                        validation_result['max_drawdown_pct'],
                        max_preview_validation_drawdown_pct,
                    )
                )
            if (
                result['round_trips'] >= min_preview_trips and
                _preview_win_rate_allowed(
                    result['win_rate'], min_preview_win_rate,
                ) and
                result['total_return_pct'] >= min_preview_return_pct and
                result['alpha_vs_all_in_hold'] >= min_preview_alpha_vs_all_in and
                result['cost_reduction_pct'] >= min_preview_cost_reduction_pct and
                _preview_cost_path_allowed(
                    result['min_cost_reduction_pct'],
                    result['cost_reduction_positive_days_pct'],
                    min_preview_min_cost_reduction_pct,
                    min_preview_cost_reduction_positive_days_pct,
                ) and
                _preview_drawdown_allowed(
                    result['max_drawdown_pct'], max_preview_drawdown_pct,
                ) and
                validation_pass
            ):
                previewed.append(row)
        previewed.sort(
            key=_preview_sort_key,
            reverse=True,
        )
        rows = previewed[:top]
    return jsonify({
        'count': len(rows),
        'rows': rows,
    })


@api_bp.route('/t0/portfolio', methods=['POST'])
def t0_portfolio():
    body = request.get_json(silent=True) or {}
    code = str(body.get('code') or '688981.SH').strip().upper()
    count = _body_int(body, 'count', -1)
    bars = tdx.get_kline(code, period='1m', count=count, dividend_type='front')
    bars = bars if isinstance(bars, list) else []
    data_source = 'tdx_sdk'
    if not bars:
        roots = body.get('roots')
        if roots is not None and not isinstance(roots, list):
            return jsonify({'error': 'roots must be a list of minline directories'}), 400
        bars = load_lc1_bars_for_code(code, roots)
        data_source = 'local_lc1' if bars else data_source
    if not bars:
        return jsonify({'error': f'no 1m bars for {code}'}), 404
    strategy_selection_ratio = _body_float(body, 'strategy_selection_ratio', 0.0)
    selection_bars, _ = _split_bars_for_validation(
        bars, strategy_selection_ratio,
    )
    allocation = choose_t0_allocation(
        selection_bars,
        requested_mode=str(body.get('allocation_mode') or 'auto'),
    )
    base_position_pct = (
        _body_float(body, 'base_position_pct', allocation['base_position_pct'])
        if _has_body_value(body, 'base_position_pct')
        else allocation['base_position_pct']
    )
    t_shares_pct = (
        _body_float(body, 't_shares_pct', allocation['t_shares_pct'])
        if _has_body_value(body, 't_shares_pct')
        else allocation['t_shares_pct']
    )
    strategy_defaults = allocation.get('strategy_params', {})
    manual_strategy_keys = {
        'min_amplitude_pct', 'high_band', 'low_band', 'take_profit_pct',
        'stop_loss_pct', 'fee_bps', 'sell_tax_bps', 'slippage_bps',
        'allow_sell_first', 'allow_buy_first', 'max_round_trips_per_day',
        'stop_after_daily_loss', 'stop_after_cost_floor_pct',
        'earliest_entry_time', 'latest_entry_time',
    }
    manual_strategy = any(_has_body_value(body, k) for k in manual_strategy_keys)
    if manual_strategy:
        variants = [{
            'selected_variant': 'manual',
            'min_amplitude_pct': _body_float(
                body, 'min_amplitude_pct',
                float(strategy_defaults.get('min_amplitude_pct', 1.0)),
            ),
            'high_band': _body_float(
                body, 'high_band',
                float(strategy_defaults.get('high_band', 0.82)),
            ),
            'low_band': _body_float(
                body, 'low_band',
                float(strategy_defaults.get('low_band', 0.25)),
            ),
            'take_profit_pct': _body_float(
                body, 'take_profit_pct',
                float(strategy_defaults.get('take_profit_pct', 0.8)),
            ),
            'stop_loss_pct': _body_float(
                body, 'stop_loss_pct',
                float(strategy_defaults.get('stop_loss_pct', 1.2)),
            ),
            'fee_bps': _body_float(body, 'fee_bps', 2.5),
            'sell_tax_bps': _body_float(body, 'sell_tax_bps', 5.0),
            'slippage_bps': _body_float(body, 'slippage_bps', 2.0),
            'allow_sell_first': _body_bool(
                body, 'allow_sell_first',
                bool(strategy_defaults.get('allow_sell_first', True)),
            ),
            'allow_buy_first': _body_bool(
                body, 'allow_buy_first',
                bool(strategy_defaults.get('allow_buy_first', True)),
            ),
            'max_round_trips_per_day': _body_int(
                body, 'max_round_trips_per_day',
                int(strategy_defaults.get('max_round_trips_per_day', 1)),
            ),
            'stop_after_daily_loss': _body_bool(
                body, 'stop_after_daily_loss',
                bool(strategy_defaults.get('stop_after_daily_loss', False)),
            ),
            'stop_after_cost_floor_pct': (
                _body_float(body, 'stop_after_cost_floor_pct', 0.0)
                if _has_body_value(body, 'stop_after_cost_floor_pct')
                else strategy_defaults.get('stop_after_cost_floor_pct')
            ),
            'earliest_entry_time': str(body.get('earliest_entry_time') or '09:35'),
            'latest_entry_time': str(
                body.get('latest_entry_time')
                or strategy_defaults.get('latest_entry_time')
                or '14:00'
            ),
        }]
    else:
        variants = t0_strategy_variants(allocation)
    selected = choose_best_t0_result(
        _run_t0_portfolio_with_strategy(
            code,
            selection_bars,
            allocation=allocation,
            initial_capital=_body_float(body, 'initial_capital', 1_000_000.0),
            base_position_pct=base_position_pct,
            t_shares_pct=t_shares_pct,
            strategy_params=params,
        )
        for params in variants
    )
    selected_variant = selected['selected_variant']
    selected_params = next(
        p for p in variants if p['selected_variant'] == selected_variant
    )
    result = (
        selected if selection_bars is bars else
        _run_t0_portfolio_with_strategy(
            code,
            bars,
            allocation=allocation,
            initial_capital=_body_float(body, 'initial_capital', 1_000_000.0),
            base_position_pct=base_position_pct,
            t_shares_pct=t_shares_pct,
            strategy_params=selected_params,
        )
    )
    result['allocation'] = allocation
    result['data_source'] = data_source
    result['strategy_selection_ratio'] = max(
        0.0, min(0.8, strategy_selection_ratio),
    )
    result['strategy_selection_days'] = _count_bar_days(selection_bars)
    return jsonify(result)
