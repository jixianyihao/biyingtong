"""GeminiLLM — google.generativeai translation."""
from unittest.mock import MagicMock


def _fake(text='ok', function_calls=None, finish='STOP', in_tok=10, out_tok=5):
    from types import SimpleNamespace
    parts = []
    if text:
        parts.append(SimpleNamespace(text=text, function_call=None))
    if function_calls:
        for fc in function_calls:
            parts.append(SimpleNamespace(
                text=None,
                function_call=SimpleNamespace(name=fc['name'], args=fc['args']),
            ))
    return SimpleNamespace(
        candidates=[SimpleNamespace(
            content=SimpleNamespace(parts=parts),
            finish_reason=finish,
        )],
        usage_metadata=SimpleNamespace(
            prompt_token_count=in_tok,
            candidates_token_count=out_tok,
            cached_content_token_count=0,
        ),
    )


def test_gemini_simple_chat(monkeypatch):
    from llm import gemini as gm
    from llm.base import Message

    fake = MagicMock()
    fake.generate_content.return_value = _fake(text='hello')
    monkeypatch.setattr(gm, '_build_model', lambda **kw: fake)

    llm = gm.GeminiLLM(model_id='gemini-2.0-pro', api_key='sk-test')
    resp = llm.chat([Message(role='user', content='hi')])
    assert resp.messages[0].content == 'hello'
    assert resp.stop_reason == 'end_turn'


def test_gemini_parses_function_call(monkeypatch):
    from llm import gemini as gm
    from llm.base import Message, ToolSpec

    fake = MagicMock()
    fake.generate_content.return_value = _fake(
        text='',
        function_calls=[{'name': 'get_kline', 'args': {'code': '600519.SH'}}],
    )
    monkeypatch.setattr(gm, '_build_model', lambda **kw: fake)

    llm = gm.GeminiLLM(model_id='gemini-2.0-pro', api_key='sk-test')
    tools = [ToolSpec(name='get_kline', description='K', input_schema={})]
    resp = llm.chat([Message(role='user', content='q')], tools=tools)

    assert resp.stop_reason == 'tool_use'
    assert resp.tool_calls[0].name == 'get_kline'
    assert resp.tool_calls[0].input == {'code': '600519.SH'}


def test_gemini_separates_system_instruction(monkeypatch):
    from llm import gemini as gm
    from llm.base import Message

    captured = {}
    def _cap(**kw):
        captured.update(kw)
        fake = MagicMock()
        fake.generate_content.return_value = _fake(text='ok')
        return fake
    monkeypatch.setattr(gm, '_build_model', _cap)

    llm = gm.GeminiLLM(model_id='gemini-2.0-pro', api_key='sk-test')
    llm.chat([
        Message(role='system', content='You are X'),
        Message(role='user', content='q'),
    ])
    assert captured.get('system_instruction') == 'You are X'
