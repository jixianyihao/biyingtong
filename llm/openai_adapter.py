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
        extra_body: dict | None = None,
        force_stream: bool = False,
    ):
        self.model_id = model_id
        self.provider = provider
        self.training_cutoff = training_cutoff
        self._api_key = api_key
        self._base_url = base_url
        self._extra_body = extra_body
        self._force_stream = force_stream

    def _response_from_stream(self, stream) -> LLMResponse:
        content_parts: list[str] = []
        tool_parts: dict[int, dict[str, str]] = {}
        finish_reason = 'stop'
        usage_raw = None

        for chunk in stream:
            usage_raw = getattr(chunk, 'usage', None) or usage_raw
            for choice in (getattr(chunk, 'choices', None) or []):
                finish_reason = getattr(choice, 'finish_reason', None) or finish_reason
                delta = getattr(choice, 'delta', None)
                if delta is None:
                    continue
                piece = getattr(delta, 'content', None)
                if piece:
                    content_parts.append(piece)
                for tc in (getattr(delta, 'tool_calls', None) or []):
                    idx = getattr(tc, 'index', None)
                    if idx is None:
                        idx = len(tool_parts)
                    state = tool_parts.setdefault(
                        idx, {'id': '', 'name': '', 'arguments': ''})
                    tc_id = getattr(tc, 'id', None)
                    if tc_id:
                        state['id'] = tc_id
                    fn = getattr(tc, 'function', None)
                    if fn is not None:
                        name = getattr(fn, 'name', None)
                        if name:
                            state['name'] += name
                        args = getattr(fn, 'arguments', None)
                        if args:
                            state['arguments'] += args

        reply = []
        text = ''.join(content_parts)
        if text:
            reply.append(Message(role='assistant', content=text))

        tool_calls: list[ToolCall] = []
        for state in [tool_parts[i] for i in sorted(tool_parts)]:
            try:
                args = json.loads(state['arguments'] or '{}')
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(
                id=state['id'], name=state['name'], input=args))

        usage = Usage(
            input_tokens=getattr(usage_raw, 'prompt_tokens', 0) if usage_raw else 0,
            output_tokens=getattr(usage_raw, 'completion_tokens', 0) if usage_raw else 0,
            cached_read_tokens=0,
        )
        return LLMResponse(
            messages=reply,
            tool_calls=tool_calls,
            stop_reason=_STOP_MAP.get(finish_reason, 'other'),
            usage=usage,
        )

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        cacheable_prefix_len: int = 0,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        client = _get_client(api_key=self._api_key, base_url=self._base_url)

        openai_msgs: list[dict] = []
        for m in messages:
            # Translate Anthropic-style content blocks (produced by AgentRunner
            # for tool_result and assistant tool_use turns) into OpenAI format.
            if isinstance(m.content, list):
                if m.role == 'user':
                    # Split tool_result blocks into individual role='tool' messages
                    for block in m.content:
                        if isinstance(block, dict) and block.get('type') == 'tool_result':
                            openai_msgs.append({
                                'role': 'tool',
                                'tool_call_id': block.get('tool_use_id', ''),
                                'content': block.get('content', ''),
                            })
                        elif isinstance(block, dict) and block.get('type') == 'text':
                            openai_msgs.append({
                                'role': 'user',
                                'content': block.get('text', ''),
                            })
                    continue
                if m.role == 'assistant':
                    text_parts = []
                    tc_list = []
                    for block in m.content:
                        if not isinstance(block, dict):
                            continue
                        if block.get('type') == 'text':
                            text_parts.append(block.get('text', ''))
                        elif block.get('type') == 'tool_use':
                            tc_list.append({
                                'id': block.get('id', ''),
                                'type': 'function',
                                'function': {
                                    'name': block.get('name', ''),
                                    'arguments': json.dumps(
                                        block.get('input', {}),
                                        ensure_ascii=False,
                                    ),
                                },
                            })
                    d: dict = {
                        'role': 'assistant',
                        'content': '\n'.join(text_parts) if text_parts else None,
                    }
                    if tc_list:
                        d['tool_calls'] = tc_list
                    openai_msgs.append(d)
                    continue
                # Fallback: stringify
                openai_msgs.append({'role': m.role,
                                    'content': json.dumps(m.content, ensure_ascii=False)})
                continue
            d = {'role': m.role, 'content': m.content}
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

        if self._extra_body:
            kwargs['extra_body'] = self._extra_body
        if self._force_stream:
            kwargs['stream'] = True

        try:
            raw = client.chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001
            kind, retry = _classify(e)
            raise LLMError(self.provider, kind, str(e), retryable=retry) from e

        if self._force_stream:
            return self._response_from_stream(raw)

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
