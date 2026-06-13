from __future__ import annotations

from collections import defaultdict
from math import sqrt
from statistics import mean
from typing import Any


def _float(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _date(row: dict[str, Any]) -> str:
    return str(row.get('date') or row.get('ts') or '')[:10]


def _pct(numerator: float, denominator: float) -> float:
    return numerator / denominator * 100.0 if denominator else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    return sqrt(sum((v - avg) ** 2 for v in values) / len(values))


def summarize_intraday_features(
    code: str,
    bars: list[dict[str, Any]],
) -> dict[str, Any]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bar in bars:
        day = _date(bar)
        if day:
            by_day[day].append(bar)

    ranges: list[float] = []
    amplitudes: list[float] = []
    opening_ranges: list[float] = []
    reversals: list[float] = []
    volumes: list[float] = []
    vwap_devs: list[float] = []

    for day_rows in by_day.values():
        if not day_rows:
            continue
        first = day_rows[0]
        last = day_rows[-1]
        day_high = max(_float(row, 'high') for row in day_rows)
        day_low = min(_float(row, 'low') for row in day_rows)
        first_close = _float(first, 'close')
        last_close = _float(last, 'close')
        ranges.append(_pct(day_high - day_low, first_close))
        amplitudes.append(_pct(day_high - day_low, day_low))
        opening_slice = day_rows[: min(30, len(day_rows))]
        opening_high = max(_float(row, 'high') for row in opening_slice)
        opening_low = min(_float(row, 'low') for row in opening_slice)
        opening_ranges.append(_pct(opening_high - opening_low, first_close))
        reversals.append(
            abs(last_close - first_close) / max(day_high - day_low, 1e-9),
        )

        cum_money = 0.0
        cum_volume = 0.0
        for row in day_rows:
            close = _float(row, 'close')
            vol = _float(row, 'vol', _float(row, 'volume'))
            volumes.append(vol)
            cum_money += close * vol
            cum_volume += vol
            vwap = cum_money / cum_volume if cum_volume else close
            vwap_devs.append(_pct(close - vwap, vwap))

    dev_std = _std(vwap_devs)
    tail_count = sum(
        1 for value in vwap_devs
        if dev_std > 0 and abs(value) / dev_std >= 1.5
    )
    vol_avg = mean(volumes) if volumes else 0.0
    vol_cv = _std(volumes) / vol_avg if vol_avg else 0.0
    closes = [_float(row, 'close') for row in bars]
    trend = _pct(closes[-1] - closes[0], closes[0]) if len(closes) >= 2 else 0.0

    return {
        'code': code,
        'days': len(by_day),
        'bar_count': len(bars),
        'avg_amplitude_pct': round(mean(amplitudes), 4) if amplitudes else 0.0,
        'avg_intraday_range_pct': round(mean(ranges), 4) if ranges else 0.0,
        'vwap_deviation_mean_pct': (
            round(mean(vwap_devs), 4) if vwap_devs else 0.0
        ),
        'vwap_deviation_std_pct': round(dev_std, 4),
        'vwap_zscore_tail_count': tail_count,
        'opening_range_pct': (
            round(mean(opening_ranges), 4) if opening_ranges else 0.0
        ),
        'opening_gap_pct': 0.0,
        'volume_cv': round(vol_cv, 4),
        'trend_slope': round(trend, 4),
        'reversal_score': round(mean(reversals), 4) if reversals else 0.0,
    }
