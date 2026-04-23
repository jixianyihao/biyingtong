"""Assemble LLM messages for an agent decision point + hash utility."""
from __future__ import annotations

import hashlib
import json

from llm.base import Message


def build_messages(
    *,
    system_prompt: str,
    date: str,
    portfolio: dict,
    market_context: dict,
    default_pool: list[str],
    market_snapshot: dict | None = None,
) -> list[Message]:
    """Return [system Message, user Message]."""
    cash = portfolio.get('cash', 0)
    equity = portfolio.get('equity', 0)
    positions = portfolio.get('positions', {})

    lines = [f'决策日期：{date}']
    lines.append(f'组合：现金 {cash:.0f}，总资产 {equity:.0f}')
    if positions:
        lines.append('当前持仓：')
        for code, info in positions.items():
            lines.append(
                f'  - {code} × {info.get("shares", 0)} 股（均价 '
                f'{info.get("avg_price", 0):.2f}）'
            )
    else:
        lines.append('当前无持仓。')
    lines.append(f'备选池：{", ".join(default_pool)}')
    if market_context:
        lines.append('市场快照：')
        for k, v in market_context.items():
            lines.append(f'  - {k}: {v}')
    if market_snapshot and market_snapshot.get('stocks'):
        lines.append('')
        lines.append('研究数据:')
        for code, data in market_snapshot['stocks'].items():
            lines.append(f'  {code}:')
            ks = data.get('kline_summary')
            if ks:
                lines.append(
                    f'    K线: latest={ks.get("latest_close")}, '
                    f'30d_return={ks.get("return_30d_pct")}%, '
                    f'vol={ks.get("volatility_30d_pct")}%'
                )
            fin = data.get('financials')
            if fin:
                fin_str = ', '.join(f'{k}={v}' for k, v in fin.items())
                lines.append(f'    财务: {fin_str}')
            tech = data.get('technical')
            if tech:
                tech_str = ', '.join(f'{k}={v}' for k, v in tech.items())
                lines.append(f'    技术: {tech_str}')
    lines.append('')
    lines.append(
        '使用工具调研后调用 place_decision 给出当日决策（'
        'buy / sell / hold 三选一，含理由与完整思考）。'
    )
    user_msg = '\n'.join(lines)
    return [
        Message(role='system', content=system_prompt),
        Message(role='user', content=user_msg),
    ]


def prompt_hash(messages: list[Message]) -> str:
    payload = json.dumps(
        [{'role': m.role, 'content': m.content} for m in messages],
        ensure_ascii=False, sort_keys=True,
    ).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()[:16]
