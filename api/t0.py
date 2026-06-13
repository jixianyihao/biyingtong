from __future__ import annotations

from datetime import date, datetime

from flask import jsonify, request

from t0.scorer import score_minute_bars, score_snapshot
from t0.allocator import choose_t0_allocation
from t0.grid import run_grid_search
from t0.local_lc1 import load_lc1_bars_for_code, scan_lc1_candidates
from t0.optimizer import T0OptimizerConstraints, optimize_t0_parameters
from t0.portfolio import run_t0_portfolio_backtest
from t0.strategy_selector import (
    choose_best_t0_result,
    choose_best_validated_t0_result,
    t0_strategy_variants,
)
from t0.strategy_profiles import (
    DEFAULT_T0_STRATEGY_PROFILE,
    get_t0_strategy_profile,
    list_t0_strategy_profiles,
)
from tdx_service import tdx

from . import api_bp


_T0_PORTFOLIO_PREVIEW_CACHE: dict[tuple, dict] = {}
_T0_PORTFOLIO_PREVIEW_CACHE_MAX = 5_000

DEFAULT_T0_OPTIMIZER_GRID = DEFAULT_T0_STRATEGY_PROFILE.optimizer_grid


def _float_arg(name: str, default: float):
    raw = request.args.get(name)
    if raw is None or raw == '':
        return default, None
    try:
        return float(raw), None
    except ValueError:
        return default, f'{name} must be numeric'


def _optimizer_grid_size(grid: dict) -> int:
    total = 1
    for values in grid.values():
        total *= len(list(values))
    return total


@api_bp.route('/t0/strategy-profiles')
def t0_strategy_profiles():
    profiles = []
    for profile in list_t0_strategy_profiles():
        profiles.append({
            'name': profile.name,
            'display_name': profile.display_name,
            'description': profile.description,
            'base_params': profile.base_params,
            'optimizer_grid': profile.optimizer_grid,
            'optimizer_grid_size': _optimizer_grid_size(profile.optimizer_grid) + 1,
        })
    return jsonify({'count': len(profiles), 'profiles': profiles})


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
) -> tuple[float, ...]:
    """Rank candidates by out-of-sample outcome when available.

    If fold fields are present, stable pass rate and worst-fold cost path are
    primary. Otherwise use validation/full-period cost-reduction. Returns and
    alpha remain tie-breakers instead of the main goal.
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
    fold_pass_rate = row.get('preview_validation_pass_rate_pct', 0.0)
    fold_worst_cost = row.get(
        'preview_validation_worst_cost_reduction_pct',
        primary_cost_reduction,
    )
    fold_worst_min_cost = row.get(
        'preview_validation_worst_min_cost_reduction_pct',
        primary_min_cost_reduction,
    )
    fold_avg_cost = row.get(
        'preview_validation_avg_cost_reduction_pct',
        primary_cost_reduction,
    )
    next_bar_cost = row.get('preview_next_bar_cost_reduction_pct')
    next_bar_min_cost = row.get('preview_next_bar_min_cost_reduction_pct')
    has_next_bar_stress = 1.0 if next_bar_cost is not None else 0.0
    next_bar_fold_pass_rate = row.get(
        'preview_validation_next_bar_pass_rate_pct', 0.0,
    )
    next_bar_fold_worst_cost = row.get(
        'preview_validation_next_bar_worst_cost_reduction_pct',
        next_bar_cost,
    )
    next_bar_fold_worst_min_cost = row.get(
        'preview_validation_next_bar_worst_min_cost_reduction_pct',
        next_bar_min_cost,
    )
    next_bar_fold_avg_cost = row.get(
        'preview_validation_next_bar_avg_cost_reduction_pct',
        next_bar_cost,
    )
    optimizer_validation_cost = row.get(
        'optimizer_best_validation_cost_reduction_pct',
    )
    optimizer_full_cost = row.get('optimizer_best_cost_reduction_pct')
    optimizer_has_best = (
        1.0 if (
            optimizer_validation_cost is not None or
            optimizer_full_cost is not None
        ) else 0.0
    )
    optimizer_fold_pass_rate = row.get(
        'optimizer_best_fold_pass_rate_pct', 0.0,
    )
    optimizer_worst_fold_cost = row.get(
        'optimizer_best_worst_fold_cost_reduction_pct',
        optimizer_validation_cost,
    )
    return (
        optimizer_has_best,
        float(optimizer_fold_pass_rate or 0.0),
        float(optimizer_worst_fold_cost or 0.0),
        float(optimizer_validation_cost or 0.0),
        float(optimizer_full_cost or 0.0),
        has_next_bar_stress,
        float(next_bar_fold_pass_rate or 0.0),
        float(next_bar_fold_worst_cost or 0.0),
        float(next_bar_fold_worst_min_cost or 0.0),
        float(next_bar_fold_avg_cost or 0.0),
        float(next_bar_cost or 0.0),
        float(next_bar_min_cost or 0.0),
        float(fold_pass_rate or 0.0),
        float(fold_worst_cost or 0.0),
        float(fold_worst_min_cost or 0.0),
        float(fold_avg_cost or 0.0),
        float(primary_cost_reduction or 0.0),
        float(primary_min_cost_reduction or 0.0),
        float(primary_positive_days or 0.0),
        float(primary_return or 0.0),
        float(primary_alpha or 0.0),
        float(row.get('preview_cost_reduction_pct') or 0.0),
        float(row.get('preview_min_cost_reduction_pct') or 0.0),
        float(row.get('preview_cost_reduction_positive_days_pct') or 0.0),
        float(row.get('preview_total_return_pct') or 0.0),
        float(row.get('preview_round_trips') or 0),
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


def _fold_min_trips(total_min_trips: int, folds: int) -> int:
    total = max(0, int(total_min_trips or 0))
    if total <= 1:
        return total
    fold_count = max(1, int(folds or 1))
    return max(1, (total + fold_count - 1) // fold_count)


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


def _split_validation_folds(bars: list[dict], folds: int) -> list[list[dict]]:
    """Split validation bars into contiguous day folds for stability checks."""
    ordered_days: list[date] = []
    seen: set[date] = set()
    for bar in bars:
        day = _bar_day(bar)
        if day is None or day in seen:
            continue
        seen.add(day)
        ordered_days.append(day)

    if not ordered_days:
        return []

    fold_count = max(1, min(int(folds or 1), len(ordered_days)))
    chunks: list[list[dict]] = []
    for idx in range(fold_count):
        start = idx * len(ordered_days) // fold_count
        end = (idx + 1) * len(ordered_days) // fold_count
        day_set = set(ordered_days[start:end])
        chunk = [bar for bar in bars if _bar_day(bar) in day_set]
        if chunk:
            chunks.append(chunk)
    return chunks


def _preview_result_passes(
    result: dict,
    *,
    min_trips: int,
    min_win_rate: float,
    min_return_pct: float,
    min_alpha_vs_all_in: float,
    min_cost_reduction_pct: float,
    min_min_cost_reduction_pct: float,
    min_cost_reduction_positive_days_pct: float,
    max_drawdown_pct: float,
) -> bool:
    return (
        result['round_trips'] >= min_trips and
        _preview_win_rate_allowed(result['win_rate'], min_win_rate) and
        result['total_return_pct'] >= min_return_pct and
        result['alpha_vs_all_in_hold'] >= min_alpha_vs_all_in and
        result['cost_reduction_pct'] >= min_cost_reduction_pct and
        _preview_cost_path_allowed(
            result['min_cost_reduction_pct'],
            result['cost_reduction_positive_days_pct'],
            min_min_cost_reduction_pct,
            min_cost_reduction_positive_days_pct,
        ) and
        _preview_drawdown_allowed(result['max_drawdown_pct'], max_drawdown_pct)
    )


def _preview_fold_result_passes(
    result: dict,
    *,
    min_trips: int,
    min_cost_reduction_pct: float,
    min_min_cost_reduction_pct: float,
    max_drawdown_pct: float,
) -> bool:
    """Small validation folds are stability checks, not full strategy ratings."""
    return (
        result['round_trips'] >= min_trips and
        result['cost_reduction_pct'] >= min_cost_reduction_pct and
        result['min_cost_reduction_pct'] >= min_min_cost_reduction_pct and
        _preview_drawdown_allowed(result['max_drawdown_pct'], max_drawdown_pct)
    )


def _validation_fold_summary(
    results: list[dict],
    pass_flags: list[bool],
    *,
    prefix: str = 'preview_validation',
) -> dict:
    if not results:
        return {
            f'{prefix}_fold_count': 0,
            f'{prefix}_pass_count': 0,
            f'{prefix}_pass_rate_pct': 0.0,
            f'{prefix}_worst_cost_reduction_pct': 0.0,
            f'{prefix}_worst_min_cost_reduction_pct': 0.0,
            f'{prefix}_avg_cost_reduction_pct': 0.0,
        }
    cost_values = [float(r.get('cost_reduction_pct') or 0.0) for r in results]
    min_cost_values = [
        float(r.get('min_cost_reduction_pct') or 0.0) for r in results
    ]
    pass_count = sum(1 for flag in pass_flags if flag)
    return {
        f'{prefix}_fold_count': len(results),
        f'{prefix}_pass_count': pass_count,
        f'{prefix}_pass_rate_pct': round(
            pass_count / len(results) * 100.0, 4,
        ),
        f'{prefix}_worst_cost_reduction_pct': round(
            min(cost_values), 4,
        ),
        f'{prefix}_worst_min_cost_reduction_pct': round(
            min(min_cost_values), 4,
        ),
        f'{prefix}_avg_cost_reduction_pct': round(
            sum(cost_values) / len(cost_values), 4,
        ),
    }


def _count_bar_days(bars: list[dict]) -> int:
    return len({d for d in (_bar_day(bar) for bar in bars) if d is not None})


def _bars_cache_signature(bars: list[dict]) -> tuple:
    if not bars:
        return (0,)
    first = bars[0]
    last = bars[-1]
    close_sum = round(
        sum(float(bar.get('close') or 0.0) for bar in bars),
        6,
    )
    return (
        len(bars),
        str(first.get('date') or ''),
        float(first.get('open') or 0.0),
        float(first.get('high') or 0.0),
        float(first.get('low') or 0.0),
        float(first.get('close') or 0.0),
        str(last.get('date') or ''),
        float(last.get('open') or 0.0),
        float(last.get('high') or 0.0),
        float(last.get('low') or 0.0),
        float(last.get('close') or 0.0),
        close_sum,
    )


def _strategy_cache_signature(strategy_params: dict) -> tuple:
    return tuple(
        (str(key), repr(value))
        for key, value in sorted(strategy_params.items())
    )


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
    base_pct = (
        float(strategy_params['base_position_pct'])
        if strategy_params.get('base_position_pct') is not None
        else float(base_position_pct)
        if base_position_pct is not None
        else float(allocation['base_position_pct'])
    )
    t_pct = (
        float(strategy_params['t_shares_pct'])
        if strategy_params.get('t_shares_pct') is not None
        else float(t_shares_pct)
        if t_shares_pct is not None
        else float(allocation['t_shares_pct'])
    )
    cache_key = (
        str(code).upper(),
        _bars_cache_signature(bars),
        float(initial_capital),
        base_pct,
        t_pct,
        _strategy_cache_signature(strategy_params),
    )
    cached = _T0_PORTFOLIO_PREVIEW_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    result = run_t0_portfolio_backtest(
        code,
        bars,
        initial_capital=initial_capital,
        base_position_pct=base_pct,
        t_shares_pct=t_pct,
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
        signal_mode=str(strategy_params.get('signal_mode') or 'band'),
        vwap_deviation_pct=float(
            strategy_params.get('vwap_deviation_pct', 1.0),
        ),
        vwap_zscore_threshold=float(
            strategy_params.get('vwap_zscore_threshold', 1.5),
        ),
        execution_style=str(strategy_params.get('execution_style') or 'market'),
        earliest_entry_time=str(strategy_params.get('earliest_entry_time', '09:35')),
        latest_entry_time=str(strategy_params.get('latest_entry_time', '14:00')),
    )
    result['selected_variant'] = strategy_params.get('selected_variant', 'default')
    if len(_T0_PORTFOLIO_PREVIEW_CACHE) >= _T0_PORTFOLIO_PREVIEW_CACHE_MAX:
        _T0_PORTFOLIO_PREVIEW_CACHE.clear()
    _T0_PORTFOLIO_PREVIEW_CACHE[cache_key] = dict(result)
    return result


def _load_t0_bars_from_body(code: str, body: dict) -> tuple[list[dict], str]:
    count = _body_int(body, 'count', -1)
    bars = tdx.get_kline(code, period='1m', count=count, dividend_type='front')
    bars = bars if isinstance(bars, list) else []
    data_source = 'tdx_sdk'
    if not bars:
        roots = body.get('roots')
        if roots is not None and not isinstance(roots, list):
            raise ValueError('roots must be a list of minline directories')
        bars = load_lc1_bars_for_code(code, roots)
        data_source = 'local_lc1' if bars else data_source
    return bars, data_source


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
    try:
        strategy_profile = get_t0_strategy_profile(body.get('strategy_profile'))
    except KeyError as exc:
        return jsonify({'error': str(exc)}), 400
    roots = body.get('roots')
    if roots is not None and not isinstance(roots, list):
        return jsonify({'error': 'roots must be a list of minline directories'}), 400
    top = max(1, min(100, _body_int(body, 'top', 30)))
    max_files = max(1, min(20_000, _body_int(body, 'max_files', 2_000)))
    with_optimizer = _body_bool(body, 'with_optimizer', False)
    with_backtest = _body_bool(body, 'with_backtest', False) or with_optimizer
    with_next_bar_stress = _body_bool(body, 'with_next_bar_stress', False)
    optimizer_limit = max(1, min(200, _body_int(body, 'optimizer_limit', 40)))
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
        min_preview_next_bar_cost_reduction_pct = _body_float(
            body, 'min_preview_next_bar_cost_reduction_pct', float('-inf'),
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
        min_preview_validation_fold_cost_reduction_pct = _body_float(
            body,
            'min_preview_validation_fold_cost_reduction_pct',
            min_preview_validation_cost_reduction_pct,
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
        preview_validation_folds = max(
            1, min(12, _body_int(body, 'preview_validation_folds', 1)),
        )
        min_preview_validation_pass_rate_pct = _body_float(
            body, 'min_preview_validation_pass_rate_pct', 0.0,
        )
        min_preview_validation_next_bar_cost_reduction_pct = _body_float(
            body,
            'min_preview_validation_next_bar_cost_reduction_pct',
            min_preview_next_bar_cost_reduction_pct,
        )
        min_preview_validation_next_bar_pass_rate_pct = _body_float(
            body, 'min_preview_validation_next_bar_pass_rate_pct', 0.0,
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
            train_results = [
                _run_t0_portfolio_with_strategy(
                    str(row['code']),
                    selection_bars,
                    allocation=allocation,
                    initial_capital=1_000_000.0,
                    strategy_params=params,
                )
                for params in variants
            ]
            validation_selection_results = (
                [
                    _run_t0_portfolio_with_strategy(
                        str(row['code']),
                        validation_bars,
                        allocation=allocation,
                        initial_capital=1_000_000.0,
                        strategy_params=params,
                    )
                    for params in variants
                ]
                if validation_bars and len(variants) > 1
                else []
            )
            selected = choose_best_validated_t0_result(
                train_results,
                validation_selection_results,
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
            preview_pass = (
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
                )
            )
            if not preview_pass:
                continue
            next_bar_stress_pass = True
            if with_next_bar_stress:
                stress_params = {
                    **selected_params,
                    'selected_variant': (
                        f"{selected_params.get('selected_variant', 'default')}"
                        "_next_bar_stress"
                    ),
                    'execution_style': 'next_bar',
                }
                stress_result = _run_t0_portfolio_with_strategy(
                    str(row['code']),
                    bars,
                    allocation=allocation,
                    initial_capital=1_000_000.0,
                    strategy_params=stress_params,
                )
                row.update({
                    'preview_next_bar_total_return_pct': (
                        stress_result['total_return_pct']
                    ),
                    'preview_next_bar_alpha_vs_all_in': (
                        stress_result['alpha_vs_all_in_hold']
                    ),
                    'preview_next_bar_round_trips': (
                        stress_result['round_trips']
                    ),
                    'preview_next_bar_win_rate': stress_result['win_rate'],
                    'preview_next_bar_cost_reduction_pct': (
                        stress_result['cost_reduction_pct']
                    ),
                    'preview_next_bar_min_cost_reduction_pct': (
                        stress_result['min_cost_reduction_pct']
                    ),
                    'preview_next_bar_cost_reduction_positive_days_pct': (
                        stress_result[
                            'cost_reduction_positive_days_pct'
                        ]
                    ),
                    'preview_next_bar_selected_variant': (
                        stress_result['selected_variant']
                    ),
                })
                next_bar_stress_pass = (
                    stress_result['cost_reduction_pct'] >=
                    min_preview_next_bar_cost_reduction_pct
                )
                if not next_bar_stress_pass:
                    continue
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
                validation_pass = _preview_result_passes(
                    validation_result,
                    min_trips=min_preview_validation_trips,
                    min_win_rate=min_preview_validation_win_rate,
                    min_return_pct=min_preview_validation_return_pct,
                    min_alpha_vs_all_in=min_preview_validation_alpha_vs_all_in,
                    min_cost_reduction_pct=(
                        min_preview_validation_cost_reduction_pct
                    ),
                    min_min_cost_reduction_pct=(
                        min_preview_validation_min_cost_reduction_pct
                    ),
                    min_cost_reduction_positive_days_pct=(
                        min_preview_validation_cost_reduction_positive_days_pct
                    ),
                    max_drawdown_pct=max_preview_validation_drawdown_pct,
                )
                if preview_validation_folds > 1:
                    validation_folds = _split_validation_folds(
                        validation_bars, preview_validation_folds,
                    )
                    fold_min_trips = _fold_min_trips(
                        min_preview_validation_trips,
                        len(validation_folds),
                    )
                    fold_results = [
                        _run_t0_portfolio_with_strategy(
                            str(row['code']),
                            fold_bars,
                            allocation=allocation,
                            initial_capital=1_000_000.0,
                            strategy_params=selected_params,
                        )
                        for fold_bars in validation_folds
                    ]
                    fold_pass_flags = [
                        _preview_fold_result_passes(
                            fold_result,
                            min_trips=fold_min_trips,
                            min_cost_reduction_pct=(
                                min_preview_validation_fold_cost_reduction_pct
                            ),
                            min_min_cost_reduction_pct=(
                                min_preview_validation_min_cost_reduction_pct
                            ),
                            max_drawdown_pct=max_preview_validation_drawdown_pct,
                        )
                        for fold_result in fold_results
                    ]
                    fold_summary = _validation_fold_summary(
                        fold_results, fold_pass_flags,
                    )
                    row.update(fold_summary)
                    validation_pass = (
                        validation_pass and
                        fold_summary['preview_validation_pass_rate_pct'] >=
                        min_preview_validation_pass_rate_pct
                    )
                    if with_next_bar_stress:
                        fold_stress_params = {
                            **selected_params,
                            'selected_variant': (
                                f"{selected_params.get('selected_variant', 'default')}"
                                "_next_bar_validation_stress"
                            ),
                            'execution_style': 'next_bar',
                        }
                        next_bar_fold_results = [
                            _run_t0_portfolio_with_strategy(
                                str(row['code']),
                                fold_bars,
                                allocation=allocation,
                                initial_capital=1_000_000.0,
                                strategy_params=fold_stress_params,
                            )
                            for fold_bars in validation_folds
                        ]
                        next_bar_fold_pass_flags = [
                            _preview_fold_result_passes(
                                fold_result,
                                min_trips=fold_min_trips,
                                min_cost_reduction_pct=(
                                    min_preview_validation_next_bar_cost_reduction_pct
                                ),
                                min_min_cost_reduction_pct=(
                                    min_preview_validation_min_cost_reduction_pct
                                ),
                                max_drawdown_pct=max_preview_validation_drawdown_pct,
                            )
                            for fold_result in next_bar_fold_results
                        ]
                        next_bar_fold_summary = _validation_fold_summary(
                            next_bar_fold_results,
                            next_bar_fold_pass_flags,
                            prefix='preview_validation_next_bar',
                        )
                        row.update(next_bar_fold_summary)
                        validation_pass = (
                            validation_pass and
                            next_bar_fold_summary[
                                'preview_validation_next_bar_pass_rate_pct'
                            ] >= min_preview_validation_next_bar_pass_rate_pct
                        )
            if validation_pass and with_optimizer:
                optimizer_base_params = {
                    **selected_params,
                    'selected_variant': 'optimizer_candidate',
                    'signal_mode': selected_params.get('signal_mode', 'band'),
                    'execution_style': selected_params.get(
                        'execution_style', 'market',
                    ),
                    'stop_after_daily_loss': True,
                }
                optimizer = optimize_t0_parameters(
                    str(row['code']),
                    bars,
                    base_params=optimizer_base_params,
                    grid=strategy_profile.optimizer_grid,
                    run_strategy=(
                        lambda c, slice_bars, params:
                        _run_t0_portfolio_with_strategy(
                            c,
                            slice_bars,
                            allocation=allocation,
                            initial_capital=1_000_000.0,
                            strategy_params=params,
                        )
                    ),
                    offset=0,
                    limit=optimizer_limit,
                    validation_ratio=validation_ratio,
                    fold_count=preview_validation_folds,
                    include_base_candidate=True,
                    constraints=T0OptimizerConstraints(
                        min_full_cost_reduction_pct=(
                            min_preview_cost_reduction_pct
                            if min_preview_cost_reduction_pct != float('-inf')
                            else 0.5
                        ),
                        min_validation_cost_reduction_pct=(
                            min_preview_validation_cost_reduction_pct
                            if (
                                min_preview_validation_cost_reduction_pct !=
                                float('-inf')
                            )
                            else 0.2
                        ),
                        min_full_round_trips=max(1, min_preview_trips),
                        min_validation_round_trips=max(
                            1, min_preview_validation_trips,
                        ),
                        min_fold_cost_reduction_pct=(
                            min_preview_validation_fold_cost_reduction_pct
                            if (
                                min_preview_validation_fold_cost_reduction_pct !=
                                float('-inf')
                            )
                            else -1.2
                        ),
                        min_fold_min_cost_reduction_pct=(
                            min_preview_validation_min_cost_reduction_pct
                            if (
                                min_preview_validation_min_cost_reduction_pct !=
                                float('-inf')
                            )
                            else -1.2
                        ),
                    ),
                )
                row.update({
                    'optimizer_evaluated': optimizer['evaluated'],
                    'optimizer_next_offset': optimizer['next_offset'],
                    'optimizer_row_count': len(optimizer['rows']),
                })
                if optimizer['rows']:
                    best = optimizer['rows'][0]
                    row.update({
                        'optimizer_best_score': best['score'],
                        'optimizer_best_params': best['params'],
                        'optimizer_best_cost_reduction_pct': (
                            best['full'].get('cost_reduction_pct')
                        ),
                        'optimizer_best_validation_cost_reduction_pct': (
                            best['validation'].get('cost_reduction_pct')
                        ),
                        'optimizer_best_fold_pass_rate_pct': best.get(
                            'fold_pass_rate_pct',
                        ),
                        'optimizer_best_worst_fold_cost_reduction_pct': (
                            best.get('worst_fold_cost_reduction_pct')
                        ),
                    })
            if validation_pass:
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


@api_bp.route('/t0/optimize', methods=['POST'])
def t0_optimize():
    body = request.get_json(silent=True) or {}
    code = str(body.get('code') or '688981.SH').strip().upper()
    try:
        strategy_profile = get_t0_strategy_profile(body.get('strategy_profile'))
    except KeyError as exc:
        return jsonify({'error': str(exc)}), 400
    try:
        bars, data_source = _load_t0_bars_from_body(code, body)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    if not bars:
        return jsonify({'error': f'no 1m bars for {code}'}), 404

    initial_capital = _body_float(body, 'initial_capital', 1_000_000.0)
    strategy_selection_ratio = _body_float(body, 'strategy_selection_ratio', 0.35)
    selection_bars, validation_bars = _split_bars_for_validation(
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
    variants = t0_strategy_variants(allocation)
    train_results = [
        _run_t0_portfolio_with_strategy(
            code,
            selection_bars,
            allocation=allocation,
            initial_capital=initial_capital,
            base_position_pct=base_position_pct,
            t_shares_pct=t_shares_pct,
            strategy_params=params,
        )
        for params in variants
    ]
    validation_results = (
        [
            _run_t0_portfolio_with_strategy(
                code,
                validation_bars,
                allocation=allocation,
                initial_capital=initial_capital,
                base_position_pct=base_position_pct,
                t_shares_pct=t_shares_pct,
                strategy_params=params,
            )
            for params in variants
        ]
        if validation_bars and len(variants) > 1
        else []
    )
    selected = choose_best_validated_t0_result(train_results, validation_results)
    base_params = next(
        p for p in variants
        if p['selected_variant'] == selected['selected_variant']
    )
    base_params = {
        **base_params,
        'selected_variant': 'optimizer_candidate',
        'signal_mode': base_params.get('signal_mode', 'band'),
        'execution_style': base_params.get('execution_style', 'market'),
        'stop_after_daily_loss': True,
        'fee_bps': _body_float(body, 'fee_bps', 2.5),
        'sell_tax_bps': _body_float(body, 'sell_tax_bps', 5.0),
        'slippage_bps': _body_float(body, 'slippage_bps', 2.0),
    }
    grid = body.get('grid') or strategy_profile.optimizer_grid
    if not isinstance(grid, dict):
        return jsonify({'error': 'grid must be an object'}), 400

    optimizer = optimize_t0_parameters(
        code,
        bars,
        base_params=base_params,
        grid=grid,
        run_strategy=lambda c, slice_bars, params: _run_t0_portfolio_with_strategy(
            c,
            slice_bars,
            allocation=allocation,
            initial_capital=initial_capital,
            base_position_pct=base_position_pct,
            t_shares_pct=t_shares_pct,
            strategy_params=params,
        ),
        offset=_body_int(body, 'offset', 0),
        limit=_body_int(body, 'limit', 80),
        validation_ratio=_body_float(body, 'validation_ratio', 0.35),
        fold_count=_body_int(body, 'fold_count', 3),
        include_base_candidate=True,
        constraints=T0OptimizerConstraints(
            min_full_cost_reduction_pct=_body_float(
                body, 'min_full_cost_reduction_pct', 0.5,
            ),
            min_validation_cost_reduction_pct=_body_float(
                body, 'min_validation_cost_reduction_pct', 0.5,
            ),
            min_full_round_trips=_body_int(body, 'min_full_round_trips', 20),
            min_validation_round_trips=_body_int(
                body, 'min_validation_round_trips', 8,
            ),
            min_fold_cost_reduction_pct=_body_float(
                body, 'min_fold_cost_reduction_pct', -1.2,
            ),
            min_fold_min_cost_reduction_pct=_body_float(
                body, 'min_fold_min_cost_reduction_pct', -1.2,
            ),
        ),
    )
    return jsonify({
        'code': code,
        'data_source': data_source,
        'strategy_profile': strategy_profile.name,
        'allocation': allocation,
        'base_variant': selected['selected_variant'],
        'optimizer': optimizer,
    })


@api_bp.route('/t0/portfolio', methods=['POST'])
def t0_portfolio():
    body = request.get_json(silent=True) or {}
    code = str(body.get('code') or '688981.SH').strip().upper()
    try:
        bars, data_source = _load_t0_bars_from_body(code, body)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    if not bars:
        return jsonify({'error': f'no 1m bars for {code}'}), 404
    strategy_selection_ratio = _body_float(body, 'strategy_selection_ratio', 0.35)
    selection_bars, validation_bars = _split_bars_for_validation(
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
        'signal_mode', 'vwap_deviation_pct', 'vwap_zscore_threshold',
        'execution_style',
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
            'signal_mode': str(
                body.get('signal_mode')
                or strategy_defaults.get('signal_mode')
                or 'band'
            ),
            'vwap_deviation_pct': _body_float(
                body, 'vwap_deviation_pct',
                float(strategy_defaults.get('vwap_deviation_pct', 1.0)),
            ),
            'vwap_zscore_threshold': _body_float(
                body, 'vwap_zscore_threshold',
                float(strategy_defaults.get('vwap_zscore_threshold', 1.5)),
            ),
            'execution_style': str(
                body.get('execution_style')
                or strategy_defaults.get('execution_style')
                or 'market'
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
    train_results = [
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
    ]
    validation_results = (
        [
            _run_t0_portfolio_with_strategy(
                code,
                validation_bars,
                allocation=allocation,
                initial_capital=_body_float(
                    body, 'initial_capital', 1_000_000.0,
                ),
                base_position_pct=base_position_pct,
                t_shares_pct=t_shares_pct,
                strategy_params=params,
            )
            for params in variants
        ]
        if validation_bars and len(variants) > 1
        else []
    )
    selected = choose_best_validated_t0_result(train_results, validation_results)
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
    result['strategy_validation_days'] = _count_bar_days(validation_bars)
    return jsonify(result)
