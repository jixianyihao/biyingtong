from __future__ import annotations

from datetime import date, datetime

from flask import jsonify, request

from t0.scorer import score_minute_bars, score_snapshot
from t0.allocator import choose_t0_allocation
from t0.grid import run_grid_search
from t0.local_lc1 import load_lc1_bars_for_code, scan_lc1_candidates
from t0.portfolio import run_t0_portfolio_backtest
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


def _preview_sort_key(row: dict) -> tuple[float, float, int]:
    """Rank already-filtered candidates by actual portfolio outcome first."""
    return (
        float(row.get('preview_total_return_pct') or 0.0),
        float(row.get('preview_alpha_vs_all_in') or 0.0),
        int(row.get('preview_round_trips') or 0),
    )


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
        previewed = []
        for row in rows:
            bars = load_lc1_bars_for_code(str(row['code']), roots)
            if not bars:
                continue
            allocation = choose_t0_allocation(bars)
            defaults = allocation.get('strategy_params', {})
            result = run_t0_portfolio_backtest(
                str(row['code']),
                bars,
                initial_capital=1_000_000.0,
                base_position_pct=float(allocation['base_position_pct']),
                t_shares_pct=float(allocation['t_shares_pct']),
                min_amplitude_pct=float(defaults.get('min_amplitude_pct', 1.0)),
                high_band=float(defaults.get('high_band', 0.82)),
                low_band=float(defaults.get('low_band', 0.25)),
                take_profit_pct=float(defaults.get('take_profit_pct', 0.8)),
                stop_loss_pct=float(defaults.get('stop_loss_pct', 1.2)),
                allow_sell_first=bool(defaults.get('allow_sell_first', True)),
                allow_buy_first=bool(defaults.get('allow_buy_first', True)),
                max_round_trips_per_day=int(defaults.get('max_round_trips_per_day', 1)),
                latest_entry_time=str(defaults.get('latest_entry_time', '14:00')),
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
            })
            if (
                result['round_trips'] >= min_preview_trips and
                result['total_return_pct'] >= min_preview_return_pct and
                result['alpha_vs_all_in_hold'] >= min_preview_alpha_vs_all_in
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
    allocation = choose_t0_allocation(
        bars,
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
    result = run_t0_portfolio_backtest(
        code,
        bars,
        initial_capital=_body_float(body, 'initial_capital', 1_000_000.0),
        base_position_pct=base_position_pct,
        t_shares_pct=t_shares_pct,
        min_amplitude_pct=_body_float(
            body, 'min_amplitude_pct',
            float(strategy_defaults.get('min_amplitude_pct', 1.0)),
        ),
        high_band=_body_float(
            body, 'high_band',
            float(strategy_defaults.get('high_band', 0.82)),
        ),
        low_band=_body_float(
            body, 'low_band',
            float(strategy_defaults.get('low_band', 0.25)),
        ),
        take_profit_pct=_body_float(
            body, 'take_profit_pct',
            float(strategy_defaults.get('take_profit_pct', 0.8)),
        ),
        stop_loss_pct=_body_float(
            body, 'stop_loss_pct',
            float(strategy_defaults.get('stop_loss_pct', 1.2)),
        ),
        fee_bps=_body_float(body, 'fee_bps', 2.5),
        sell_tax_bps=_body_float(body, 'sell_tax_bps', 5.0),
        slippage_bps=_body_float(body, 'slippage_bps', 2.0),
        allow_sell_first=_body_bool(
            body, 'allow_sell_first',
            bool(strategy_defaults.get('allow_sell_first', True)),
        ),
        allow_buy_first=_body_bool(
            body, 'allow_buy_first',
            bool(strategy_defaults.get('allow_buy_first', True)),
        ),
        max_round_trips_per_day=_body_int(
            body, 'max_round_trips_per_day',
            int(strategy_defaults.get('max_round_trips_per_day', 1)),
        ),
        earliest_entry_time=str(body.get('earliest_entry_time') or '09:35'),
        latest_entry_time=str(
            body.get('latest_entry_time')
            or strategy_defaults.get('latest_entry_time')
            or '14:00'
        ),
    )
    result['allocation'] = allocation
    result['data_source'] = data_source
    return jsonify(result)
