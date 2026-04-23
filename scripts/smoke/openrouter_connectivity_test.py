"""OpenRouter + Hunyuan connectivity + tool-use test."""
from __future__ import annotations

import json
import os
import sys
import time


def main():
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        print('ERROR: set OPENROUTER_API_KEY', file=sys.stderr)
        sys.exit(2)

    from openai import OpenAI
    client = OpenAI(base_url='https://openrouter.ai/api/v1', api_key=key)

    t0 = time.time()
    resp = client.chat.completions.create(
        model='tencent/hy3-preview:free',
        messages=[
            {'role': 'system', 'content': 'You are a helpful assistant. Use the provided tool when needed.'},
            {'role': 'user', 'content': '现在是 2025 年 11 月 17 日。请调用 get_stock_price 查一下 600519.SH 当天的收盘价，然后用一句话回答。'},
        ],
        tools=[{
            'type': 'function',
            'function': {
                'name': 'get_stock_price',
                'description': 'Fetch closing price of a stock on a given date.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'code': {'type': 'string'},
                        'date': {'type': 'string'},
                    },
                    'required': ['code', 'date'],
                },
            },
        }],
        extra_body={
            'provider': {'sort': 'throughput'},
            'reasoning': {'enabled': True},
        },
    )
    t1 = time.time()

    print(f'wall time: {t1 - t0:.2f}s')
    choice = resp.choices[0]
    msg = choice.message
    print(f'finish_reason: {choice.finish_reason}')
    if resp.usage:
        print(f'usage: prompt={resp.usage.prompt_tokens} completion={resp.usage.completion_tokens}')
    if msg.content:
        print(f'text: {msg.content[:300]}')
    if msg.tool_calls:
        for tc in msg.tool_calls:
            print(f'tool: {tc.function.name}')
            print(f'args: {tc.function.arguments}')
    else:
        print('(no tool calls)')


if __name__ == '__main__':
    main()
