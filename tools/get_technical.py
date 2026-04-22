"""get_technical — compute MA/MACD/RSI/BOLL from storage.kline() closes."""
from __future__ import annotations

import math

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_technical',
    description='Compute technical indicator (MA/MACD/RSI/BOLL).',
    input_schema={
        'type': 'object',
        'properties': {
            'code': {'type': 'string'},
            'indicator': {'type': 'string', 'enum': ['MA', 'MACD', 'RSI', 'BOLL']},
            'period': {'type': 'integer', 'minimum': 1,
                       'description': 'MA/RSI window. Default: MA=20, RSI=14.'},
        },
        'required': ['code', 'indicator'],
    },
)


def _get_closes(code: str) -> list[float]:
    from storage import kline
    return kline().get_closes(code, 200)


def _ma(closes, period):
    out = []
    for i in range(len(closes)):
        if i + 1 < period:
            out.append(float('nan'))
        else:
            out.append(round(sum(closes[i + 1 - period: i + 1]) / period, 2))
    return out


def _ema(closes, period):
    if not closes:
        return []
    alpha = 2 / (period + 1)
    out = [closes[0]]
    for i in range(1, len(closes)):
        out.append(alpha * closes[i] + (1 - alpha) * out[-1])
    return [round(v, 4) for v in out]


def _macd(closes):
    e12 = _ema(closes, 12)
    e26 = _ema(closes, 26)
    dif = [a - b for a, b in zip(e12, e26)]
    dea = _ema(dif, 9)
    bar = [2 * (d - e) for d, e in zip(dif, dea)]
    return {
        'dif': [round(v, 4) for v in dif],
        'dea': [round(v, 4) for v in dea],
        'bar': [round(v, 4) for v in bar],
    }


def _rsi(closes, period=14):
    if len(closes) < period + 1:
        return [50.0] * len(closes)
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    out = [float('nan')] * (period + 1)
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        rs = avg_g / avg_l if avg_l > 0 else 100
        out.append(round(100 - 100 / (1 + rs), 2))
    while len(out) < len(closes):
        out.append(out[-1])
    return out[: len(closes)]


def _boll(closes, period=20, k=2.0):
    mid = _ma(closes, period)
    up, lo = [], []
    for i in range(len(closes)):
        if i + 1 < period or mid[i] != mid[i]:
            up.append(float('nan'))
            lo.append(float('nan'))
        else:
            w = closes[i + 1 - period: i + 1]
            mean = mid[i]
            var = sum((x - mean) ** 2 for x in w) / period
            sd = math.sqrt(var)
            up.append(round(mean + k * sd, 2))
            lo.append(round(mean - k * sd, 2))
    return {'upper': up, 'middle': mid, 'lower': lo}


def call(input: dict) -> dict:
    code = input.get('code', '')
    ind = input.get('indicator', '').upper()

    closes = _get_closes(code)
    if not closes:
        return {'code': code, 'indicator': ind, 'error': 'no K-line data'}

    if ind == 'MA':
        p = int(input.get('period', 20))
        return {'code': code, 'indicator': 'MA', 'period': p,
                'values': _ma(closes, p)}
    if ind == 'MACD':
        return {'code': code, 'indicator': 'MACD', **_macd(closes)}
    if ind == 'RSI':
        p = int(input.get('period', 14))
        return {'code': code, 'indicator': 'RSI', 'period': p,
                'values': _rsi(closes, p)}
    if ind == 'BOLL':
        p = int(input.get('period', 20))
        return {'code': code, 'indicator': 'BOLL', 'period': p, **_boll(closes, p)}

    raise ValueError(f'unknown indicator: {ind}')
