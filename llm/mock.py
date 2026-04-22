"""MockLLM — scripted-response adapter for deterministic tests."""
from __future__ import annotations

from .base import LLMBase, LLMResponse, Message, ToolCall, ToolSpec, Usage


class MockLLM(LLMBase):
    provider = 'mock'
    model_id = 'mock'
    training_cutoff = '2099-12-31'

    def __init__(self, scripted: list[dict]):
        self._scripted = list(scripted)
        self._idx = 0
        self.calls: list[dict] = []

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        cacheable_prefix_len: int = 0,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        self.calls.append({
            'messages': list(messages),
            'tools': list(tools) if tools else [],
            'cacheable_prefix_len': cacheable_prefix_len,
            'temperature': temperature,
            'max_tokens': max_tokens,
        })

        assert self._idx < len(self._scripted), (
            f'MockLLM script exhausted after {self._idx} call(s)'
        )
        spec = self._scripted[self._idx]
        self._idx += 1

        tool_calls = [ToolCall(id=tc['id'], name=tc['name'], input=tc['input'])
                      for tc in spec.get('tool_calls', [])]

        text = spec.get('text', '') or ''
        reply = [Message(role='assistant', content=text)] if text else []

        input_text = ''.join(m.content for m in messages if isinstance(m.content, str))
        return LLMResponse(
            messages=reply,
            tool_calls=tool_calls,
            stop_reason=spec.get('stop_reason', 'end_turn'),
            usage=Usage(
                input_tokens=max(1, len(input_text) // 4),
                output_tokens=max(1, len(text) // 4),
            ),
        )
