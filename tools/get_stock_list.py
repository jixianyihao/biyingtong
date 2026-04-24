# tools/get_stock_list.py
"""Dynamic sector stock list — wraps tq.get_stock_list_in_sector.

Replaces the per-persona hand-coded 15-stock pool. An agent that wants a
dynamic universe lists `get_stock_list` in `allowed_tools` and calls it
from its prompt.
"""
from __future__ import annotations

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_stock_list',
    description=(
        '获取指定板块的股票列表（或列出所有板块）。'
        '用于动态构建股池；替代硬编码 default_pool。'
    ),
    input_schema={
        'type': 'object',
        'properties': {
            'sector': {
                'type': 'string',
                'description': '板块名称，如 "白酒"、"新能源"。留空时须设 list_sectors=true。',
            },
            'list_sectors': {
                'type': 'boolean',
                'description': '若 true，返回所有板块名称列表而不是板块内股票。',
            },
        },
    },
)


def _is_valid_code(code) -> bool:
    return (
        isinstance(code, str)
        and (code.endswith('.SH') or code.endswith('.SZ'))
        and len(code) >= 9
    )


def call(payload: dict) -> dict:
    from tdx_service import tdx

    if payload.get('list_sectors'):
        sectors = tdx.get_sector_list()
        return {'sectors': list(sectors)}

    sector = payload.get('sector')
    if not sector:
        return {'error': 'sector is required (or set list_sectors=true)'}

    raw = tdx.get_stock_list_in_sector(sector)
    codes = [c for c in (raw or []) if _is_valid_code(c)]
    return {
        'sector': sector,
        'codes': codes,
        'count': len(codes),
    }
