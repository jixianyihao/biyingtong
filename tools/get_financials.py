"""get_financials — read latest PE/PB/ROE/growth from storage.financial()."""
from __future__ import annotations

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_financials',
    description='Get latest financial metrics (PE, PB, ROE, margins, growth).',
    input_schema={
        'type': 'object',
        'properties': {
            'code': {'type': 'string'},
        },
        'required': ['code'],
    },
)


def call(input: dict) -> dict:
    code = input.get('code', '')
    from storage import financial
    row = financial().get_latest(code)

    if row is None:
        return {'code': code, 'error': 'no financial data'}

    return {
        'code': code,
        'pe': row.get('pe'),
        'pb': row.get('pb'),
        'roe': row.get('roe'),
        'gross_margin': row.get('gross_margin'),
        'revenue_growth': row.get('revenue_growth'),
        'net_profit_growth': row.get('net_profit_growth'),
        'as_of': row.get('date'),
    }
