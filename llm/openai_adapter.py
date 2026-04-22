"""OpenAI-compatible adapter — OpenAI, DeepSeek, Moonshot, etc."""
from __future__ import annotations

import json

from .base import LLMBase, LLMError, LLMResponse, Message, ToolCall, ToolSpec, Usage


def _get_client(api_key: str, base_url: str | None = None):
    import openai
    if base_url:
        return openai.OpenAI(api_key=api_key, base_url=base_url)
    return openai.OpenAI(api_key=api_key)


_STOP_MAP = {
    'stop': 'end_turn', 'length': 'max_tokens',
    'tool_calls': 'tool_use', 'function_call': 'tool_use',
    'content_filter': 'error',
}


def _classify(e: Exception) -> tuple[str, bool]:
    msg = str(e).lower()
    if '429' in msg or 'rate' in msg:
        return 'rate_limit', True
    if 'timeout' in msg:
        return 'timeout', True
    if '401' in msg or '403' in msg or 'auth' in msg or 'api key' in msg:
        return 'auth', False
    if '400' in msg or 'invalid' in msg:
        return 'bad_request', False
    return 'other', False


class OpenAILLM(LLMBase):
    def __init__(
        self, model_id: str, api_key: str,
        base_url: str | None = None,
        provider: str = 'openai',
        training_cutoff: str = '2025-10-31',
    ):
        self.model_id = model_id
        self.provider = provider
        self.training_cutoff = training_cutoff
        self._api_key = api_key
        self._base_url = base_url

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        cacheable_prefix_len: int = 0,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        client = _get_client(api_key=self._api_key, base_url=self._base_url)

        openai_msgs = []
        for m in messages:
            d: dict = {'role': m.role, 'content': m.content}
            if m.tool_call_id is not None:
                d['tool_call_id'] = m.tool_call_id
            openai_msgs.append(d)

        kwargs = dict(
            model=self.model_id,
            messages=openai_msgs,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs['tools'] = [
                {
                    'type': 'function',
                    'function': {
                        'name': t.name,
                        'description': t.description,
                        'parameters': t.input_schema,
                    },
                }
                for t in tools
            ]

        try:
            raw = client.chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001
            kind, retry = _classify(e)
            raise LLMError(self.provider, kind, str(e), retryable=retry) from e

        choice = raw.choices[0]
        msg = choice.message

        reply: list[Message] = []
        if msg.content:
            reply.append(Message(role='assistant', content=msg.content))

        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, input=args))

        cached = 0
        if raw.usage and getattr(raw.usage, 'prompt_tokens_details', None) is not None:
            cached = getattr(raw.usage.prompt_tokens_details, 'cached_tokens', 0) or 0

        usage = Usage(
            input_tokens=raw.usage.prompt_tokens if raw.usage else 0,
            output_tokens=raw.usage.completion_tokens if raw.usage else 0,
            cached_read_tokens=cached,
        )

        return LLMResponse(
            messages=reply,
            tool_calls=tool_calls,
            stop_reason=_STOP_MAP.get(choice.finish_reason, 'other'),
            usage=usage,
        )
