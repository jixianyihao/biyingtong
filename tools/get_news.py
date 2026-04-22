"""get_news — news items for a stock. MVP stub returning empty list.

Real implementation deferred per Spec § 19 (pending news source decision).
"""
from __future__ import annotations

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_news',
    description='Get recent news items for a stock. MVP stub returns [].',
    input_schema={
        'type': 'object',
        'properties': {
            'code': {'type': 'string'},
            'limit': {'type': 'integer', 'default': 10},
        },
        'required': ['code'],
    },
)


def call(input: dict) -> dict:
    return {
        'code': input.get('code', ''),
        'news': [],
        '_note': 'P1 stub; news source TBD per Spec § 19',
    }
