from __future__ import annotations

from typing import Any


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bar_float(bar: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _as_float(bar.get(key))
        if value is not None:
            return value
    return None


def _round(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def _invalid(code: str, bar_count: int, reason: str) -> dict[str, Any]:
    return {
        'code': code,
        'name': '',
        'action': 'invalid',
        'score': 0,
        'metrics': {
            'bar_count': bar_count,
            'amplitude_pct': None,
            'range_position': None,
            'day_pct': None,
            'last_price': None,
            'high': None,
            'low': None,
            'volume': None,
        },
        'reasons': [reason],
    }


def score_minute_bars(
    code: str,
    bars: list[dict[str, Any]],
    *,
    last_close: float | None = None,
    name: str = '',
    min_amplitude_pct: float = 1.0,
    low_band: float = 0.25,
    high_band: float = 0.82,
) -> dict[str, Any]:
    """Score 1-minute bars for a concentrated intraday T candidate."""
    clean: list[dict[str, Any]] = []
    for bar in bars or []:
        close = _bar_float(bar, 'close', 'Close')
        high = _bar_float(bar, 'high', 'High')
        low = _bar_float(bar, 'low', 'Low')
        if close is None or high is None or low is None:
            continue
        clean.append({
            'close': close,
            'high': high,
            'low': low,
            'vol': _bar_float(bar, 'vol', 'volume', 'Volume') or 0.0,
        })

    if not clean:
        return _invalid(code, 0, 'no usable 1m bars')

    last_price = clean[-1]['close']
    high = max(b['high'] for b in clean)
    low = min(b['low'] for b in clean)
    volume = sum(b['vol'] for b in clean)
    if high <= 0 or low <= 0 or last_price <= 0 or high < low:
        return _invalid(code, len(clean), 'invalid OHLC values')

    base = last_close if last_close and last_close > 0 else clean[0]['close']
    intraday_range = high - low
    amplitude_pct = intraday_range / base * 100.0 if base > 0 else 0.0
    day_pct = (last_price - base) / base * 100.0 if base > 0 else 0.0
    range_position = (
        (last_price - low) / intraday_range if intraday_range > 0 else 0.5
    )
    range_position = max(0.0, min(1.0, range_position))

    reasons: list[str] = []
    if amplitude_pct < min_amplitude_pct:
        action = 'watch'
        reasons.append(
            f'amplitude below threshold: {amplitude_pct:.2f}% < '
            f'{min_amplitude_pct:.2f}%'
        )
    elif range_position >= high_band and day_pct > 0:
        action = 'sell_t_candidate'
        reasons.append(
            f'near intraday high: range_position={range_position:.3f} '
            f'>= {high_band:.2f}'
        )
        reasons.append('only sell T against an existing base position')
    elif range_position <= low_band:
        action = 'buy_t_candidate'
        reasons.append(
            f'near intraday low: range_position={range_position:.3f} '
            f'<= {low_band:.2f}'
        )
        reasons.append('buy-back signal needs size control and stop loss')
    else:
        action = 'watch'
        reasons.append('price is mid-range; wait for high/low edge')

    edge_score = max(range_position, 1.0 - range_position) * 20.0
    score = int(round(max(0.0, min(100.0, amplitude_pct * 25.0 + edge_score))))
    return {
        'code': code,
        'name': name,
        'action': action,
        'score': score,
        'metrics': {
            'bar_count': len(clean),
            'amplitude_pct': _round(amplitude_pct),
            'range_position': _round(range_position),
            'day_pct': _round(day_pct),
            'last_price': _round(last_price, 4),
            'high': _round(high, 4),
            'low': _round(low, 4),
            'volume': volume,
        },
        'reasons': reasons,
    }


def score_snapshot(
    snapshot: dict[str, Any],
    *,
    min_amplitude_pct: float = 3.0,
    low_band: float = 0.25,
    high_band: float = 0.82,
) -> dict[str, Any]:
    """Fallback scorer from current snapshot when minute bars are unavailable."""
    code = str(snapshot.get('code') or '')
    name = str(snapshot.get('name') or '')
    price = _bar_float(snapshot, 'price', 'last')
    last_close = _bar_float(snapshot, 'lastClose', 'preClose', 'prev_close')
    high = _bar_float(snapshot, 'high')
    low = _bar_float(snapshot, 'low')
    volume = _bar_float(snapshot, 'vol', 'volume') or 0.0
    if price is None or last_close is None or high is None or low is None:
        out = _invalid(code, 0, 'snapshot price/lastClose/high/low required')
        out['name'] = name
        return out
    return score_minute_bars(
        code,
        [{'close': price, 'high': high, 'low': low, 'vol': volume}],
        last_close=last_close,
        name=name,
        min_amplitude_pct=min_amplitude_pct,
        low_band=low_band,
        high_band=high_band,
    )
