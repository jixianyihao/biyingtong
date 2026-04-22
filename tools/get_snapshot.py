"""get_snapshot — live five-level quote via tdx_service."""
from __future__ import annotations

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_snapshot',
    description='Get real-time snapshot (price + 5-level depth). Live only.',
    input_schema={
        'type': 'object',
        'properties': {
            'code': {'type': 'string'},
        },
        'required': ['code'],
    },
)


def _normalize(code: str) -> str:
    if '.' in code:
        return code
    if code.startswith(('6', '9')):
        return f'{code}.SH'
    return f'{code}.SZ'


def call(input: dict) -> dict:
    code = _normalize(input.get('code', ''))
    from tdx_service import tdx
    tdx.ensure_connected()
    s = tdx.get_snapshot(code)
    if not s:
        return {'code': code, 'error': 'snapshot unavailable'}

    out = {
        'code': s.get('code'), 'name': s.get('name'),
        'price': s.get('price'), 'chg': s.get('chg'), 'pct': s.get('pct'),
        'open': s.get('open'), 'high': s.get('high'), 'low': s.get('low'),
        'vol': s.get('vol'), 'amount': s.get('amount'),
    }
    for i in range(1, 6):
        out[f'bid{i}'] = s.get(f'bid{i}')
        out[f'bidVol{i}'] = s.get(f'bidVol{i}')
        out[f'ask{i}'] = s.get(f'ask{i}')
        out[f'askVol{i}'] = s.get(f'askVol{i}')
    return out
