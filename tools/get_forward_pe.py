# tools/get_forward_pe.py
"""Forward PE — wraps tq.get_gp_one_data for consensus PE fields.

Returns the 3-year forward PE curve (current year T, T+1, T+2) as analyst
consensus. Primary consumer is the value-investor persona (buffet / linyuan)
whose prompts reference forward valuation but had no dedicated data source.

TDX field map:
  GO23 = 一致预期 T 年 PE
  GO24 = 一致预期 T+1 年 PE
  GO25 = 一致预期 T+2 年 PE
"""
from __future__ import annotations

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_forward_pe',
    description=(
        '取股票的一致预期 Forward PE (T/T+1/T+2)。'
        '用于价值派 agent 的前瞻估值。'
    ),
    input_schema={
        'type': 'object',
        'properties': {
            'code': {
                'type': 'string',
                'description': '股票代码，如 "600519.SH"',
            },
        },
        'required': ['code'],
    },
)


def _to_float(value):
    """Coerce tq response (string or numeric) to float; return None on failure."""
    if value is None:
        return None
    try:
        s = str(value).strip()
        if not s:
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def call(payload: dict) -> dict:
    from tdx_service import tdx

    code = payload.get('code')
    if not code:
        return {'error': 'code is required'}

    raw = tdx.get_gp_one_data([code], ['GO23', 'GO24', 'GO25']) or {}
    fields = raw.get(code) or {}

    return {
        'code': code,
        'pe_t': _to_float(fields.get('GO23')),
        'pe_t1': _to_float(fields.get('GO24')),
        'pe_t2': _to_float(fields.get('GO25')),
    }
