"""get_technical — compute MA/MACD/RSI/BOLL via talib (C-implemented, battle-tested).

Previous hand-rolled math (MA/EMA/RSI/BOLL) had well-known pitfalls:
- Wilder RSI smoothing seed
- MACD EMA initialization
- BOLL sample vs population stddev
This version delegates to talib 0.6.8 which is the industry standard.
"""
from __future__ import annotations

import math

import numpy as np
import talib

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_technical',
    description='Compute technical indicator (MA/MACD/RSI/BOLL) via talib.',
    input_schema={
        'type': 'object',
        'properties': {
            'code': {'type': 'string'},
            'indicator': {'type': 'string',
                          'enum': ['MA', 'MACD', 'RSI', 'BOLL']},
            'period': {'type': 'integer', 'minimum': 1,
                       'description': 'MA/RSI window. Default: MA=20, RSI=14.'},
        },
        'required': ['code', 'indicator'],
    },
)


def _get_closes(code: str) -> list[float]:
    from storage import kline
    return kline().get_closes(code, 200)


def _to_list(arr: np.ndarray, digits: int) -> list:
    """Convert numpy array with NaN padding -> python list, rounding non-NaN."""
    out = []
    for v in arr:
        f = float(v)
        if math.isnan(f):
            out.append(float('nan'))
        else:
            out.append(round(f, digits))
    return out


def call(input: dict) -> dict:
    code = input.get('code', '')
    ind = input.get('indicator', '').upper()

    closes_raw = _get_closes(code)
    if not closes_raw:
        return {'code': code, 'indicator': ind, 'error': 'no K-line data'}

    closes = np.asarray(closes_raw, dtype=np.float64)

    if ind == 'MA':
        p = int(input.get('period', 20))
        # talib.SMA: same-length output, first (p-1) entries are NaN
        values = talib.SMA(closes, timeperiod=p)
        return {'code': code, 'indicator': 'MA', 'period': p,
                'values': _to_list(values, 2)}

    if ind == 'MACD':
        # talib.MACD returns (macd, signal, hist) each len == len(closes)
        # macd  ~ existing dif
        # signal ~ existing dea
        # hist   ~ existing bar / 2  (talib uses hist = macd - signal;
        #                             old code doubled it: bar = 2*(dif-dea))
        macd_line, signal_line, hist = talib.MACD(
            closes, fastperiod=12, slowperiod=26, signalperiod=9)
        return {
            'code': code, 'indicator': 'MACD',
            'dif': _to_list(macd_line, 4),
            'dea': _to_list(signal_line, 4),
            # Preserve the previous convention bar = 2*(dif-dea)
            'bar': _to_list(hist * 2, 4),
        }

    if ind == 'RSI':
        p = int(input.get('period', 14))
        values = talib.RSI(closes, timeperiod=p)
        return {'code': code, 'indicator': 'RSI', 'period': p,
                'values': _to_list(values, 2)}

    if ind == 'BOLL':
        p = int(input.get('period', 20))
        upper, middle, lower = talib.BBANDS(
            closes, timeperiod=p, nbdevup=2.0, nbdevdn=2.0, matype=0)
        return {
            'code': code, 'indicator': 'BOLL', 'period': p,
            'upper': _to_list(upper, 2),
            'middle': _to_list(middle, 2),
            'lower': _to_list(lower, 2),
        }

    raise ValueError(f'unknown indicator: {ind}')
