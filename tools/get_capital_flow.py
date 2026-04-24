# tools/get_capital_flow.py
"""Capital flow — wraps tq.get_gpjy_value (stock) and tq.get_bkjy_value (sector).

Exposes 资金流 / 成交额 / 换手率 for any A-share or sector. Used by
short-term (游资/热点) personas whose prompts mention 资金流入 but previously
had no data source.

Default fields match the typical 游资 decision set.
"""
from __future__ import annotations

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_capital_flow',
    description=(
        '取个股或板块的资金流/成交/换手率数据。'
        '个股传 code (如 "600519.SH")，板块传 sector_code (如 "880660.SH")。'
    ),
    input_schema={
        'type': 'object',
        'properties': {
            'code': {
                'type': 'string',
                'description': '股票代码；与 sector_code 二选一',
            },
            'sector_code': {
                'type': 'string',
                'description': '板块代码（TDX 880xxx.SH/SZ）；与 code 二选一',
            },
            'start_date': {
                'type': 'string',
                'description': 'YYYYMMDD',
            },
            'end_date': {
                'type': 'string',
                'description': 'YYYYMMDD',
            },
            'fields': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': '可选 field 列表。未指定时用默认。',
            },
        },
    },
)

# GP1-GP5 cover 成交量/成交额/换手率/振幅/量比 (approximate — refer to TDX docs GP field map)
_DEFAULT_STOCK_FIELDS = ['GP1', 'GP2', 'GP3', 'GP4', 'GP5']
# BK5-BK9 cover 板块成交额/涨跌家数/资金净流入 (approximate)
_DEFAULT_SECTOR_FIELDS = ['BK5', 'BK6', 'BK7', 'BK8', 'BK9']


def _flatten(raw: dict) -> list[dict]:
    """Flatten tq response {code: {field: [{Date, Value}, ...]}} to [{date, field, value}]."""
    rows: list[dict] = []
    for _code, field_map in (raw or {}).items():
        for field, entries in (field_map or {}).items():
            for entry in (entries or []):
                rows.append({
                    'date': entry.get('Date'),
                    'field': field,
                    'value': entry.get('Value'),
                })
    return rows


def call(payload: dict) -> dict:
    from tdx_service import tdx

    code = payload.get('code')
    sector_code = payload.get('sector_code')
    if not code and not sector_code:
        return {'error': 'code or sector_code is required'}
    start = payload.get('start_date') or ''
    end = payload.get('end_date') or ''

    if code:
        fields = payload.get('fields') or _DEFAULT_STOCK_FIELDS
        raw = tdx.get_gpjy_value([code], fields, start, end)
        return {
            'code': code,
            'start_date': start,
            'end_date': end,
            'rows': _flatten(raw),
        }
    fields = payload.get('fields') or _DEFAULT_SECTOR_FIELDS
    raw = tdx.get_bkjy_value([sector_code], fields, start, end)
    return {
        'sector_code': sector_code,
        'start_date': start,
        'end_date': end,
        'rows': _flatten(raw),
    }
