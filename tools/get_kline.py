"""get_kline — read K-line from storage.kline()."""
from __future__ import annotations

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_kline',
    description='Get historical K-line (OHLCV) for a stock from local cache.',
    input_schema={
        'type': 'object',
        'properties': {
            'code': {'type': 'string',
                     'description': "股票代码, e.g. '600519.SH' or '600519'."},
            'period': {'type': 'string', 'enum': ['1d', '1w', '1M']},
            'count': {'type': 'integer', 'minimum': 1, 'maximum': 500},
        },
        'required': ['code', 'period', 'count'],
    },
)


_VALID = {'1d', '1w', '1M'}


def call(input: dict) -> dict:
    code = input.get('code', '')
    period = input.get('period', '1d')
    count = int(input.get('count', 30))

    if period not in _VALID:
        raise ValueError(f"period must be one of {_VALID}, got {period!r}")

    from storage import kline
    bars = kline().get_recent(code, period, count)

    return {
        'code': code,
        'period': period,
        'bars': [
            {
                'date': b.datetime.strftime('%Y-%m-%d'),
                'open': round(b.open_price, 2),
                'high': round(b.high_price, 2),
                'low': round(b.low_price, 2),
                'close': round(b.close_price, 2),
                'volume': int(b.volume),
            }
            for b in bars
        ],
    }
