"""ClaudeLLM — Anthropic translation + prompt caching."""
from unittest.mock import MagicMock


def _fake_resp(text='ok', tool_use=None, stop='end_turn',
               in_tok=10, out_tok=5, cache_read=0, cache_write=0):
    from types import SimpleNamespace
    blocks = []
    if text:
        blocks.append(SimpleNamespace(type='text', text=text))
    if tool_use:
        blocks.append(SimpleNamespace(
            type='tool_use', id=tool_use['id'], name=tool_use['name'],
            input=tool_use['input'],
        ))
    return SimpleNamespace(
        content=blocks, stop_reason=stop,
        usage=SimpleNamespace(
            input_tokens=in_tok, output_tokens=out_tok,
            cache_read_input_tokens=cache_read, cache_creation_input_tokens=cache_write,
        ),
    )


def test_claude_simple_chat(monkeypatch):
    from llm import claude
    from llm.base import Message

    fake = MagicMock()
    fake.messages.create.return_value = _fake_resp(text='hello')
    monkeypatch.setattr(claude, '_get_client', lambda **kwargs: fake)

    llm = claude.ClaudeLLM(model_id='claude-opus-4-7', api_key='sk-test')
    resp = llm.chat([Message(role='user', content='hi')])

    assert resp.messages[0].content == 'hello'
    assert fake.messages.create.call_args.kwargs['model'] == 'claude-opus-4-7'


def test_claude_system_message_separated(monkeypatch):
    from llm import claude
    from llm.base import Message

    fake = MagicMock()
    fake.messages.create.return_value = _fake_resp()
    monkeypatch.setattr(claude, '_get_client', lambda **kwargs: fake)

    llm = claude.ClaudeLLM(model_id='claude-opus-4-7', api_key='sk-test')
    llm.chat([
        Message(role='system', content='You are X'),
        Message(role='user', content='hi'),
    ])

    kw = fake.messages.create.call_args.kwargs
    sys_val = kw['system']
    # Could be string or list depending on caching (cacheable_prefix_len=0 here)
    assert 'You are X' in (sys_val if isinstance(sys_val, str) else sys_val[0]['text'])
    assert len(kw['messages']) == 1


def test_claude_tool_use_response(monkeypatch):
    from llm import claude
    from llm.base import Message, ToolSpec

    fake = MagicMock()
    fake.messages.create.return_value = _fake_resp(
        text='', tool_use={'id': 't1', 'name': 'get_kline',
                           'input': {'code': '600519.SH'}}, stop='tool_use',
    )
    monkeypatch.setattr(claude, '_get_client', lambda **kwargs: fake)

    llm = claude.ClaudeLLM(model_id='claude-opus-4-7', api_key='sk-test')
    tools = [ToolSpec(name='get_kline', description='K', input_schema={})]
    resp = llm.chat([Message(role='user', content='q')], tools=tools)

    assert resp.stop_reason == 'tool_use'
    assert resp.tool_calls[0].name == 'get_kline'


def test_claude_cacheable_prefix_adds_cache_control(monkeypatch):
    from llm import claude
    from llm.base import Message, ToolSpec

    fake = MagicMock()
    fake.messages.create.return_value = _fake_resp()
    monkeypatch.setattr(claude, '_get_client', lambda **kwargs: fake)

    llm = claude.ClaudeLLM(model_id='claude-opus-4-7', api_key='sk-test')
    tools = [ToolSpec(name='x', description='x', input_schema={})]
    llm.chat(
        [Message(role='system', content='big prompt'),
         Message(role='user', content='hi')],
        tools=tools, cacheable_prefix_len=1,
    )

    kw = fake.messages.create.call_args.kwargs
    sys_val = kw['system']
    assert isinstance(sys_val, list)
    assert sys_val[-1].get('cache_control', {}).get('type') == 'ephemeral'
    assert kw['tools'][-1].get('cache_control', {}).get('type') == 'ephemeral'


def test_claude_usage_records_cache_tokens(monkeypatch):
    from llm import claude
    from llm.base import Message

    fake = MagicMock()
    fake.messages.create.return_value = _fake_resp(
        in_tok=50, out_tok=10, cache_read=200, cache_write=80,
    )
    monkeypatch.setattr(claude, '_get_client', lambda **kwargs: fake)

    llm = claude.ClaudeLLM(model_id='claude-opus-4-7', api_key='sk-test')
    resp = llm.chat([Message(role='user', content='hi')])

    assert resp.usage.cached_read_tokens == 200
    assert resp.usage.cached_write_tokens == 80


def test_claude_api_error_raises_llm_error(monkeypatch):
    from llm import claude
    from llm.base import LLMError, Message
    import pytest

    fake = MagicMock()
    fake.messages.create.side_effect = RuntimeError('429 rate limited')
    monkeypatch.setattr(claude, '_get_client', lambda **kwargs: fake)

    llm = claude.ClaudeLLM(model_id='claude-opus-4-7', api_key='sk-test')
    with pytest.raises(LLMError) as exc:
        llm.chat([Message(role='user', content='hi')])
    assert exc.value.provider == 'anthropic'
    assert exc.value.retryable is True
