"""Anthropic adapter — wraps `anthropic` SDK with canonical Message/ToolSpec."""
from __future__ import annotations

from .base import LLMBase, LLMError, LLMResponse, Message, ToolCall, ToolSpec, Usage


def _get_client(api_key: str):
    """Lazy SDK import; monkeypatched in tests."""
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def _classify(e: Exception) -> tuple[str, bool]:
    msg = str(e).lower()
    if '429' in msg or 'rate' in msg:
        return 'rate_limit', True
    if 'timeout' in msg:
        return 'timeout', True
    if '401' in msg or '403' in msg or 'auth' in msg:
        return 'auth', False
    if '400' in msg or 'invalid' in msg:
        return 'bad_request', False
    if '5' in msg[:3] or 'server' in msg:
        return 'server_error', True
    return 'other', False


class ClaudeLLM(LLMBase):
    provider = 'anthropic'

    def __init__(self, model_id: str, api_key: str, training_cutoff: str = '2026-01-31'):
        self.model_id = model_id
        self.training_cutoff = training_cutoff
        self._api_key = api_key

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        cacheable_prefix_len: int = 0,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        client = _get_client(self._api_key)

        system_msgs = [m for m in messages if m.role == 'system']
        other_msgs = [m for m in messages if m.role != 'system']

        system_param = None
        if system_msgs:
            sys_text = '\n\n'.join(
                m.content if isinstance(m.content, str) else str(m.content)
                for m in system_msgs
            )
            if cacheable_prefix_len >= 1:
                system_param = [{
                    'type': 'text', 'text': sys_text,
                    'cache_control': {'type': 'ephemeral'},
                }]
            else:
                system_param = sys_text

        anthropic_tools = None
        if tools:
            anthropic_tools = []
            last = len(tools) - 1
            for i, t in enumerate(tools):
                entry = {
                    'name': t.name,
                    'description': t.description,
                    'input_schema': t.input_schema,
                }
                if cacheable_prefix_len >= 1 and i == last:
                    entry['cache_control'] = {'type': 'ephemeral'}
                anthropic_tools.append(entry)

        kwargs = dict(
            model=self.model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{'role': m.role, 'content': m.content} for m in other_msgs],
        )
        if system_param is not None:
            kwargs['system'] = system_param
        if anthropic_tools is not None:
            kwargs['tools'] = anthropic_tools

        try:
            raw = client.messages.create(**kwargs)
        except Exception as e:  # noqa: BLE001
            kind, retry = _classify(e)
            raise LLMError('anthropic', kind, str(e), retryable=retry) from e

        reply_messages: list[Message] = []
        tool_calls: list[ToolCall] = []
        for block in raw.content:
            btype = getattr(block, 'type', None)
            if btype == 'text':
                reply_messages.append(Message(role='assistant', content=block.text))
            elif btype == 'tool_use':
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))

        usage = Usage(
            input_tokens=getattr(raw.usage, 'input_tokens', 0),
            output_tokens=getattr(raw.usage, 'output_tokens', 0),
            cached_read_tokens=getattr(raw.usage, 'cache_read_input_tokens', 0) or 0,
            cached_write_tokens=getattr(raw.usage, 'cache_creation_input_tokens', 0) or 0,
        )

        return LLMResponse(
            messages=reply_messages,
            tool_calls=tool_calls,
            stop_reason=raw.stop_reason or 'end_turn',
            usage=usage,
        )
