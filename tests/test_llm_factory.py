from unittest.mock import MagicMock


def test_openai_provider_can_use_codex_relay_env(monkeypatch, tmp_path):
    """Codex relay is configured as provider=openai but may arrive via
    ANTHROPIC_* env names in this workflow."""
    import storage
    from llm.base import Message
    from llm.factory import build_llm
    from storage.sqlite_models import SQLiteModelStore

    store = SQLiteModelStore(tmp_path=tmp_path)
    store.init_schema()
    store.seed()
    storage.set_models(store)

    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_BASE_URL', raising=False)
    monkeypatch.setenv('ANTHROPIC_AUTH_TOKEN', 'relay-token')
    monkeypatch.setenv('ANTHROPIC_BASE_URL', 'https://relay.example/api')

    from llm import openai_adapter as oa

    captured = {}

    def _capture(**kw):
        captured.update(kw)
        fake = MagicMock()
        fake.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(role='assistant', content='ok',
                                  tool_calls=None),
                finish_reason='stop',
            )],
            usage=MagicMock(prompt_tokens=1, completion_tokens=1),
        )
        fake.chat.completions.create.return_value.usage.prompt_tokens_details = None
        return fake

    monkeypatch.setattr(oa, '_get_client', _capture)

    try:
        llm = build_llm('gpt-5.3-codex-spark')
        llm.chat([Message(role='user', content='ping')])
    finally:
        storage.reset()

    assert captured['api_key'] == 'relay-token'
    assert captured['base_url'] == 'https://relay.example/api'
