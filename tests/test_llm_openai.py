"""OpenAILLM — handles OpenAI and any OpenAI-compatible provider (DeepSeek)."""
from unittest.mock import MagicMock


def _fake(content='ok', tool_calls=None, finish='stop', in_tok=10, out_tok=5, cached=0):
    from types import SimpleNamespace
    tc_list = []
    if tool_calls:
        for t in tool_calls:
            tc_list.append(SimpleNamespace(
                id=t['id'], type='function',
                function=SimpleNamespace(name=t['name'], arguments=t['arguments_json']),
            ))
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(
                role='assistant',
                content=content if content else None,
                tool_calls=tc_list or None,
            ),
            finish_reason=finish,
        )],
        usage=SimpleNamespace(
            prompt_tokens=in_tok, completion_tokens=out_tok,
            prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
        ),
    )


def test_openai_simple_chat(monkeypatch):
    from llm import openai_adapter as oa
    from llm.base import Message

    fake = MagicMock()
    fake.chat.completions.create.return_value = _fake(content='hi')
    monkeypatch.setattr(oa, '_get_client', lambda **kw: fake)

    llm = oa.OpenAILLM(model_id='gpt-4o', api_key='sk-test')
    resp = llm.chat([Message(role='user', content='q')])

    assert resp.messages[0].content == 'hi'
    assert resp.stop_reason == 'end_turn'


def test_openai_translates_tools(monkeypatch):
    from llm import openai_adapter as oa
    from llm.base import Message, ToolSpec

    fake = MagicMock()
    fake.chat.completions.create.return_value = _fake()
    monkeypatch.setattr(oa, '_get_client', lambda **kw: fake)

    llm = oa.OpenAILLM(model_id='gpt-4o', api_key='sk-test')
    tools = [ToolSpec(name='get_kline', description='K',
                      input_schema={'type': 'object'})]
    llm.chat([Message(role='user', content='q')], tools=tools)

    sent = fake.chat.completions.create.call_args.kwargs['tools']
    assert sent[0]['type'] == 'function'
    assert sent[0]['function']['name'] == 'get_kline'


def test_openai_parses_tool_calls(monkeypatch):
    from llm import openai_adapter as oa
    from llm.base import Message

    fake = MagicMock()
    fake.chat.completions.create.return_value = _fake(
        content='', finish='tool_calls',
        tool_calls=[{'id': 'c1', 'name': 'get_kline',
                     'arguments_json': '{"code": "600519.SH"}'}],
    )
    monkeypatch.setattr(oa, '_get_client', lambda **kw: fake)

    llm = oa.OpenAILLM(model_id='gpt-4o', api_key='sk-test')
    resp = llm.chat([Message(role='user', content='q')])

    assert resp.stop_reason == 'tool_use'
    assert resp.tool_calls[0].input == {'code': '600519.SH'}


def test_deepseek_uses_base_url(monkeypatch):
    from llm import openai_adapter as oa
    from llm.base import Message

    captured = {}
    def _capture(**kw):
        captured.update(kw)
        fake = MagicMock()
        fake.chat.completions.create.return_value = _fake(content='ok')
        return fake
    monkeypatch.setattr(oa, '_get_client', _capture)

    llm = oa.OpenAILLM(
        model_id='deepseek-chat', api_key='sk-ds',
        base_url='https://api.deepseek.com/v1',
        provider='deepseek',
    )
    llm.chat([Message(role='user', content='hi')])
    assert captured.get('base_url') == 'https://api.deepseek.com/v1'


def test_openai_maps_cached_tokens(monkeypatch):
    from llm import openai_adapter as oa
    from llm.base import Message

    fake = MagicMock()
    fake.chat.completions.create.return_value = _fake(in_tok=100, cached=50)
    monkeypatch.setattr(oa, '_get_client', lambda **kw: fake)

    llm = oa.OpenAILLM(model_id='gpt-4o', api_key='sk-test')
    resp = llm.chat([Message(role='user', content='hi')])
    assert resp.usage.cached_read_tokens == 50
