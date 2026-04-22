"""get_index — market index snapshot via tdx_service."""
from __future__ import annotations

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_index',
    description='Get current snapshot of a market index.',
    input_schema={
        'type': 'object',
        'properties': {
            'index_code': {'type': 'string',
                           'description': "'000300.SH' (HS300), '000001.SH' (SSE)"},
        },
        'required': ['index_code'],
    },
)


def call(input: dict) -> dict:
    code = input.get('index_code', '000300.SH')
    from tdx_service import tdx
    tdx.ensure_connected()
    s = tdx.get_snapshot(code)
    if not s:
        return {'code': code, 'error': 'unavailable'}
    return {
        'code': s.get('code'), 'name': s.get('name'),
        'price': s.get('price'), 'chg': s.get('chg'), 'pct': s.get('pct'),
    }
