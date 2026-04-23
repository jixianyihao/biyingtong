"""Minimum-viable GLM connectivity test.

Sends ONE request with ONE tool and prints:
  - HTTP response time
  - whether GLM returned text vs tool_use
  - the exact content GLM produced

No infrastructure, no caching, no agents. Just: does GLM-5-Turbo at
open.bigmodel.cn/api/anthropic actually accept tools and respond usefully?
"""
from __future__ import annotations

import json
import os
import sys
import time


def main():
    token = os.environ.get('ANTHROPIC_AUTH_TOKEN')
    base_url = os.environ.get('ANTHROPIC_BASE_URL')
    if not (token and base_url):
        print('ERROR: set ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL', file=sys.stderr)
        sys.exit(2)

    import anthropic
    client = anthropic.Anthropic(auth_token=token, base_url=base_url)

    t0 = time.time()
    resp = client.messages.create(
        model='glm-5-turbo',
        max_tokens=1024,
        temperature=0.0,
        system='You are a helpful assistant. Use the provided tool when needed.',
        messages=[
            {'role': 'user', 'content': '现在是 2025 年 11 月 17 日。请调用 get_stock_price 查一下 600519.SH 当天的收盘价，然后用一句话回答。'},
        ],
        tools=[{
            'name': 'get_stock_price',
            'description': 'Fetch closing price of a stock on a given date.',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'code': {'type': 'string'},
                    'date': {'type': 'string'},
                },
                'required': ['code', 'date'],
            },
        }],
    )
    t1 = time.time()

    print(f'wall time: {t1 - t0:.2f}s')
    print(f'stop_reason: {resp.stop_reason}')
    print(f'usage: in={resp.usage.input_tokens} out={resp.usage.output_tokens}')
    print(f'content blocks: {len(resp.content)}')
    for i, block in enumerate(resp.content):
        btype = getattr(block, 'type', '?')
        print(f'  [{i}] type={btype}')
        if btype == 'text':
            print(f'      text: {block.text[:200]}')
        elif btype == 'tool_use':
            print(f'      tool: {block.name}')
            print(f'      input: {json.dumps(block.input, ensure_ascii=False)}')


if __name__ == '__main__':
    main()
