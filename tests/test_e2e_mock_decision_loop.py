"""End-to-end: MockLLM drives a tool_use loop calling real tools through storage.

Proves:
1. filter_allowed whitelist enforcement works
2. Tool dispatch + tool_result feeding
3. place_decision terminates the loop
4. Unauthorized tool calls return errors but don't crash the loop
"""
import json


def run_decision_loop(llm, allowed_tools, user_prompt, max_iters=5):
    """Minimal agent decision loop (prototype for P2's strategy layer)."""
    from llm.base import Message
    from tools import filter_allowed

    registry = filter_allowed(allowed_tools)
    tool_specs = [spec for (spec, _) in registry.values()]

    messages: list[Message] = [Message(role='user', content=user_prompt)]
    decision = None

    for i in range(max_iters):
        resp = llm.chat(messages, tools=tool_specs)
        for m in resp.messages:
            messages.append(m)

        if not resp.tool_calls:
            break

        for tc in resp.tool_calls:
            if tc.name not in registry:
                result = {'error': f'tool {tc.name} not allowed'}
            else:
                _spec, call_fn = registry[tc.name]
                try:
                    result = call_fn(tc.input)
                except Exception as e:  # noqa: BLE001
                    result = {'error': str(e)}

            if tc.name == 'place_decision' and result.get('_terminator'):
                return result, i + 1

            messages.append(Message(
                role='tool',
                content=json.dumps(result, default=str),
                tool_call_id=tc.id,
            ))

        if decision is not None:
            break

    return decision, max_iters


def test_agent_calls_kline_then_holds(vnpy_configured):
    from llm.mock import MockLLM

    mock = MockLLM(scripted=[
        {
            'text': '',
            'tool_calls': [{'id': 'c1', 'name': 'get_kline',
                             'input': {'code': '600519.SH', 'period': '1d', 'count': 20}}],
            'stop_reason': 'tool_use',
        },
        {
            'text': '',
            'tool_calls': [{'id': 'c2', 'name': 'place_decision',
                             'input': {
                                 'action': 'hold',
                                 'reason': 'Insufficient conviction to enter on 20-day trend',
                                 'thinking': '茅台 consolidating near highs.',
                             }}],
            'stop_reason': 'tool_use',
        },
    ])

    decision, iters = run_decision_loop(
        mock, allowed_tools=['get_kline'],
        user_prompt='Decide today for 600519.SH', max_iters=5,
    )
    assert decision['action'] == 'hold'
    assert iters == 2
    assert mock.calls[1]['messages'][-1].role == 'tool'


def test_unauthorized_tool_rejected_but_loop_continues(vnpy_configured):
    from llm.mock import MockLLM

    mock = MockLLM(scripted=[
        {
            'text': '',
            'tool_calls': [{'id': 'c1', 'name': 'place_order',
                             'input': {'code': '600519.SH', 'side': 'buy', 'qty': 100}}],
            'stop_reason': 'tool_use',
        },
        {
            'text': '',
            'tool_calls': [{'id': 'c2', 'name': 'place_decision',
                             'input': {
                                 'action': 'hold',
                                 'reason': 'Tool authorization denied; fallback to hold',
                                 'thinking': '.',
                             }}],
            'stop_reason': 'tool_use',
        },
    ])

    decision, _ = run_decision_loop(
        mock, allowed_tools=['get_kline'], user_prompt='x', max_iters=5,
    )
    assert decision['action'] == 'hold'
    tool_result_msg = mock.calls[1]['messages'][-1]
    assert 'not allowed' in tool_result_msg.content


def test_place_decision_always_available():
    from llm.mock import MockLLM

    mock = MockLLM(scripted=[
        {
            'text': '',
            'tool_calls': [{'id': 'c1', 'name': 'place_decision',
                             'input': {
                                 'action': 'hold',
                                 'reason': 'No tools; defaulting to hold for today',
                                 'thinking': '.',
                             }}],
            'stop_reason': 'tool_use',
        },
    ])

    decision, iters = run_decision_loop(
        mock, allowed_tools=[], user_prompt='hi', max_iters=3,
    )
    assert decision['action'] == 'hold'
    assert iters == 1


def test_max_iters_respected():
    from llm.mock import MockLLM

    loops = [
        {
            'text': '',
            'tool_calls': [{'id': f'c{i}', 'name': 'get_kline',
                             'input': {'code': '600519.SH', 'period': '1d', 'count': 5}}],
            'stop_reason': 'tool_use',
        }
        for i in range(10)
    ]
    mock = MockLLM(scripted=loops)

    decision, iters = run_decision_loop(
        mock, allowed_tools=['get_kline'], user_prompt='go', max_iters=3,
    )
    assert decision is None
    assert iters == 3
