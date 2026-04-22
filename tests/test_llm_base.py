"""Canonical LLM types + LLMBase abstract."""


def test_message_dataclass():
    from llm.base import Message
    m = Message(role='user', content='hello')
    assert m.role == 'user'
    assert m.content == 'hello'
    assert m.tool_call_id is None


def test_toolspec_dataclass():
    from llm.base import ToolSpec
    t = ToolSpec(name='x', description='d', input_schema={'type': 'object'})
    assert t.name == 'x'


def test_toolcall_dataclass():
    from llm.base import ToolCall
    tc = ToolCall(id='c1', name='get_kline', input={'code': '600519'})
    assert tc.input['code'] == '600519'


def test_usage_dataclass_defaults():
    from llm.base import Usage
    u = Usage(input_tokens=10, output_tokens=3)
    assert u.cached_read_tokens == 0
    assert u.cached_write_tokens == 0


def test_llm_response_composition():
    from llm.base import LLMResponse, Message, Usage
    r = LLMResponse(
        messages=[Message(role='assistant', content='ok')],
        tool_calls=[],
        stop_reason='end_turn',
        usage=Usage(input_tokens=10, output_tokens=2),
    )
    assert r.stop_reason == 'end_turn'


def test_llm_error_has_retryable_flag():
    from llm.base import LLMError
    e = LLMError(provider='anthropic', kind='rate_limit', message='429', retryable=True)
    assert e.retryable is True
    assert str(e) == '429'


def test_llm_base_is_abstract():
    import inspect
    from llm.base import LLMBase
    assert inspect.isabstract(LLMBase)
    import pytest
    with pytest.raises(TypeError):
        LLMBase()
