"""place_decision — terminator tool."""
from __future__ import annotations

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='place_decision',
    description=(
        'Record your final trading decision. Calling this ends the decision loop. '
        'Include action, reason (≥20 chars), and full thinking. For buy/sell also '
        'provide code and qty.'
    ),
    input_schema={
        'type': 'object',
        'properties': {
            'action': {'type': 'string', 'enum': ['buy', 'sell', 'hold']},
            'code': {'type': 'string',
                     'description': '股票代码 (e.g. 600519.SH). Required for buy/sell.'},
            'qty': {'type': 'integer', 'minimum': 0,
                    'description': 'Shares. Buy multiple of 100.'},
            'reason': {'type': 'string', 'minLength': 20, 'maxLength': 500},
            'thinking': {'type': 'string', 'description': 'Full analysis.'},
        },
        'required': ['action', 'reason', 'thinking'],
    },
)


def call(input: dict) -> dict:
    for req in ('action', 'reason', 'thinking'):
        if req not in input:
            raise ValueError(f'Missing required field: {req}')

    action = input['action']
    if action not in ('buy', 'sell', 'hold'):
        raise ValueError(f'Invalid action: {action}')

    reason = input['reason']
    if len(reason) < 20:
        raise ValueError(f'reason must be at least 20 chars, got {len(reason)}')

    return {
        'action': action,
        'code': input.get('code', ''),
        'qty': int(input.get('qty', 0)),
        'reason': reason,
        'thinking': input['thinking'],
        '_terminator': True,
    }
