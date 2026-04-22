def test_mock_simple_text_reply():
    from llm.mock import MockLLM
    from llm.base import Message

    mock = MockLLM(scripted=[
        {'text': 'Hello', 'tool_calls': [], 'stop_reason': 'end_turn'},
    ])
    resp = mock.chat([Message(role='user', content='hi')])

    assert resp.stop_reason == 'end_turn'
    assert resp.messages[0].content == 'Hello'


def test_mock_scripted_tool_call():
    from llm.mock import MockLLM
    from llm.base import Message, ToolSpec

    mock = MockLLM(scripted=[
        {'text': '', 'tool_calls': [{'id': 'c1', 'name': 'get_kline',
                                       'input': {'code': '600519.SH'}}],
         'stop_reason': 'tool_use'},
    ])
    tools = [ToolSpec(name='get_kline', description='K', input_schema={})]
    resp = mock.chat([Message(role='user', content='q')], tools=tools)

    assert resp.stop_reason == 'tool_use'
    assert resp.tool_calls[0].name == 'get_kline'
    assert resp.tool_calls[0].input == {'code': '600519.SH'}


def test_mock_advances_scripted_sequence():
    from llm.mock import MockLLM
    from llm.base import Message

    mock = MockLLM(scripted=[
        {'text': 'first', 'tool_calls': [], 'stop_reason': 'end_turn'},
        {'text': 'second', 'tool_calls': [], 'stop_reason': 'end_turn'},
    ])
    r1 = mock.chat([Message(role='user', content='a')])
    r2 = mock.chat([Message(role='user', content='b')])
    assert r1.messages[0].content == 'first'
    assert r2.messages[0].content == 'second'


def test_mock_raises_when_exhausted():
    from llm.mock import MockLLM
    from llm.base import Message
    import pytest

    mock = MockLLM(scripted=[{'text': 'one', 'tool_calls': [], 'stop_reason': 'end_turn'}])
    mock.chat([Message(role='user', content='a')])
    with pytest.raises(AssertionError, match='exhausted'):
        mock.chat([Message(role='user', content='b')])


def test_mock_records_call_history():
    from llm.mock import MockLLM
    from llm.base import Message, ToolSpec

    mock = MockLLM(scripted=[
        {'text': 'ok', 'tool_calls': [], 'stop_reason': 'end_turn'},
    ])
    tools = [ToolSpec(name='x', description='x', input_schema={})]
    mock.chat([Message(role='user', content='p')], tools=tools,
              cacheable_prefix_len=2, temperature=0.5)

    assert len(mock.calls) == 1
    assert mock.calls[0]['tools'] == tools
    assert mock.calls[0]['cacheable_prefix_len'] == 2
