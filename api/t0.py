from __future__ import annotations

from datetime import date, datetime

from flask import jsonify, request

from t0.scorer import score_minute_bars, score_snapshot
from t0.grid import run_grid_search
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


@api_bp.route('/t0/portfolio', methods=['POST'])
def t0_portfolio():
    body = request.get_json(silent=True) or {}
    code = str(body.get('code') or '688981.SH').strip().upper()
    count = _body_int(body, 'count', -1)
    bars = tdx.get_kline(code, period='1m', count=count, dividend_type='front')
    bars = bars if isinstance(bars, list) else []
    if not bars:
        return jsonify({'error': f'no 1m bars for {code}'}), 404
    result = run_t0_portfolio_backtest(
        code,
        bars,
        initial_capital=_body_float(body, 'initial_capital', 1_000_000.0),
        base_position_pct=_body_float(body, 'base_position_pct', 0.70),
        t_shares_pct=_body_float(body, 't_shares_pct', 0.25),
        min_amplitude_pct=_body_float(body, 'min_amplitude_pct', 1.0),
        high_band=_body_float(body, 'high_band', 0.82),
        low_band=_body_float(body, 'low_band', 0.25),
        take_profit_pct=_body_float(body, 'take_profit_pct', 0.8),
        stop_loss_pct=_body_float(body, 'stop_loss_pct', 1.2),
        fee_bps=_body_float(body, 'fee_bps', 2.5),
        sell_tax_bps=_body_float(body, 'sell_tax_bps', 5.0),
        slippage_bps=_body_float(body, 'slippage_bps', 2.0),
        allow_sell_first=bool(body.get('allow_sell_first', True)),
        allow_buy_first=bool(body.get('allow_buy_first', True)),
        max_round_trips_per_day=_body_int(body, 'max_round_trips_per_day', 1),
        earliest_entry_time=str(body.get('earliest_entry_time') or '09:35'),
        latest_entry_time=str(body.get('latest_entry_time') or '14:00'),
    )
    return jsonify(result)
